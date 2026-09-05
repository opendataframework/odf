"""Dev UI server: serves the topology visualization over HTTP.

Not a DI-managed ``Service`` — it introspects the container from the
outside, so it is constructed and driven directly by ``Server.start(ui=True)``
/ ``Server.stop()``, after the ``Context`` has already resolved.
"""

import json
import threading
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
except ImportError as exc:
    raise ImportError(
        "server.start(ui=True) requires the 'ui' extra. Install with: pip install odf[ui]"
    ) from exc

from opendataframework.component import ChartProtocol, DetailsProtocol
from opendataframework.context import Context
from opendataframework.repository import ReadableProtocol, StreamableProtocol, WritableProtocol
from opendataframework.utils import kebab
from opendataframework.view import (
    AudioView,
    DataView,
    ImageView,
    StreamingAudioView,
    StreamingVideoView,
    VideoView,
)

from odf.ui import data, layout
from odf.ui.topology import build_topology

if TYPE_CHECKING:
    from odf.chat.engine import ChatEngine

_STREAM_BOUNDARY = "odf-frame"

_MEDIA_CONTENT_TYPES: dict[type, str] = {
    ImageView: "image/jpeg",
    VideoView: "video/mp4",
    # WAV rather than MP3 — the demo's only AudioView repository (VoiceMemos)
    # synthesizes clips with the stdlib `wave` module to avoid an encoding
    # dependency; nothing else uses plain AudioView today.
    AudioView: "audio/wav",
}

_STATIC_DIR = Path(__file__).parent / "static"


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
    """

    def __init__(
        self,
        context: Context,
        project: str,
        host: str = "127.0.0.1",
        port: int = 4747,
        layout_file: str | Path | None = None,
        chat_engine: ChatEngine | None = None,
        icon_scripts: list[Path] | None = None,
        colors: dict[str, str] | None = None,
        favicon: str | Path | None = None,
        logo: str | Path | None = None,
        brand: str | None = None,
    ) -> None:
        """Build the FastAPI app and register every route (see class docstring for args)."""
        self._context = context
        self._project = project
        self._host = host
        self._port = port
        self._layout_path = Path(layout_file) if layout_file is not None else None
        self._chat = chat_engine
        self._icon_scripts = list(icon_scripts) if icon_scripts is not None else []
        self._colors = dict(colors) if colors is not None else {}
        self._favicon = Path(favicon) if favicon is not None else None
        self._logo = Path(logo) if logo is not None else None
        self._brand = brand
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

        app = FastAPI(title="ODF Topology", docs_url=None, redoc_url=None)

        @app.get("/api/topology")
        def topology() -> dict:
            """Return the current node/edge graph for the topology view."""
            return build_topology(self._context, self._project)

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
            """List registered icon scripts, extra named colors, the custom logo, and brand."""
            return {
                "iconScripts": [
                    f"/api/ui/icon-scripts/{i}" for i in range(len(self._icon_scripts))
                ],
                "colors": self._colors,
                "logo": "/api/ui/logo" if self._logo is not None else None,
                "brand": self._brand,
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
            records, total = data.list_records(
                instance, entity_cls, limit=limit, offset=offset, filters=filters
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
            self._context.start_stream(repo_cls.__name__)

        @app.post("/api/repositories/{repo_id}/stop-stream", status_code=204)
        def stop_stream(repo_id: str) -> None:
            """Stop a streamable repository's shared background stream."""
            repo_cls, _, _ = self._get_streamable(repo_id)
            self._context.stop_stream(repo_cls.__name__)

        @app.get("/api/repositories/{repo_id}/stream")
        def stream_records(repo_id: str) -> Response:
            """Subscribe to a running stream and return its next chunk(s)."""
            repo_cls, _, _ = self._get_streamable(repo_id)
            view = self._get_streaming_view(repo_id)
            try:
                entities = self._context.iter_stream(repo_cls.__name__)
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
        def record_media(repo_id: str, key: str) -> Response:
            """Return the raw media bytes (image/video/audio) for one record."""
            _, instance, entity_cls = self._get_readable(repo_id)
            view = self._get_data_view(repo_id)
            content_type = _MEDIA_CONTENT_TYPES.get(type(view))
            if content_type is None:
                raise HTTPException(status_code=403, detail="Repository has no media view")
            key_field = data.key_field_name(entity_cls)
            coerced_key = data.coerce_key(entity_cls, key_field, key)
            record = next((r for r in instance.all() if getattr(r, key_field) == coerced_key), None)
            if record is None:
                raise HTTPException(status_code=404, detail="Record not found")
            return Response(content=getattr(record, view.field), media_type=content_type)

        @app.get("/api/components/{component_id}/logs")
        def component_logs(component_id: str) -> list[dict]:
            """Return a component's tailed log records."""
            cls = self._find_class_or_404(component_id)
            return self._context.tail_logs(cls.__name__)

        @app.get("/api/components/{component_id}/details")
        def component_details(component_id: str) -> dict[str, str]:
            """Return a component's ``DetailsProtocol`` key/value details."""
            return self._get_details(component_id).details()

        @app.get("/api/components/{component_id}/chart", response_class=HTMLResponse)
        def component_chart(component_id: str) -> str:
            """Return a component's ``ChartProtocol`` HTML chart."""
            return self._get_chart(component_id).chart()

        @app.post("/api/components/{component_id}/start", status_code=204)
        def start_component(component_id: str) -> None:
            """Start a component through the context."""
            cls = self._find_class_or_404(component_id)
            try:
                self._context.start(cls.__name__)
            except TypeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/api/components/{component_id}/stop", status_code=204)
        def stop_component(component_id: str) -> None:
            """Stop a component through the context."""
            cls = self._find_class_or_404(component_id)
            try:
                self._context.stop(cls.__name__)
            except TypeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/api/components/{component_id}/execute", status_code=204)
        def execute_component(component_id: str) -> None:
            """Execute a component's task/pipeline through the context."""
            cls = self._find_class_or_404(component_id)
            try:
                self._context.execute(cls.__name__)
            except TypeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

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

        @app.get("/")
        def index() -> FileResponse:
            """Serve the UI's ``index.html``."""
            return FileResponse(_STATIC_DIR / "index.html")

        @app.get("/favicon.svg")
        def favicon() -> FileResponse:
            """Serve the UI's favicon — the project's custom one, if configured."""
            path = self._favicon if self._favicon is not None else _STATIC_DIR / "favicon.svg"
            return FileResponse(path, media_type="image/svg+xml")

        self._app = app

    def _find_class_or_404(self, component_id: str) -> type:
        """Resolve a kebab-case component id to its class, or raise 404."""
        for cls in self._context.instances:
            if kebab(cls.__name__) == component_id:
                return cls
        raise HTTPException(status_code=404, detail="Component not found")

    def _get_details(self, component_id: str) -> DetailsProtocol:
        """Resolve a component id to its instance, or raise 403 if not detailed."""
        cls = self._find_class_or_404(component_id)
        instance = self._context.instances[cls]
        if not isinstance(instance, DetailsProtocol):
            raise HTTPException(status_code=403, detail="Component has no details")
        return instance

    def _get_chart(self, component_id: str) -> ChartProtocol:
        """Resolve a component id to its instance, or raise 403 if not chartable."""
        cls = self._find_class_or_404(component_id)
        instance = self._context.instances[cls]
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

    def start(self) -> None:
        """Start serving in a background daemon thread. Returns immediately."""
        config = uvicorn.Config(self._app, host=self._host, port=self._port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the server to exit and wait for the background thread to finish."""
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
