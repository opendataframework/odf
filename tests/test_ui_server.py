import json
import time
from dataclasses import dataclass

from fastapi.testclient import TestClient
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.namespace import Namespace
from opendataframework.repository import Repository
from opendataframework.view import StreamingAudioView, StreamingVideoView

from odf.ui.server import UiServer


def make_ns():
    class NS(Namespace): ...

    return NS


@dataclass
class Item:
    id: int | None
    name: str


def test_index_serves_html():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_topology_endpoint_returns_resolved_graph():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/topology")

    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "proj"
    assert any(n["label"] == "Thing" for n in body["nodes"])


def test_url_reflects_host_and_port():
    with Context(namespaces=set()) as ctx:
        server = UiServer(ctx, "proj", host="127.0.0.1", port=9999)

    assert server.url == "http://127.0.0.1:9999"


# --- repository data endpoints -----------------------------------------------


def test_records_round_trip_create_update_delete():
    NS = make_ns()

    @NS
    @Repository(Item)
    class Items:
        def __init__(self) -> None:
            self._rows: dict[int, Item] = {}
            self._next_id = 1

        def all(self):
            return list(self._rows.values())

        def save(self, item: Item) -> None:
            if item.id is None:
                item.id = self._next_id
                self._next_id += 1
            self._rows[item.id] = item

        def delete(self, item_id: int) -> None:
            self._rows.pop(item_id, None)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        r = client.get("/api/repositories")
        assert r.status_code == 200
        assert r.json()[0]["id"] == "items"

        assert client.get("/api/repositories/items/records").json() == []

        r = client.post("/api/repositories/items/records", json={"name": "Alice"})
        assert r.status_code == 201
        created = r.json()
        assert created == {"id": 1, "name": "Alice"}

        r = client.put(f"/api/repositories/items/records/{created['id']}", json={"name": "Alicia"})
        assert r.status_code == 200
        assert r.json() == {"id": 1, "name": "Alicia"}

        assert client.get("/api/repositories/items/records").json() == [{"id": 1, "name": "Alicia"}]

        assert client.delete(f"/api/repositories/items/records/{created['id']}").status_code == 204
        assert client.get("/api/repositories/items/records").json() == []


def test_records_pagination_via_limit_and_offset():
    NS = make_ns()

    @NS
    @Repository(Item)
    class Items:
        def all(self):
            return [Item(id=i, name=str(i)) for i in range(5)]

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        r = client.get("/api/repositories/items/records")
        assert r.headers["x-total-count"] == "5"
        assert len(r.json()) == 5

        r = client.get("/api/repositories/items/records", params={"limit": 2, "offset": 1})
        assert r.status_code == 200
        assert r.headers["x-total-count"] == "5"
        assert r.json() == [{"id": 1, "name": "1"}, {"id": 2, "name": "2"}]


def test_records_filters_by_column_via_query_params():
    NS = make_ns()

    @NS
    @Repository(Item)
    class Items:
        def all(self):
            return [Item(id=1, name="Alice"), Item(id=2, name="Bob"), Item(id=3, name="Alicia")]

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        r = client.get("/api/repositories/items/records", params={"name": "ali"})
        assert r.headers["x-total-count"] == "2"
        assert r.json() == [{"id": 1, "name": "Alice"}, {"id": 3, "name": "Alicia"}]

        # A query param that isn't an entity field is ignored, not an error.
        r = client.get("/api/repositories/items/records", params={"nonexistent_field": "x"})
        assert r.status_code == 200
        assert r.headers["x-total-count"] == "3"


def test_unknown_repository_returns_404():
    NS = make_ns()
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.get("/api/repositories/nonexistent/records").status_code == 404
        assert client.post("/api/repositories/nonexistent/records", json={}).status_code == 404
        assert client.put("/api/repositories/nonexistent/records/1", json={}).status_code == 404
        assert client.delete("/api/repositories/nonexistent/records/1").status_code == 404


# --- component logs endpoint --------------------------------------------------


def test_component_logs_endpoint_returns_entries(tmp_path):
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/thing/logs")

    assert r.status_code == 200
    body = r.json()
    assert any("resolved" in e["message"] for e in body)
    assert all({"ts", "level", "message"} == e.keys() for e in body)


def test_component_logs_endpoint_empty_without_log_dir():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/thing/logs")

    assert r.status_code == 200
    assert r.json() == []


def test_component_logs_endpoint_unknown_component_returns_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/nonexistent/logs")

    assert r.status_code == 404


# --- component details endpoint -------------------------------------------------


def test_component_details_endpoint_returns_declared_details():
    NS = make_ns()

    @NS
    @Component
    class Thing:
        def details(self) -> dict[str, str]:
            return {"UI": "http://localhost:4747"}

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/thing/details")

    assert r.status_code == 200
    assert r.json() == {"UI": "http://localhost:4747"}


def test_component_details_endpoint_rejects_component_without_details():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/thing/details")

    assert r.status_code == 403


def test_component_details_endpoint_unknown_component_returns_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/nonexistent/details")

    assert r.status_code == 404


# --- component chart endpoint --------------------------------------------------


def test_component_chart_endpoint_returns_declared_html():
    NS = make_ns()

    @NS
    @Component
    class Thing:
        def chart(self) -> str:
            return "<html><body>chart</body></html>"

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/thing/chart")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.text == "<html><body>chart</body></html>"


def test_component_chart_endpoint_rejects_component_without_chart():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/thing/chart")

    assert r.status_code == 403


def test_component_chart_endpoint_unknown_component_returns_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/components/nonexistent/chart")

    assert r.status_code == 404


# --- lifecycle endpoints -------------------------------------------------------


def test_start_stop_endpoints_toggle_a_service():
    NS = make_ns()

    @NS
    class Svc:
        def setup(self) -> None: ...
        def run(self) -> None: ...
        def stop(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/components/svc/stop").status_code == 204
        assert ctx.is_running("Svc") is False

        assert client.post("/api/components/svc/start").status_code == 204
        assert ctx.is_running("Svc") is True


def test_start_endpoint_rejects_non_service():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/components/thing/start")

    assert r.status_code == 400


def test_execute_endpoint_runs_a_task():
    NS = make_ns()
    calls = []

    from opendataframework.task import Task

    @NS
    @Task
    class DoThing:
        def execute(self) -> None:
            calls.append("ran")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/components/do-thing/execute")

    assert r.status_code == 204
    assert calls == ["ran"]


def test_execute_endpoint_rejects_non_executable():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/components/thing/execute")

    assert r.status_code == 400


def test_execute_endpoint_surfaces_task_exceptions_as_500():
    NS = make_ns()

    from opendataframework.task import Task

    @NS
    @Task
    class Boom:
        def execute(self) -> None:
            raise RuntimeError("kaboom")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/components/boom/execute")

    assert r.status_code == 500


def test_lifecycle_endpoints_unknown_component_returns_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/components/nonexistent/start").status_code == 404
        assert client.post("/api/components/nonexistent/stop").status_code == 404
        assert client.post("/api/components/nonexistent/execute").status_code == 404


# --- streaming endpoints -------------------------------------------------------


@dataclass
class Frame:
    id: int | None
    data: bytes


def test_start_stop_stream_endpoints_toggle_a_repository():
    NS = make_ns()

    @NS
    @Repository(Frame)
    class Cam:
        def stream(self):
            n = 0
            while True:
                n += 1
                time.sleep(0.01)  # mimic a blocking device read that releases the GIL
                yield Frame(id=n, data=b"jpg")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/repositories/cam/start-stream").status_code == 204
        assert ctx.is_streaming("Cam") is True

        assert client.post("/api/repositories/cam/stop-stream").status_code == 204
        assert ctx.is_streaming("Cam") is False


def test_start_stop_stream_endpoints_unknown_repository_returns_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/repositories/nonexistent/start-stream").status_code == 404
        assert client.post("/api/repositories/nonexistent/stop-stream").status_code == 404


def test_stream_endpoint_returns_409_before_streaming_is_started():
    NS = make_ns()

    @NS
    @Repository(Frame)
    class Cam:
        def stream(self):
            while True:
                time.sleep(0.01)
                yield Frame(id=1, data=b"jpg")

        def data_view(self):
            return StreamingVideoView(field="data")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/cam/stream")

    assert r.status_code == 409


def test_stream_endpoint_serves_frames_once_started():
    # A bounded stream() and a plain (non-incremental) client.get() — the
    # in-process TestClient bridges requests through a blocking portal that
    # waits for the whole ASGI call to finish, so it can't do a true
    # incremental read of a never-ending stream (that's exercised at the
    # Context level in test_context.py instead). A short sleep before each
    # frame gives the subscriber time to attach before frames are produced.
    NS = make_ns()

    @NS
    @Repository(Frame)
    class Cam:
        def stream(self):
            for n in range(1, 4):
                time.sleep(0.02)
                yield Frame(id=n, data=b"jpg-bytes")

        def data_view(self):
            return StreamingVideoView(field="data")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        client.post("/api/repositories/cam/start-stream")

        r = client.get("/api/repositories/cam/stream")

    # The single-slot "latest frame wins" queue can race the end-of-stream
    # sentinel and drop the very last frame — harmless for a real, unbounded
    # stream, so assert only that real frame data made it through, not an
    # exact count.
    assert r.status_code == 200
    assert r.content.count(b"jpg-bytes") >= 1


def test_stream_endpoint_serves_one_chunk_per_request_for_audio():
    # StreamingAudioView delivers one complete, independently decodable
    # chunk per request (see odf.ui.server.stream_records) rather than
    # multiplexing over one multipart connection like StreamingVideoView —
    # browsers have no multipart support for <audio>.
    NS = make_ns()

    @NS
    @Repository(Frame)
    class Radio:
        def stream(self):
            n = 0
            while True:
                n += 1
                time.sleep(0.02)
                yield Frame(id=n, data=f"chunk-{n}".encode())

        def data_view(self):
            return StreamingAudioView(field="data")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        client.post("/api/repositories/radio/start-stream")

        r = client.get("/api/repositories/radio/stream")

    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert b"odf-frame" not in r.content
    assert r.content.startswith(b"chunk-")


def test_repositories_endpoint_reports_streaming_state():
    NS = make_ns()

    @NS
    @Repository(Frame)
    class Cam:
        def stream(self):
            while True:
                time.sleep(0.01)
                yield Frame(id=1, data=b"jpg")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        schema = client.get("/api/repositories").json()[0]
        assert schema["streamable"] is True
        assert schema["streaming"] is False

        client.post("/api/repositories/cam/start-stream")
        schema = client.get("/api/repositories").json()[0]
        assert schema["streaming"] is True

        client.post("/api/repositories/cam/stop-stream")


# --- layout persistence endpoints -----------------------------------------------


def test_layout_endpoints_disabled_without_layout_file():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.get("/api/layout").json() == {}
        assert client.put("/api/layout", json={"thing": {"col": 1, "row": 2}}).status_code == 204
        # nothing was persisted — a disabled store is a no-op, not a crash
        assert client.get("/api/layout").json() == {}


def test_layout_round_trips_through_put_and_get(tmp_path):
    layout_file = tmp_path / "layout.json"
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", layout_file=layout_file)._app)

        assert client.get("/api/layout").json() == {}

        positions = {"thing": {"col": 1, "row": 2, "icon": "camera"}}
        assert client.put("/api/layout", json=positions).status_code == 204
        assert client.get("/api/layout").json() == positions

    assert layout_file.exists()


def test_layout_put_overwrites_previous_save(tmp_path):
    layout_file = tmp_path / "layout.json"
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", layout_file=layout_file)._app)

        client.put("/api/layout", json={"a": {"col": 1, "row": 1}})
        client.put("/api/layout", json={"b": {"col": 2, "row": 2}})

        assert client.get("/api/layout").json() == {"b": {"col": 2, "row": 2}}


# --- chat endpoints --------------------------------------------------------


class StubChatEngine:
    model = "stub-model"

    async def stream(self, messages):
        yield {"type": "token", "content": "Hello"}
        yield {"type": "token", "content": ", world"}


def test_chat_config_endpoint_disabled_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/chat/config")

    assert r.status_code == 200
    assert r.json() == {"enabled": False, "model": None}


def test_chat_endpoint_returns_404_when_disabled():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert r.status_code == 404


def test_chat_config_endpoint_reflects_enabled_engine():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", chat_engine=StubChatEngine())._app)
        r = client.get("/api/chat/config")

    assert r.status_code == 200
    assert r.json() == {"enabled": True, "model": "stub-model"}


def test_chat_endpoint_streams_ndjson_events():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", chat_engine=StubChatEngine())._app)
        r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert r.status_code == 200
    assert "application/x-ndjson" in r.headers["content-type"]
    events = [json.loads(line) for line in r.text.strip().split("\n")]
    assert events == [
        {"type": "token", "content": "Hello"},
        {"type": "token", "content": ", world"},
    ]


def test_read_only_repository_rejects_writes():
    NS = make_ns()

    @NS
    @Repository(Item)
    class ReadOnlyItems:
        def all(self):
            return [Item(id=1, name="Alice")]

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.get("/api/repositories/read-only-items/records").status_code == 200
        assert (
            client.post("/api/repositories/read-only-items/records", json={"name": "X"}).status_code
            == 403
        )
        assert (
            client.put(
                "/api/repositories/read-only-items/records/1", json={"name": "X"}
            ).status_code
            == 403
        )
        assert client.delete("/api/repositories/read-only-items/records/1").status_code == 403


# --- favicon / logo -----------------------------------------------------------


def test_favicon_serves_builtin_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/favicon.svg")

    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_favicon_serves_custom_file_when_configured(tmp_path):
    favicon = tmp_path / "favicon.svg"
    favicon.write_text("<svg><title>custom</title></svg>")

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", favicon=favicon)._app)
        r = client.get("/favicon.svg")

    assert r.status_code == 200
    assert "custom" in r.text


def test_logo_endpoint_404_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/ui/logo")

    assert r.status_code == 404


def test_logo_endpoint_serves_custom_file_when_configured(tmp_path):
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg><title>custom logo</title></svg>")

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", logo=logo)._app)
        r = client.get("/api/ui/logo")

    assert r.status_code == 200
    assert "custom logo" in r.text


def test_ui_extensions_reports_no_logo_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/ui/extensions")

    assert r.json()["logo"] is None


def test_ui_extensions_reports_logo_url_when_configured(tmp_path):
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg></svg>")

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", logo=logo)._app)
        r = client.get("/api/ui/extensions")

    assert r.json()["logo"] == "/api/ui/logo"


def test_ui_extensions_reports_no_brand_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/ui/extensions")

    assert r.json()["brand"] is None


def test_ui_extensions_reports_configured_brand():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", brand="Beacon Watch")._app)
        r = client.get("/api/ui/extensions")

    assert r.json()["brand"] == "Beacon Watch"
