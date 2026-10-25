"""Dev UI server: serves the topology visualization over HTTP.

Not a DI-managed ``Service`` — it introspects the container from the
outside, so it is constructed and driven directly by ``Server.start(ui=True)``
/ ``Server.stop()``, after the ``Context`` has already resolved.
"""

import dataclasses
import json
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
    from pydantic import ValidationError
    from starlette.concurrency import run_in_threadpool
except ImportError as exc:
    raise ImportError(
        "server.start(ui=True) requires the 'ui' extra. Install with: pip install odf[ui]"
    ) from exc

from opendataframework.component import ChartProtocol, DetailsProtocol
from opendataframework.context import Context
from opendataframework.repository import ReadableProtocol, StreamableProtocol, WritableProtocol
from opendataframework.view import (
    AudioView,
    DataView,
    DocumentView,
    ImageView,
    LocationView,
    StreamingAudioView,
    StreamingVideoView,
    TimeseriesView,
    VideoView,
)

from odf.ui import annotations, arguments, data, events, keys, layout, media, themes
from odf.ui.notebooks import NotebookServer, local_host
from odf.ui.origin import HostCheck, OriginCheck
from odf.ui.topology import TopologyView, build_topology

if TYPE_CHECKING:
    from odf.chat.engine import ChatEngine

_STREAM_BOUNDARY = "odf-frame"

_MEDIA_CONTENT_TYPES: dict[type, str] = {
    ImageView: "image/jpeg",
    VideoView: "video/mp4",
    AudioView: "audio/wav",
    DocumentView: "application/octet-stream",
}

# The views whose annotations are one list for the repository, not per record.
_LIST_VIEWS = (TimeseriesView, LocationView)


class UiServer:
    """Serves the UI for a single ``Context`` over HTTP.

    Runs uvicorn in a background daemon thread so ``start()`` never blocks
    the caller — mirroring how the framework backgrounds ``Service.run()``.

    Args:
        context: The already-open ``Context`` to introspect on every request.
        project: Display name shown in the UI header.
        host: Interface to bind to.
        port: Port to bind to.
        layout_file: Path to persist dragged node grid positions to, as JSON.
            ``None`` (the default) disables layout persistence entirely — the
            ``/api/layout`` endpoints become a read-only no-op — mirroring how
            ``Context``'s ``log_dir=None`` disables file logging. ``Project``
            opts in to a real path when starting the UI.
        annotations_file: Path to persist annotations drawn in the image,
            document, video, audio, timeseries and location views, and the classes given to records,
            to, as JSON (see ``odf.ui.annotations``). ``None`` (the default)
            disables annotation — the UI offers no drawing and the save
            endpoint returns 404. ``Project`` opts in to a real path when
            starting the UI.
        chat_engine: A ready ``ChatEngine`` to serve the chat window through,
            or ``None`` (the default) to disable it — the chat toggle stays
            hidden in the UI and ``POST /api/chat`` returns 404. ``Project``
            builds this when ``start(chat=True)`` is passed.
        icon_scripts: Paths to ``.js`` files registering custom icons into
            the UI (see ``odf.ui.extensions``), served under
            ``/api/ui/icon-scripts/{index}`` and listed in
            ``GET /api/ui/extensions``.
        colors: Extra named colors (name → hex) offered in the UI's
            color pickers alongside the built-in swatches.
        favicon: Path to a custom ``.svg`` favicon, served at ``/favicon.svg``
            in place of the built-in ODF mark. ``None`` (the default) keeps
            the built-in favicon.
        logo: Path to a custom logo image (svg/png/...), served at
            ``/api/ui/logo`` and swapped into the header in place of the
            built-in CSS-drawn mark. ``None`` (the default) keeps that mark.
        brand: Display name shown in the header next to the logo, and as the
            browser tab title's prefix (``"{brand} — {project}"``). ``None``
            (the default) keeps the built-in ``"ODF"`` label. Distinct from
            ``project`` — that's the specific project being visualized;
            this is the product/tool name wrapping around it.
        theme: Name of the UI theme (visual file-set) to serve, or a path to
            a theme directory of the project's own — see
            ``odf.ui.themes``. Defaults to ``"default"``. Orthogonal to the
            UI's own client-side light/dark color-mode toggle, which each
            theme keeps working independently.
        topology: Which components and connections the topology shows — see
            ``odf.ui.topology.TopologyView``. ``None`` (the default) shows
            everything. Display-only: hidden components stay reachable through
            the other endpoints.
        notebooks: Whether a notebook in a document view can be edited in
            the reader, in a Jupyter Notebook server launched on the first
            edit (see ``odf.ui.notebooks``) and reached through the UI at
            ``/proxy/jupyter/`` (see ``odf.ui.proxy``). Needs the
            ``notebook`` package.
            ``False`` (the default) only renders notebooks.
        grid: How the topology grid is drawn: ``"iso"`` (the default), the
            isometric grid with a building per node, or ``"flat"``, a
            top-down schematic with every node the same shape in its type's
            color and node customization turned off (see
            ``static/grids/flat.js``).
    """

    def __init__(
        self,
        context: Context,
        project: str,
        host: str = "127.0.0.1",
        port: int = 4747,
        layout_file: str | Path | None = None,
        annotations_file: str | Path | None = None,
        chat_engine: ChatEngine | None = None,
        icon_scripts: list[Path] | None = None,
        colors: dict[str, str] | None = None,
        favicon: str | Path | None = None,
        logo: str | Path | None = None,
        brand: str | None = None,
        theme: str = "default",
        topology: TopologyView | None = None,
        notebooks: bool = False,
        grid: str = "iso",
    ) -> None:
        """Build the FastAPI app and register every route (see class docstring for args)."""
        self._context = context
        self._project = project
        self._host = host
        self._port = port
        self._layout_path = Path(layout_file) if layout_file is not None else None
        self._annotations_path = Path(annotations_file) if annotations_file is not None else None
        # Saving is load-modify-write on one file, from FastAPI's thread pool.
        self._annotations_lock = threading.Lock()
        self._chat = chat_engine
        self._icon_scripts = list(icon_scripts) if icon_scripts is not None else []
        self._colors = dict(colors) if colors is not None else {}
        self._favicon = Path(favicon) if favicon is not None else None
        self._logo = Path(logo) if logo is not None else None
        self._brand = brand
        self._theme_dir = themes.theme_dir(theme)
        self._topology = topology
        self._grid = grid
        self._notebooks: NotebookServer | None = None
        self._events = events.EventHub(context)
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

        app = FastAPI(title="ODF Topology", docs_url=None, redoc_url=None)
        app.add_middleware(OriginCheck)

        if notebooks:
            # Only now: forwarding needs tornado, which comes with Jupyter.
            from odf.ui import proxy

            self._notebooks = NotebookServer(self.local_url, proxy.prefix("jupyter"), Path.cwd())
            proxy.mount_proxy(
                app, "jupyter", lambda: self._notebooks.origin, lambda: self._notebooks.credentials
            )

        @app.get("/api/topology")
        def topology() -> dict:
            """Return the current node/edge graph for the topology view."""
            saved = layout.load(self._layout_path) if self._layout_path is not None else {}
            return build_topology(self._context, self._project, self._topology, saved)

        @app.get("/api/layout")
        def get_layout() -> dict:
            """Return persisted node grid positions, or ``{}`` if unset."""
            return layout.load(self._layout_path) if self._layout_path is not None else {}

        @app.put("/api/layout", status_code=204)
        def put_layout(body: dict) -> None:
            """Persist dragged node grid positions, if layout persistence is enabled."""
            if self._layout_path is not None:
                layout.save(self._layout_path, body)

        @app.get("/api/ui/extensions")
        def ui_extensions() -> dict:
            """List icon scripts, colors, the custom logo, brand, grid, and enabled features."""
            return {
                "iconScripts": [
                    f"/api/ui/icon-scripts/{i}" for i in range(len(self._icon_scripts))
                ],
                "colors": self._colors,
                "logo": "/api/ui/logo" if self._logo is not None else None,
                "brand": self._brand,
                "grid": self._grid,
                "annotations": self._annotations_path is not None,
                "notebooks": self._notebooks is not None,
            }

        @app.get("/api/ui/logo")
        def logo() -> FileResponse:
            """Serve the project's custom logo image, if one is configured."""
            if self._logo is None:
                raise HTTPException(status_code=404, detail="No custom logo configured")
            return FileResponse(self._logo)

        @app.get("/api/ui/icon-scripts/{index}")
        def icon_script(index: int) -> FileResponse:
            """Serve one registered icon script by its position in ``icon_scripts``."""
            if not 0 <= index < len(self._icon_scripts):
                raise HTTPException(status_code=404, detail="Icon script not found")
            return FileResponse(self._icon_scripts[index], media_type="application/javascript")

        @app.get("/api/repositories")
        def repositories() -> list[dict]:
            """List every repository resolved in the context, with its shape."""
            return data.build_repositories(self._context)

        @app.get("/api/repositories/{repo_id}/records")
        def list_records(
            repo_id: str,
            request: Request,
            response: Response,
            limit: int | None = None,
            offset: int = 0,
        ) -> list[dict]:
            """List a repository's records, paginated and filtered by query params."""
            _, instance, entity_cls = self._get_readable(repo_id)
            filters = data.parse_filters(entity_cls, request.query_params.items())
            view = data.resolve_view(instance, readable=True)
            records, total = data.list_records(
                instance, entity_cls, limit=limit, offset=offset, filters=filters, view=view
            )
            response.headers["X-Total-Count"] = str(total)
            return records

        @app.post("/api/repositories/{repo_id}/records", status_code=201)
        def create_record(repo_id: str, body: dict) -> dict:
            """Create a new record in a repository from the request body."""
            _, instance, entity_cls = self._get_writable(repo_id)
            entity = data.build_entity(
                entity_cls, body, key=data.key_field_name(entity_cls), key_value=None
            )
            instance.save(entity)
            return data.to_json_safe_dict(entity)

        @app.put("/api/repositories/{repo_id}/records/{key}")
        def update_record(repo_id: str, key: str, body: dict) -> dict:
            """Update the record matching ``key`` with the request body."""
            _, instance, entity_cls = self._get_writable(repo_id)
            key_field = data.key_field_name(entity_cls)
            entity = data.build_entity(
                entity_cls,
                body,
                key=key_field,
                key_value=data.coerce_key(entity_cls, key_field, key),
            )
            instance.save(entity)
            return data.to_json_safe_dict(entity)

        @app.delete("/api/repositories/{repo_id}/records/{key}", status_code=204)
        def delete_record(repo_id: str, key: str) -> None:
            """Delete the record matching ``key`` from a repository."""
            _, instance, entity_cls = self._get_writable(repo_id)
            key_field = data.key_field_name(entity_cls)
            instance.delete(data.coerce_key(entity_cls, key_field, key))

        @app.post("/api/repositories/{repo_id}/start-stream", status_code=204)
        def start_stream(repo_id: str) -> None:
            """Start a streamable repository's shared background stream."""
            repo_cls, _, _ = self._get_streamable(repo_id)
            self._context.start_stream(self._context.key(repo_cls))

        @app.post("/api/repositories/{repo_id}/stop-stream", status_code=204)
        def stop_stream(repo_id: str) -> None:
            """Stop a streamable repository's shared background stream."""
            repo_cls, _, _ = self._get_streamable(repo_id)
            self._context.stop_stream(self._context.key(repo_cls))

        @app.get("/api/repositories/{repo_id}/stream")
        def stream_records(repo_id: str) -> Response:
            """Subscribe to a running stream and return its next chunk(s)."""
            repo_cls, _, _ = self._get_streamable(repo_id)
            view = self._get_streaming_view(repo_id)
            try:
                entities = self._context.iter_stream(self._context.key(repo_cls))
            except KeyError as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"{repo_cls.__name__} is not streaming — start it first",
                ) from exc
            if isinstance(view, StreamingAudioView):
                # multipart/x-mixed-replace only has browser support for <img>
                # (MJPEG) — <audio> can't consume it. So instead of one
                # multiplexed connection, each request pulls exactly one
                # complete, independently decodable chunk off the shared
                # subscription; the frontend polls this endpoint in a chain
                # (see showStreamView() in the dev UI) to approximate a live
                # feed. entities.close() unsubscribes immediately rather than
                # leaving the queue attached until GC.
                try:
                    chunk = getattr(next(entities), view.field)
                except StopIteration as exc:
                    raise HTTPException(status_code=409, detail="stream ended") from exc
                finally:
                    entities.close()
                return Response(content=chunk, media_type="audio/wav")
            return StreamingResponse(
                self._multipart_stream(entities, view.field, "image/jpeg"),
                media_type=f"multipart/x-mixed-replace; boundary={_STREAM_BOUNDARY}",
            )

        @app.get("/api/repositories/{repo_id}/records/{key}/media")
        def record_media(repo_id: str, key: str, request: Request) -> Response:
            """Return the raw media bytes (image/video/audio/document) for one record.

            Honors a single-range ``Range`` header with a ``206``, which is
            what lets a browser seek within a clip (and Safari play one).

            A document is only ever served as a PDF, as plain text or as an
            opaque download, and never left for the browser to sniff, so
            stored markup can't run on the UI's origin when it is opened.

            A repository's ``content_metadata()`` names the content, sent as
            ``Content-Disposition``, and declares its type, taken over
            sniffing within those same rules (see ``media.media_type``).
            """
            _, instance, entity_cls = self._get_readable(repo_id)
            view = self._get_data_view(repo_id)
            default_type = _MEDIA_CONTENT_TYPES.get(type(view))
            if default_type is None:
                raise HTTPException(status_code=403, detail="Repository has no media view")
            key_field = data.key_field_name(entity_cls)
            coerced_key = data.coerce_key(entity_cls, key_field, key)
            record = next((r for r in instance.all() if getattr(r, key_field) == coerced_key), None)
            if record is None:
                raise HTTPException(status_code=404, detail="Record not found")
            content = getattr(record, view.field)
            if not isinstance(content, (bytes, bytearray)):
                raise HTTPException(status_code=404, detail="Record has no media")
            content = bytes(content)
            metadata = data.content_metadata(instance, view, record)
            declared_type = metadata.content_type if metadata is not None else None
            headers = {"Accept-Ranges": "bytes"}
            sniff_length = media.SNIFF_LENGTH
            if isinstance(view, DocumentView):
                sniff_length = media.DOCUMENT_SNIFF_LENGTH
            if isinstance(view, DocumentView) or declared_type:
                headers["X-Content-Type-Options"] = "nosniff"
            disposition = media.content_disposition(metadata.filename if metadata else None)
            if disposition is not None:
                headers["Content-Disposition"] = disposition
            content_type = media.media_type(content[:sniff_length], default_type, declared_type)
            try:
                byte_range = media.parse_range(request.headers.get("range"), len(content))
            except ValueError:
                return Response(
                    status_code=416,
                    headers={**headers, "Content-Range": f"bytes */{len(content)}"},
                )
            if byte_range is None:
                return Response(content=content, media_type=content_type, headers=headers)
            start, end = byte_range
            headers["Content-Range"] = f"bytes {start}-{end}/{len(content)}"
            return Response(
                content=content[start : end + 1],
                status_code=206,
                media_type=content_type,
                headers=headers,
            )

        @app.put("/api/repositories/{repo_id}/records/{key}/media", status_code=204)
        async def put_record_media(repo_id: str, key: str, request: Request) -> None:
            """Replace a document record's file with the request body, through ``save()``.

            Only a record whose document is a file (bytes) takes one: a
            document held in the record itself is edited as a field instead.
            This is how a notebook edited in Jupyter is saved (see
            ``odf.ui.notebook_contents``).
            """
            body = await request.body()
            await run_in_threadpool(self._replace_document, repo_id, key, body)

        @app.post("/api/notebooks/session")
        def notebook_session() -> dict:
            """Launch the Jupyter that edits notebooks, if needed, and say how to reach it."""
            if self._notebooks is None:
                raise HTTPException(status_code=404, detail="Notebook editing is not enabled")
            try:
                self._notebooks.start()
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            return {"url": "/proxy/jupyter/"}

        @app.get("/api/repositories/{repo_id}/annotations")
        def repository_annotations(repo_id: str) -> dict:
            """Return a repository's labels and annotations.

            An image, document, video or audio repository's are per record,
            a timeseries or location repository's one list (see
            ``odf.ui.annotations``).
            """
            view = self._get_annotatable_view(repo_id)
            block = annotations.series if isinstance(view, _LIST_VIEWS) else annotations.repository
            if self._annotations_path is None:
                return block({}, repo_id)
            with self._annotations_lock:
                return block(self._load_annotations(), repo_id)

        @app.put("/api/repositories/{repo_id}/annotations")
        def put_repository_annotations(repo_id: str, body: dict) -> dict:
            """Replace a timeseries or location repository's annotations, returning its labels."""
            view = self._get_annotatable_view(repo_id)
            if not isinstance(view, _LIST_VIEWS):
                raise HTTPException(
                    status_code=404, detail="Repository's annotations are per record"
                )
            replace = (
                annotations.set_series
                if isinstance(view, TimeseriesView)
                else annotations.set_regions
            )
            if self._annotations_path is None:
                raise HTTPException(status_code=404, detail="Annotations are not enabled")
            with self._annotations_lock:
                saved = self._load_annotations()
                try:
                    block = replace(saved, repo_id, body.get("annotations"))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                annotations.save(self._annotations_path, saved)
            return {"labels": block["labels"]}

        @app.put("/api/repositories/{repo_id}/records/{key}/annotations")
        def put_record_annotations(repo_id: str, key: str, body: dict) -> dict:
            """Replace one record's annotations, returning the repository's labels."""
            view = self._get_annotatable_view(repo_id)
            if isinstance(view, _LIST_VIEWS):
                raise HTTPException(
                    status_code=404, detail="Repository's annotations are not per record"
                )
            if self._annotations_path is None:
                raise HTTPException(status_code=404, detail="Annotations are not enabled")
            with self._annotations_lock:
                saved = self._load_annotations()
                try:
                    if isinstance(view, DocumentView):
                        block = annotations.set_document_record(
                            saved, repo_id, key, body.get("annotations")
                        )
                    elif isinstance(view, (VideoView, AudioView)):
                        block = annotations.set_clip_record(
                            saved, repo_id, key, body.get("duration"), body.get("annotations")
                        )
                    else:
                        block = annotations.set_record(
                            saved,
                            repo_id,
                            key,
                            body.get("width"),
                            body.get("height"),
                            body.get("annotations"),
                        )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                annotations.save(self._annotations_path, saved)
            return {"labels": block["labels"]}

        @app.get("/api/repositories/{repo_id}/classes")
        def repository_classes(repo_id: str) -> dict:
            """Return a repository's classes and the class of each record that has one."""
            self._get_classifiable_view(repo_id)
            if self._annotations_path is None:
                return annotations.classes({}, repo_id)
            with self._annotations_lock:
                return annotations.classes(self._load_annotations(), repo_id)

        @app.put("/api/repositories/{repo_id}/records/{key}/class")
        def put_record_class(repo_id: str, key: str, body: dict) -> dict:
            """Set one record's class, or clear it, returning the repository's classes."""
            self._get_classifiable_view(repo_id)
            if self._annotations_path is None:
                raise HTTPException(status_code=404, detail="Annotations are not enabled")
            with self._annotations_lock:
                saved = self._load_annotations()
                try:
                    block = annotations.set_class(saved, repo_id, key, body.get("class"))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                annotations.save(self._annotations_path, saved)
            return {"classes": block["classes"]}

        # Every resolved class is served under its execution type's
        # collection, by registered name: a @Task registered as "loader" is
        # /api/tasks/loader (see odf.ui.keys). Actions that only apply to one
        # kind have routes for that kind only.

        @app.get("/api/events")
        def run_events() -> StreamingResponse:
            """Stream every protocol call the context makes, as server-sent events."""
            return StreamingResponse(
                events.sse(self._events),
                media_type="text/event-stream",
                # X-Accel-Buffering: nginx would otherwise hold events back.
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        @app.get("/api/{collection}/{name}/logs")
        def component_logs(collection: str, name: str) -> list[dict]:
            """Return a component's tailed log records."""
            cls = self._find_or_404(collection, name)
            return self._context.tail_logs(self._context.key(cls))

        @app.get("/api/{collection}/{name}/details")
        def component_details(collection: str, name: str) -> dict[str, str]:
            """Return a component's ``DetailsProtocol`` key/value details."""
            return self._get_details(collection, name).details()

        @app.get("/api/{collection}/{name}/chart", response_class=HTMLResponse)
        def component_chart(collection: str, name: str) -> str:
            """Return a component's ``ChartProtocol`` HTML chart."""
            return self._get_chart(collection, name).chart()

        @app.post("/api/services/{name}/start", status_code=204)
        def start_service(name: str) -> None:
            """Start a service through the context."""
            cls = self._find_or_404("services", name)
            try:
                self._context.start(self._context.key(cls))
            except TypeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/api/services/{name}/stop", status_code=204)
        def stop_service(name: str) -> None:
            """Stop a service through the context."""
            cls = self._find_or_404("services", name)
            try:
                self._context.stop(self._context.key(cls))
            except TypeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/api/{collection}/{name}/execute", status_code=204)
        def execute(collection: str, name: str) -> None:
            """Execute a task or pipeline through the context."""
            if collection not in ("tasks", "pipelines"):
                raise HTTPException(status_code=404, detail="Not found")
            cls = self._find_or_404(collection, name)
            try:
                self._context.execute(self._context.key(cls))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        # Whatever takes arguments (see odf.ui.arguments): an agent's
        # /api/agents/{name}/{parameters,invoke}, a function's
        # /api/functions/{name}/{parameters,call}.
        for kind, entry in arguments.ENTRIES.items():
            collection = keys.COLLECTIONS[kind]
            app.add_api_route(
                f"/api/{collection}/{{name}}/parameters",
                self._parameters_route(collection),
                methods=["GET"],
                name=f"{kind}_parameters",
            )
            app.add_api_route(
                f"/api/{collection}/{{name}}/{entry.verb}",
                self._call_route(collection),
                methods=["POST"],
                name=f"{kind}_{entry.verb}",
            )

        @app.get("/api/chat/config")
        def chat_config() -> dict:
            """Report whether chat is enabled and which model it uses."""
            return {
                "enabled": self._chat is not None,
                "model": self._chat.model if self._chat else None,
            }

        @app.post("/api/chat")
        def chat(body: dict) -> StreamingResponse:
            """Stream one chat turn's events as newline-delimited JSON."""
            if self._chat is None:
                raise HTTPException(status_code=404, detail="Chat is not enabled")
            return StreamingResponse(
                self._chat_events(body.get("messages", [])), media_type="application/x-ndjson"
            )

        # The UI's own files are revalidated on every load: ``/theme.css`` and
        # ``/theme.js`` change content with the selected theme, and all of them
        # change together on upgrade, so a stale cached copy would mix them.
        no_cache = {"Cache-Control": "no-cache"}

        @app.get("/")
        def index() -> FileResponse:
            """Serve the UI's ``index.html``, shared by every theme."""
            return FileResponse(themes.STATIC_DIR / "index.html", headers=no_cache)

        @app.get("/app.js")
        def app_js() -> FileResponse:
            """Serve the UI's script, shared by every theme."""
            return FileResponse(
                themes.STATIC_DIR / "app.js", media_type="application/javascript", headers=no_cache
            )

        @app.get("/icons/{name}")
        def icon_group(name: str) -> FileResponse:
            """Serve one of the UI's built-in icon group scripts."""
            icons_dir = themes.STATIC_DIR / "icons"
            if name not in {p.name for p in icons_dir.glob("*.js")}:
                raise HTTPException(status_code=404, detail=f"Unknown icon script: {name}")
            return FileResponse(
                icons_dir / name, media_type="application/javascript", headers=no_cache
            )

        @app.get("/grids/{name}")
        def grid_script(name: str) -> FileResponse:
            """Serve one of the UI's built-in grid scripts."""
            grids_dir = themes.STATIC_DIR / "grids"
            if name not in {p.name for p in grids_dir.glob("*.js")}:
                raise HTTPException(status_code=404, detail=f"Unknown grid script: {name}")
            return FileResponse(
                grids_dir / name, media_type="application/javascript", headers=no_cache
            )

        @app.get("/theme.css")
        def theme_css() -> FileResponse:
            """Serve the selected theme's stylesheet."""
            return FileResponse(
                self._theme_dir / "theme.css", media_type="text/css", headers=no_cache
            )

        @app.get("/theme.js")
        def theme_js() -> Response:
            """Serve the selected theme's script — empty if it doesn't have one."""
            path = self._theme_dir / "theme.js"
            if not path.is_file():
                return Response("", media_type="application/javascript", headers=no_cache)
            return FileResponse(path, media_type="application/javascript", headers=no_cache)

        @app.get("/favicon.svg")
        def favicon() -> FileResponse:
            """Serve the UI's favicon — the project's custom one, if configured."""
            path = self._favicon if self._favicon is not None else self._theme_dir / "favicon.svg"
            return FileResponse(path, media_type="image/svg+xml")

        self._app = app

    def _parameters_route(self, collection: str) -> Callable[[str], dict]:
        """Return the route serving the JSON schema of a ``collection`` object's arguments."""

        def parameters(name: str) -> dict:
            """Return the JSON schema of the arguments the named object takes."""
            obj = self._find_or_404(collection, name)
            return arguments.model(self._context, obj).model_json_schema()

        return parameters

    def _call_route(self, collection: str) -> Callable[[str, dict], dict]:
        """Return the route calling a ``collection`` object through ``Context.call()``."""

        def call(name: str, body: dict) -> dict:
            """Call the named object, with the request body as its arguments."""
            obj = self._find_or_404(collection, name)
            model = arguments.model(self._context, obj)
            try:
                validated = model.model_validate(body)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422, detail=jsonable_encoder(exc.errors(include_url=False))
                ) from exc
            kwargs = {field: getattr(validated, field) for field in type(validated).model_fields}
            try:
                result = self._context.call(self._context.key(obj), **kwargs)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            try:
                return {"result": jsonable_encoder(result)}
            except Exception:
                return {"result": str(result)}

        return call

    def _find_or_404(self, collection: str, name: str) -> type | Callable[..., object]:
        """Resolve ``/api/{collection}/{name}`` to its class or function, or raise 404."""
        cls = keys.resolve_collection(self._context, collection, name)
        if cls is None:
            raise HTTPException(status_code=404, detail="Component not found")
        return cls

    def _get_details(self, collection: str, name: str) -> DetailsProtocol:
        """Resolve a component to its instance, or raise 403 if not detailed."""
        instance = self._context.instances.get(self._find_or_404(collection, name))
        if not isinstance(instance, DetailsProtocol):
            raise HTTPException(status_code=403, detail="Component has no details")
        return instance

    def _get_chart(self, collection: str, name: str) -> ChartProtocol:
        """Resolve a component to its instance, or raise 403 if not chartable."""
        instance = self._context.instances.get(self._find_or_404(collection, name))
        if not isinstance(instance, ChartProtocol):
            raise HTTPException(status_code=403, detail="Component has no chart")
        return instance

    def _find_repo_or_404(self, repo_id: str) -> tuple[type, object, type]:
        """Resolve a repository id to (class, instance, entity class), or raise 404."""
        found = data.find_repository(self._context, repo_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        return found

    def _get_readable(self, repo_id: str) -> tuple[type, object, type]:
        """Resolve a repository id, or raise 403 if it is not readable."""
        repo_cls, instance, entity_cls = self._find_repo_or_404(repo_id)
        if not isinstance(instance, ReadableProtocol):
            raise HTTPException(status_code=403, detail="Repository is not readable")
        return repo_cls, instance, entity_cls

    def _get_writable(self, repo_id: str) -> tuple[type, object, type]:
        """Resolve a repository id, or raise 403 if it is not writable."""
        repo_cls, instance, entity_cls = self._find_repo_or_404(repo_id)
        if not isinstance(instance, WritableProtocol):
            raise HTTPException(status_code=403, detail="Repository is not writable")
        return repo_cls, instance, entity_cls

    def _get_streamable(self, repo_id: str) -> tuple[type, object, type]:
        """Resolve a repository id, or raise 403 if it is not streamable."""
        repo_cls, instance, entity_cls = self._find_repo_or_404(repo_id)
        if not isinstance(instance, StreamableProtocol):
            raise HTTPException(status_code=403, detail="Repository is not streamable")
        return repo_cls, instance, entity_cls

    def _get_data_view(self, repo_id: str) -> DataView:
        """Resolve a repository id to its ``data_view()``, or raise 403 if it has none."""
        _, instance, _ = self._find_repo_or_404(repo_id)
        view = data.resolve_view(instance, readable=isinstance(instance, ReadableProtocol))
        if view is None:
            raise HTTPException(status_code=403, detail="Repository has no data view")
        return view

    def _replace_document(self, repo_id: str, key: str, content: bytes) -> None:
        """Save the record matching ``key`` with ``content`` as its document file."""
        _, instance, entity_cls = self._get_writable(repo_id)
        if not isinstance(instance, ReadableProtocol):
            raise HTTPException(status_code=403, detail="Repository is not readable")
        view = self._get_data_view(repo_id)
        if not isinstance(view, DocumentView):
            raise HTTPException(status_code=403, detail="Repository has no document view")
        key_field = data.key_field_name(entity_cls)
        coerced_key = data.coerce_key(entity_cls, key_field, key)
        record = next((r for r in instance.all() if getattr(r, key_field) == coerced_key), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        if not isinstance(getattr(record, view.field), (bytes, bytearray)):
            raise HTTPException(status_code=409, detail="Record's document is not a file")
        instance.save(dataclasses.replace(record, **{view.field: content}))

    def _get_annotatable_view(self, repo_id: str) -> DataView:
        """Resolve a repository id's data view, or raise 404 if it can't be annotated."""
        view = self._get_data_view(repo_id)
        if not isinstance(view, (ImageView, DocumentView, VideoView, AudioView, *_LIST_VIEWS)):
            raise HTTPException(status_code=404, detail="Repository's view takes no annotations")
        return view

    def _get_classifiable_view(self, repo_id: str) -> DataView:
        """Resolve a repository id's data view, or raise 404 if its records take no class."""
        view = self._get_data_view(repo_id)
        if isinstance(view, (StreamingVideoView, StreamingAudioView)):
            raise HTTPException(status_code=404, detail="Repository has no stored records")
        return view

    def _load_annotations(self) -> dict:
        """Load the annotations file, or raise 500 if it exists but can't be read."""
        try:
            return annotations.load(self._annotations_path)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    def _get_streaming_view(self, repo_id: str) -> StreamingVideoView | StreamingAudioView:
        """Resolve a repository id's data view, or raise 403 if it isn't streaming."""
        view = self._get_data_view(repo_id)
        if not isinstance(view, (StreamingVideoView, StreamingAudioView)):
            raise HTTPException(status_code=403, detail="Repository has no streaming view")
        return view

    @staticmethod
    def _multipart_stream(entities: Iterator[object], field: str, content_type: str):
        """Wrap a stream of entities as a multipart byte stream.

        ``entities`` comes from ``Context.iter_stream()`` — one subscription
        to the repository's shared, already-running stream (see
        ``Context.start_stream()``). A client disconnect (browser tab
        closed, ``<img>`` removed) stops this generator being iterated,
        which in turn detaches the subscription — it does not stop the
        underlying stream, which keeps running for any other subscriber.
        """
        for entity in entities:
            chunk = getattr(entity, field)
            yield (
                (
                    f"--{_STREAM_BOUNDARY}\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Length: {len(chunk)}\r\n\r\n"
                ).encode()
                + chunk
                + b"\r\n"
            )

    async def _chat_events(self, messages: list[dict]) -> AsyncIterator[str]:
        """Newline-delimited JSON events for one chat turn — see ``ChatEngine.stream``."""
        async for event in self._chat.stream(messages):
            yield json.dumps(event) + "\n"

    @property
    def url(self) -> str:
        """The base URL the UI is served from."""
        return f"http://{self._host}:{self._port}"

    @property
    def local_url(self) -> str:
        """The base URL to reach the UI at from this machine, whatever it binds to."""
        return f"http://{local_host(self._host)}:{self._port}"

    def start(self) -> None:
        """Start serving in a background daemon thread. Returns immediately."""
        self._events.start()
        config = uvicorn.Config(
            HostCheck(self._app, self._host), host=self._host, port=self._port, log_level="warning"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the server to exit and wait for the background thread to finish."""
        # Ends the open event streams first, which shutdown would wait on.
        self._events.stop()
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._notebooks is not None:
            self._notebooks.stop()
