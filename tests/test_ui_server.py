import json
import re
import threading
import time
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.entity import Entity
from opendataframework.function import Function
from opendataframework.namespace import Namespace
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.view import (
    AudioView,
    ContentMetadata,
    DocumentView,
    ImageView,
    LocationView,
    StreamingAudioView,
    StreamingVideoView,
    TimeseriesView,
    VideoView,
)

from odf.ui import themes
from odf.ui.server import UiServer


def make_ns():
    class NS(Namespace): ...

    return NS


# Named apart from the `Item` entity every `odf init` template scaffolds, which
# tests/test_cli.py imports into the same process-wide registry.
@Entity(name="server-item")
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


def test_topology_endpoint_applies_the_configured_view():
    from odf.ui.topology import TopologyView

    NS = make_ns()

    @NS
    @Component
    class Plumbing: ...

    @NS
    @Component
    class Front:
        def __init__(self, plumbing: Plumbing) -> None: ...

    view = TopologyView.from_config({"components": ["Front"], "connections": False})
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", topology=view)._app)
        body = client.get("/api/topology").json()

    assert [n["id"] for n in body["nodes"]] == ["n-s.front"]
    assert body["edges"] == []


def test_topology_endpoint_moves_nodes_off_saved_cells(tmp_path):
    NS = make_ns()

    @NS
    @Component
    class Aaa: ...

    @NS
    @Component
    class Bbb: ...

    layout_file = tmp_path / "layout.json"
    layout_file.write_text(json.dumps({"n-s.bbb": {"col": 0, "row": 0}, "_grid": {"nw": 1}}))
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", layout_file=layout_file)._app)
        nodes = client.get("/api/topology").json()["nodes"]

    assert {n["id"]: (n["col"], n["row"]) for n in nodes} == {"n-s.bbb": (0, 0), "n-s.aaa": (0, 1)}


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
        assert r.json()[0]["id"] == "n-s.items"
        assert r.json()[0]["href"] == "/api/repositories/items"

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


def test_function_logs_endpoint_returns_its_calls(tmp_path):
    NS = make_ns()

    @NS
    @Function
    def double(value: int) -> int:
        return value * 2

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        ctx.call(ctx.key(double), value=2)
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/functions/double/logs")

    assert r.status_code == 200
    assert any("completed" in e["message"] for e in r.json())


def test_function_has_no_details_or_chart():
    NS = make_ns()

    @NS
    @Function
    def double(value: int) -> int:
        return value * 2

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        details = client.get("/api/functions/double/details")
        chart = client.get("/api/functions/double/chart")

    assert details.status_code == 403
    assert chart.status_code == 403


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
    @Service
    class Svc:
        def setup(self) -> None: ...
        def run(self) -> None: ...
        def stop(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/services/svc/stop").status_code == 204
        assert ctx.is_running(ctx.key(Svc)) is False

        assert client.post("/api/services/svc/start").status_code == 204
        assert ctx.is_running(ctx.key(Svc)) is True


def test_start_endpoint_only_exists_for_services():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/components/thing/start").status_code == 404
        assert client.post("/api/services/thing/start").status_code == 404


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
        r = client.post("/api/tasks/do-thing/execute")

    assert r.status_code == 204
    assert calls == ["ran"]


def test_execute_endpoint_only_exists_for_tasks_and_pipelines():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        assert client.post("/api/components/thing/execute").status_code == 404
        assert client.post("/api/tasks/thing/execute").status_code == 404


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
        r = client.post("/api/tasks/boom/execute")

    assert r.status_code == 500


def test_events_endpoint_streams_calls_as_server_sent_events():
    NS = make_ns()

    from opendataframework.task import Task

    @NS
    @Task
    class DoThing:
        def execute(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        server = UiServer(ctx, "proj")
        server._events.start()

        # The test client returns a response only once its body ends, so the
        # call is made, and the stream ended, from another thread.
        def run():
            deadline = time.monotonic() + 5
            while not server._events._clients and time.monotonic() < deadline:
                time.sleep(0.01)
            ctx.execute(ctx.key(DoThing))
            server._events.stop()

        thread = threading.Thread(target=run)
        thread.start()
        r = TestClient(server._app).get("/api/events")
        thread.join()

    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["x-accel-buffering"] == "no"
    frames = [
        json.loads(line[len("data: ") :])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [(f["key"], f["state"]) for f in frames] == [
        (ctx.key(DoThing), "started"),
        (ctx.key(DoThing), "completed"),
    ]


def _librarian(NS, calls):
    from opendataframework.agent import Agent

    @NS
    @Agent
    class Librarian:
        def invoke(self, question: str, limit: int = 3, *, exact: bool = False) -> dict:
            calls.append((question, limit, exact))
            return {"question": question, "limit": limit, "exact": exact}

    return Librarian


def test_parameters_endpoint_returns_the_invoke_schema():
    NS = make_ns()
    _librarian(NS, [])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/agents/librarian/parameters")

    assert r.status_code == 200
    schema = r.json()
    assert list(schema["properties"]) == ["question", "limit", "exact"]
    assert schema["properties"]["limit"] == {"default": 3, "title": "Limit", "type": "integer"}
    assert schema["required"] == ["question"]


def test_invoke_endpoint_calls_the_agent_with_coerced_arguments():
    NS = make_ns()
    calls = []
    _librarian(NS, calls)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/agents/librarian/invoke", json={"question": "Dune?", "limit": "2"})

    assert r.status_code == 200
    assert r.json() == {"result": {"question": "Dune?", "limit": 2, "exact": False}}
    assert calls == [("Dune?", 2, False)]


def test_invoke_endpoint_logs_the_call(tmp_path):
    NS = make_ns()
    _librarian(NS, [])

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        client.post("/api/agents/librarian/invoke", json={"question": "Dune?"})
        logs = client.get("/api/agents/librarian/logs").json()

    assert any("invoke() completed" in entry["message"] for entry in logs)


def test_invoke_endpoint_rejects_a_missing_argument_with_422():
    NS = make_ns()
    calls = []
    _librarian(NS, calls)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/agents/librarian/invoke", json={})

    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["question"]
    assert calls == []


def test_invoke_endpoints_reject_a_component_that_is_not_an_agent():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.get("/api/components/thing/parameters").status_code == 404
        assert client.post("/api/components/thing/invoke", json={}).status_code == 404
        assert client.get("/api/agents/thing/parameters").status_code == 404
        assert client.post("/api/agents/thing/invoke", json={}).status_code == 404


def test_invoke_endpoint_surfaces_agent_exceptions_as_500():
    NS = make_ns()

    from opendataframework.agent import Agent

    @NS
    @Agent
    class Grumpy:
        def invoke(self) -> None:
            raise RuntimeError("not today")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/agents/grumpy/invoke", json={})

    assert r.status_code == 500
    assert r.json()["detail"] == "not today"


def test_invoke_endpoint_falls_back_to_str_for_an_unencodable_result():
    NS = make_ns()

    from opendataframework.agent import Agent

    class Opaque:
        __slots__ = ()

        def __str__(self) -> str:
            return "opaque"

    @NS
    @Agent
    class Odd:
        def invoke(self) -> Opaque:
            return Opaque()

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/agents/odd/invoke", json={})

    assert r.json() == {"result": "opaque"}


def _scale(NS, calls):
    @NS
    @Component
    class Units:
        factor = 10

    @NS
    @Function
    def scale(value: int, units: Units, *, label: str = "x") -> dict:
        """Scale a value by the configured factor.

        Longer details.
        """
        calls.append((value, label))
        return {"value": value * units.factor, "label": label}

    return scale


def test_parameters_endpoint_leaves_out_a_function_s_injected_parameters():
    NS = make_ns()
    _scale(NS, [])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/functions/scale/parameters")

    assert r.status_code == 200
    schema = r.json()
    assert list(schema["properties"]) == ["value", "label"]
    assert schema["required"] == ["value"]


def test_call_endpoint_calls_the_function_with_coerced_arguments(tmp_path):
    NS = make_ns()
    calls = []
    _scale(NS, calls)

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/functions/scale/call", json={"value": "4"})
        logs = client.get("/api/functions/scale/logs").json()

    assert r.status_code == 200
    assert r.json() == {"result": {"value": 40, "label": "x"}}
    assert calls == [(4, "x")]
    assert any("completed" in entry["message"] for entry in logs)


def test_call_endpoint_rejects_a_missing_argument_with_422():
    NS = make_ns()
    calls = []
    _scale(NS, calls)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.post("/api/functions/scale/call", json={})

    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["value"]
    assert calls == []


def test_each_kind_is_called_only_by_its_own_verb():
    NS = make_ns()
    _scale(NS, [])
    _librarian(NS, [])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/functions/scale/invoke", json={}).status_code == 404
        assert client.post("/api/agents/librarian/call", json={}).status_code == 404
        assert client.get("/api/functions/librarian/parameters").status_code == 404
        assert client.get("/api/agents/scale/parameters").status_code == 404


def test_lifecycle_endpoints_unknown_component_returns_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.post("/api/services/nonexistent/start").status_code == 404
        assert client.post("/api/services/nonexistent/stop").status_code == 404
        assert client.post("/api/tasks/nonexistent/execute").status_code == 404
        assert client.get("/api/bogus/nonexistent/logs").status_code == 404


# --- streaming endpoints -------------------------------------------------------


@Entity
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
        assert ctx.is_streaming(ctx.key(Cam)) is True

        assert client.post("/api/repositories/cam/stop-stream").status_code == 204
        assert ctx.is_streaming(ctx.key(Cam)) is False


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


@Entity
@dataclass
class Photo:
    name: str
    image: bytes | None


def photos_namespace(photos):
    """A namespace holding a ``Photos`` repository of ``photos`` with an ``ImageView``."""
    NS = make_ns()

    @NS
    @Repository(Photo)
    class Photos:
        def all(self):
            return photos

        def data_view(self):
            return ImageView(field="image")

    return NS


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"GIF89arest", "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBPrest", "image/webp"),
        (b"\x00\x00\x00\x18ftypheicrest", "image/heic"),
        (b"\x00\x00\x00\x18ftypavifrest", "image/avif"),
        (b"unrecognised", "image/jpeg"),
    ],
)
def test_record_media_serves_an_image_with_its_detected_type(content, content_type):
    NS = photos_namespace([Photo(name="a", image=content)])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/photos/records/a/media")

    assert r.status_code == 200
    assert r.headers["content-type"] == content_type
    assert r.content == content


@Entity
@dataclass
class Clip:
    name: str
    clip: bytes


def clips_namespace(clips, view):
    """A namespace holding a ``Clips`` repository of ``clips`` with ``view``."""
    NS = make_ns()

    @NS
    @Repository(Clip)
    class Clips:
        def all(self):
            return clips

        def data_view(self):
            return view

    return NS


@pytest.mark.parametrize(
    ("view", "content", "content_type"),
    [
        (VideoView(field="clip"), b"\x00\x00\x00\x18ftypisomrest", "video/mp4"),
        (VideoView(field="clip"), b"\x1a\x45\xdf\xa3rest", "video/webm"),
        (VideoView(field="clip"), b"unrecognised", "video/mp4"),
        (AudioView(field="clip"), b"RIFF\x00\x00\x00\x00WAVErest", "audio/wav"),
        (AudioView(field="clip"), b"ID3\x04rest", "audio/mpeg"),
        (AudioView(field="clip"), b"OggS\x00rest", "audio/ogg"),
        (AudioView(field="clip"), b"unrecognised", "audio/wav"),
    ],
)
def test_record_media_serves_a_clip_with_its_detected_type(view, content, content_type):
    NS = clips_namespace([Clip(name="a", clip=content)], view)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/clips/records/a/media")

    assert r.status_code == 200
    assert r.headers["content-type"] == content_type
    assert r.headers["accept-ranges"] == "bytes"
    assert r.content == content


@pytest.mark.parametrize(
    ("range_header", "content_range", "body"),
    [
        ("bytes=2-5", "bytes 2-5/10", b"2345"),
        ("bytes=4-", "bytes 4-9/10", b"456789"),
        ("bytes=-3", "bytes 7-9/10", b"789"),
    ],
)
def test_record_media_serves_a_requested_byte_range(range_header, content_range, body):
    NS = clips_namespace([Clip(name="a", clip=b"0123456789")], VideoView(field="clip"))

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/clips/records/a/media", headers={"Range": range_header})

    assert r.status_code == 206
    assert r.headers["content-range"] == content_range
    assert r.headers["content-type"] == "video/mp4"
    assert r.content == body


def test_record_media_returns_416_for_a_range_past_the_end():
    NS = clips_namespace([Clip(name="a", clip=b"0123456789")], AudioView(field="clip"))

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/clips/records/a/media", headers={"Range": "bytes=10-"})

    assert r.status_code == 416
    assert r.headers["content-range"] == "bytes */10"


def test_record_media_resolves_a_url_encoded_key():
    NS = photos_namespace([Photo(name="front door #1.jpg", image=b"\xff\xd8\xffjpg")])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/photos/records/front%20door%20%231.jpg/media")

    assert r.status_code == 200
    assert r.content == b"\xff\xd8\xffjpg"


def test_record_media_returns_404_for_a_missing_record_or_missing_bytes():
    NS = photos_namespace([Photo(name="empty", image=None)])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        unknown = client.get("/api/repositories/photos/records/nope/media")
        no_bytes = client.get("/api/repositories/photos/records/empty/media")

    assert unknown.status_code == 404
    assert no_bytes.status_code == 404


@Entity
@dataclass
class Paper:
    name: str
    body: bytes | str | dict


def papers_namespace(papers):
    """A namespace holding a ``Papers`` repository of ``papers`` with a ``DocumentView``."""
    NS = make_ns()

    @NS
    @Repository(Paper)
    class Papers:
        def all(self):
            return papers

        def data_view(self):
            return DocumentView(field="body")

    return NS


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"%PDF-1.7\nrest", "application/pdf"),
        (b"Receipt #102\n", "text/plain; charset=utf-8"),
        (b"<script>alert(1)</script>", "text/plain; charset=utf-8"),
        (b"PK\x03\x04\x00rest", "application/octet-stream"),
    ],
)
def test_record_media_serves_a_document_with_its_detected_type(content, content_type):
    NS = papers_namespace([Paper(name="a", body=content)])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/papers/records/a/media")

    assert r.status_code == 200
    assert r.headers["content-type"] == content_type
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.content == content


def test_record_media_serves_a_requested_byte_range_of_a_document():
    NS = papers_namespace([Paper(name="a", body=b"0123456789")])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/papers/records/a/media", headers={"Range": "bytes=2-5"})

    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 2-5/10"
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.content == b"2345"


def test_record_media_returns_404_for_a_document_held_inline():
    NS = papers_namespace([Paper(name="json", body={"total": 1}), Paper(name="text", body="hi")])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        as_json = client.get("/api/repositories/papers/records/json/media")
        as_text = client.get("/api/repositories/papers/records/text/media")
        records = client.get("/api/repositories/papers/records").json()

    assert as_json.status_code == 404
    assert as_text.status_code == 404
    assert [r["body"] for r in records] == [{"total": 1}, "hi"]


def writable_papers_namespace(papers):
    """Like ``papers_namespace``, with ``save()`` replacing the paper of the same name."""
    NS = make_ns()

    @NS
    @Repository(Paper)
    class Papers:
        def all(self):
            return list(papers)

        def save(self, paper):
            papers[:] = [paper if p.name == paper.name else p for p in papers]

        def delete(self, name):
            papers[:] = [p for p in papers if p.name != name]

        def data_view(self):
            return DocumentView(field="body")

    return NS


def test_put_record_media_saves_a_document_file_through_the_repository():
    papers = [Paper(name="a", body=b"old"), Paper(name="b", body=b"other")]
    NS = writable_papers_namespace(papers)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.put("/api/repositories/papers/records/a/media", content=b'{"cells": []}')
        served = client.get("/api/repositories/papers/records/a/media")

    assert r.status_code == 204
    assert papers == [Paper(name="a", body=b'{"cells": []}'), Paper(name="b", body=b"other")]
    assert served.content == b'{"cells": []}'


def test_put_record_media_refuses_a_document_held_inline_or_missing():
    papers = [Paper(name="text", body="hi")]
    NS = writable_papers_namespace(papers)

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        inline = client.put("/api/repositories/papers/records/text/media", content=b"x")
        missing = client.put("/api/repositories/papers/records/nope/media", content=b"x")

    assert inline.status_code == 409
    assert missing.status_code == 404
    assert papers == [Paper(name="text", body="hi")]


def test_put_record_media_refuses_a_read_only_or_non_document_repository():
    read_only = papers_namespace([Paper(name="a", body=b"old")])
    NS = make_ns()

    @NS
    @Repository(Photo)
    class Photos:
        def all(self):
            return [Photo(name="a", image=b"\xff\xd8\xff")]

        def save(self, photo): ...

        def delete(self, name): ...

        def data_view(self):
            return ImageView(field="image")

    with Context(namespaces={read_only, NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        paper = client.put("/api/repositories/papers/records/a/media", content=b"x")
        photo = client.put("/api/repositories/photos/records/a/media", content=b"x")

    assert paper.status_code == 403
    assert photo.status_code == 403


def test_notebook_editing_is_off_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        extensions = client.get("/api/ui/extensions").json()
        session = client.post("/api/notebooks/session")

    assert extensions["notebooks"] is False
    assert session.status_code == 404


def test_notebook_session_reports_a_jupyter_that_fails_to_start(monkeypatch):
    from odf.ui import notebooks

    def fail(self):
        raise RuntimeError("Jupyter exited with code 1 while starting")

    monkeypatch.setattr(notebooks.NotebookServer, "start", fail)
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", notebooks=True)._app)
        extensions = client.get("/api/ui/extensions").json()
        session = client.post("/api/notebooks/session")

    assert extensions["notebooks"] is True
    assert session.status_code == 503
    assert "code 1" in session.json()["detail"]


def described_papers_namespace(papers, metadata):
    """A ``Papers`` repository like ``papers_namespace``'s, declaring ``metadata`` per name."""
    NS = make_ns()

    @NS
    @Repository(Paper)
    class Papers:
        def all(self):
            return papers

        def data_view(self):
            return DocumentView(field="body")

        def content_metadata(self, paper):
            return metadata.get(paper.name, ContentMetadata())

    return NS


@pytest.mark.parametrize(
    ("content", "declared", "content_type"),
    [
        (b"a,b\n1,2\n", "text/csv", "text/plain; charset=utf-8"),
        (b"<script>alert(1)</script>", "text/html", "text/plain; charset=utf-8"),
        (b"%PDF-1.7\nrest", "application/zip", "application/octet-stream"),
        (b"%PDF-1.7\nrest", None, "application/pdf"),
    ],
)
def test_record_media_takes_a_declared_document_type_within_the_document_rule(
    content, declared, content_type
):
    NS = described_papers_namespace(
        [Paper(name="a", body=content)], {"a": ContentMetadata(content_type=declared)}
    )

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/papers/records/a/media")

    assert r.headers["content-type"] == content_type
    assert r.headers["x-content-type-options"] == "nosniff"


def test_record_media_takes_a_declared_image_type_and_names_the_content():
    NS = make_ns()

    @NS
    @Repository(Photo)
    class Photos:
        def all(self):
            return [Photo(name="a", image=b"\x00\x00\x01\x00icon")]

        def data_view(self):
            return ImageView(field="image")

        def content_metadata(self, photo):
            return ContentMetadata(filename=f"scans/{photo.name}.ico", content_type="image/x-icon")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        whole = client.get("/api/repositories/photos/records/a/media")
        part = client.get(
            "/api/repositories/photos/records/a/media", headers={"Range": "bytes=0-1"}
        )

    for r in (whole, part):
        assert r.headers["content-type"] == "image/x-icon"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert (
            r.headers["content-disposition"] == "inline; filename=\"a.ico\"; filename*=UTF-8''a.ico"
        )
    assert part.status_code == 206


def test_record_media_names_the_content_on_a_range_past_the_end():
    NS = described_papers_namespace(
        [Paper(name="a", body=b"0123456789")], {"a": ContentMetadata(filename="a.txt")}
    )

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/papers/records/a/media", headers={"Range": "bytes=99-"})

    assert r.status_code == 416
    assert r.headers["content-range"] == "bytes */10"
    assert r.headers["content-disposition"] == "inline; filename=\"a.txt\"; filename*=UTF-8''a.txt"


def test_record_media_sends_no_content_disposition_without_a_filename():
    NS = described_papers_namespace(
        [Paper(name="a", body=b"text")], {"a": ContentMetadata(content_type="text/plain")}
    )

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/papers/records/a/media")

    assert "content-disposition" not in r.headers


def test_records_carry_declared_content_metadata_for_a_media_view():
    NS = described_papers_namespace(
        [Paper(name="a", body=b"%PDF-1.7"), Paper(name="b", body="inline")],
        {"a": ContentMetadata(filename="a.pdf", content_type="application/pdf")},
    )

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        records = client.get("/api/repositories/papers/records").json()

    assert records == [
        {
            "name": "a",
            "body": None,
            "$content": {"filename": "a.pdf", "content_type": "application/pdf"},
        },
        {"name": "b", "body": "inline"},
    ]


def test_records_carry_no_content_metadata_for_a_repository_without_it():
    NS = papers_namespace([Paper(name="a", body=b"%PDF-1.7")])

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        records = client.get("/api/repositories/papers/records").json()

    assert records == [{"name": "a", "body": None}]


def test_record_media_returns_403_for_a_repository_without_a_media_view():
    NS = make_ns()

    @NS
    @Repository(Item)
    class Items:
        def all(self):
            return [Item(id=1, name="a")]

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/repositories/items/records/1/media")

    assert r.status_code == 403


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


# --- annotation endpoints --------------------------------------------------


def parcel_box(label="parcel"):
    return {"type": "box", "label": label, "x": 1, "y": 2, "width": 3, "height": 4}


def test_annotations_are_empty_before_anything_is_drawn(tmp_path):
    NS = photos_namespace([Photo(name="a", image=b"jpg")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=tmp_path / "ann.json")._app)

        r = client.get("/api/repositories/photos/annotations")

    assert r.status_code == 200
    assert r.json() == {"labels": [], "records": {}}


def test_annotations_round_trip_and_accumulate_labels(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = photos_namespace(
        [Photo(name="front door.jpg", image=b"jpg"), Photo(name="b", image=b"jpg")]
    )
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        first = client.put(
            "/api/repositories/photos/records/front%20door.jpg/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box()]},
        )
        second = client.put(
            "/api/repositories/photos/records/b/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box("door")]},
        )
        block = client.get("/api/repositories/photos/annotations").json()

    assert first.json() == {"labels": ["parcel"]}
    assert second.json() == {"labels": ["parcel", "door"]}
    assert block == {
        "labels": ["parcel", "door"],
        "records": {
            "front door.jpg": {"width": 10, "height": 20, "annotations": [parcel_box()]},
            "b": {"width": 10, "height": 20, "annotations": [parcel_box("door")]},
        },
    }
    assert json.loads(annotations_file.read_text())["repositories"]["photos"] == block


def test_annotations_put_drops_labels_no_box_uses_any_more(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = photos_namespace([Photo(name="a", image=b"jpg"), Photo(name="b", image=b"jpg")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)
        client.put(
            "/api/repositories/photos/records/a/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box()]},
        )
        client.put(
            "/api/repositories/photos/records/b/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box("door")]},
        )

        r = client.put(
            "/api/repositories/photos/records/a/annotations",
            json={"width": 10, "height": 20, "annotations": []},
        )

    assert r.json() == {"labels": ["door"]}
    assert json.loads(annotations_file.read_text())["repositories"]["photos"]["labels"] == ["door"]


def test_annotations_put_rejects_a_malformed_body(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = photos_namespace([Photo(name="a", image=b"jpg")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        r = client.put(
            "/api/repositories/photos/records/a/annotations",
            json={"width": 10, "height": 20, "annotations": [{"type": "box"}]},
        )

    assert r.status_code == 400
    assert not annotations_file.exists()


def test_annotations_refuse_to_overwrite_an_unreadable_file(tmp_path):
    annotations_file = tmp_path / "ann.json"
    annotations_file.write_text("not json")
    NS = photos_namespace([Photo(name="a", image=b"jpg")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        r = client.put(
            "/api/repositories/photos/records/a/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box()]},
        )

    assert r.status_code == 500
    assert annotations_file.read_text() == "not json"


def test_annotations_are_disabled_without_a_file():
    NS = photos_namespace([Photo(name="a", image=b"jpg")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        assert client.get("/api/ui/extensions").json()["annotations"] is False
        assert client.get("/api/repositories/photos/annotations").json() == {
            "labels": [],
            "records": {},
        }
        r = client.put(
            "/api/repositories/photos/records/a/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box()]},
        )

    assert r.status_code == 404


def test_extensions_report_annotations_enabled_with_a_file(tmp_path):
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=tmp_path / "ann.json")._app)

        assert client.get("/api/ui/extensions").json()["annotations"] is True


def test_document_annotations_round_trip(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = papers_namespace([Paper(name="a", body="Total: $100.00"), Paper(name="b", body=b"%PDF-")])
    span = {"type": "span", "label": "total", "start": 7, "end": 14, "text": "$100.00"}
    page_box = {
        "type": "box",
        "label": "logo",
        "page": 1,
        "x": 40,
        "y": 32.5,
        "width": 120,
        "height": 48,
        "page_width": 612,
        "page_height": 792,
    }
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        first = client.put(
            "/api/repositories/papers/records/a/annotations", json={"annotations": [span]}
        )
        second = client.put(
            "/api/repositories/papers/records/b/annotations", json={"annotations": [page_box]}
        )
        block = client.get("/api/repositories/papers/annotations").json()

    assert first.json() == {"labels": ["total"]}
    assert second.json() == {"labels": ["total", "logo"]}
    assert block == {
        "labels": ["total", "logo"],
        "records": {"a": {"annotations": [span]}, "b": {"annotations": [page_box]}},
    }
    assert json.loads(annotations_file.read_text())["repositories"]["papers"] == block


def test_document_annotations_put_rejects_a_malformed_body(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = papers_namespace([Paper(name="a", body="Total: $100.00")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        r = client.put(
            "/api/repositories/papers/records/a/annotations",
            json={"annotations": [{"type": "span", "label": "total", "start": 7, "end": 3}]},
        )

    assert r.status_code == 400
    assert not annotations_file.exists()


@Entity
@dataclass
class Reading:
    id: int
    value: float
    at: float


def readings_namespace():
    """A namespace holding a ``Readings`` repository with a ``TimeseriesView``."""
    NS = make_ns()

    @NS
    @Repository(Reading)
    class Readings:
        def all(self):
            return [Reading(id=1, value=1.5, at=100.0), Reading(id=2, value=9.0, at=200.0)]

        def data_view(self):
            return TimeseriesView(field="at")

    return NS


def test_timeseries_annotations_round_trip_in_time_order(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = readings_namespace()
    time_range = {"type": "range", "label": "drift", "start": 120.5, "end": 180}
    point = {"type": "point", "label": "spike", "at": 100.0, "key": "1"}
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        empty = client.get("/api/repositories/readings/annotations")
        saved = client.put(
            "/api/repositories/readings/annotations", json={"annotations": [time_range, point]}
        )
        block = client.get("/api/repositories/readings/annotations").json()

    assert empty.json() == {"labels": [], "annotations": []}
    assert saved.json() == {"labels": ["drift", "spike"]}
    assert block == {"labels": ["drift", "spike"], "annotations": [point, time_range]}
    assert json.loads(annotations_file.read_text())["repositories"]["readings"] == block


def test_timeseries_annotations_put_rejects_a_malformed_body(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = readings_namespace()
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        r = client.put(
            "/api/repositories/readings/annotations",
            json={"annotations": [{"type": "range", "label": "drift", "start": 9, "end": 3}]},
        )

    assert r.status_code == 400
    assert not annotations_file.exists()


def test_timeseries_annotations_are_disabled_without_a_file():
    NS = readings_namespace()
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        block = client.get("/api/repositories/readings/annotations")
        r = client.put("/api/repositories/readings/annotations", json={"annotations": []})

    assert block.json() == {"labels": [], "annotations": []}
    assert r.status_code == 404


def test_timeseries_and_record_annotations_are_put_through_their_own_routes(tmp_path):
    annotations_file = tmp_path / "ann.json"
    with Context(namespaces={readings_namespace(), photos_namespace([])}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        on_record = client.put(
            "/api/repositories/readings/records/1/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box()]},
        )
        on_repository = client.put("/api/repositories/photos/annotations", json={"annotations": []})

    assert on_record.status_code == 404
    assert on_repository.status_code == 404
    assert not annotations_file.exists()


@Entity(name="server-store")
@dataclass
class Store:
    id: int
    lat: float
    lon: float


def stores_namespace():
    """A namespace holding a ``Stores`` repository with a ``LocationView``."""
    NS = make_ns()

    @NS
    @Repository(Store)
    class Stores:
        def all(self):
            return [Store(id=1, lat=50.45, lon=30.52)]

        def data_view(self):
            return LocationView(fields=("lat", "lon"))

    return NS


def test_map_annotations_round_trip(tmp_path):
    annotations_file = tmp_path / "ann.json"
    region = {
        "type": "box",
        "label": "downtown",
        "south": 50.44,
        "west": 30.5,
        "north": 50.46,
        "east": 30.54,
    }
    with Context(namespaces={stores_namespace()}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        empty = client.get("/api/repositories/stores/annotations")
        saved = client.put("/api/repositories/stores/annotations", json={"annotations": [region]})
        block = client.get("/api/repositories/stores/annotations").json()

    assert empty.json() == {"labels": [], "annotations": []}
    assert saved.json() == {"labels": ["downtown"]}
    assert block == {"labels": ["downtown"], "annotations": [region]}
    assert json.loads(annotations_file.read_text())["repositories"]["stores"] == block


def test_map_annotations_put_rejects_a_malformed_body_and_the_record_route(tmp_path):
    annotations_file = tmp_path / "ann.json"
    with Context(namespaces={stores_namespace()}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        malformed = client.put(
            "/api/repositories/stores/annotations",
            json={"annotations": [{"type": "range", "label": "x", "start": 1, "end": 2}]},
        )
        on_record = client.put(
            "/api/repositories/stores/records/1/annotations", json={"annotations": []}
        )

    assert malformed.status_code == 400
    assert on_record.status_code == 404
    assert not annotations_file.exists()


@pytest.mark.parametrize("view", [VideoView(field="clip"), AudioView(field="clip")])
def test_clip_annotations_round_trip(tmp_path, view):
    annotations_file = tmp_path / "ann.json"
    NS = clips_namespace([Clip(name="a", clip=b"clip")], view)
    time_range = {"type": "range", "label": "speech", "start": 0.8, "end": 4.25}
    point = {"type": "point", "label": "cough", "at": 0.5}
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        saved = client.put(
            "/api/repositories/clips/records/a/annotations",
            json={"duration": 12.48, "annotations": [time_range, point]},
        )
        block = client.get("/api/repositories/clips/annotations").json()

    assert saved.json() == {"labels": ["cough", "speech"]}
    assert block == {
        "labels": ["cough", "speech"],
        "records": {"a": {"duration": 12.48, "annotations": [point, time_range]}},
    }
    assert json.loads(annotations_file.read_text())["repositories"]["clips"] == block


def test_clip_annotations_put_rejects_a_malformed_body(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = clips_namespace([Clip(name="a", clip=b"clip")], AudioView(field="clip"))
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        r = client.put(
            "/api/repositories/clips/records/a/annotations",
            json={"annotations": [{"type": "point", "label": "cough", "at": 0.5}]},
        )

    assert r.status_code == 400
    assert not annotations_file.exists()


def items_namespace():
    """A namespace holding an ``Items`` repository shown as the default table."""
    NS = make_ns()

    @NS
    @Repository(Item)
    class Items:
        def all(self):
            return [Item(id=1, name="a"), Item(id=2, name="b")]

    return NS


def test_record_classes_round_trip_for_a_table_repository(tmp_path):
    annotations_file = tmp_path / "ann.json"
    with Context(namespaces={items_namespace()}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        empty = client.get("/api/repositories/items/classes")
        first = client.put("/api/repositories/items/records/1/class", json={"class": "good"})
        second = client.put("/api/repositories/items/records/2/class", json={"class": "bad"})
        block = client.get("/api/repositories/items/classes").json()

    assert empty.json() == {"classes": [], "records": {}}
    assert first.json() == {"classes": ["good"]}
    assert second.json() == {"classes": ["good", "bad"]}
    assert block == {"classes": ["good", "bad"], "records": {"1": "good", "2": "bad"}}
    saved = json.loads(annotations_file.read_text())["repositories"]["items"]
    assert saved == {"classes": ["good", "bad"], "record_classes": {"1": "good", "2": "bad"}}


def test_record_class_is_cleared_with_null_and_kept_apart_from_boxes(tmp_path):
    annotations_file = tmp_path / "ann.json"
    NS = photos_namespace([Photo(name="a", image=b"jpg")])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        client.put(
            "/api/repositories/photos/records/a/annotations",
            json={"width": 10, "height": 20, "annotations": [parcel_box()]},
        )
        client.put("/api/repositories/photos/records/a/class", json={"class": "ok"})
        cleared = client.put("/api/repositories/photos/records/a/class", json={"class": None})
        classes = client.get("/api/repositories/photos/classes").json()
        boxes = client.get("/api/repositories/photos/annotations").json()

    assert cleared.json() == {"classes": []}
    assert classes == {"classes": [], "records": {}}
    assert boxes == {
        "labels": ["parcel"],
        "records": {"a": {"width": 10, "height": 20, "annotations": [parcel_box()]}},
    }


def test_record_class_put_rejects_a_malformed_body(tmp_path):
    annotations_file = tmp_path / "ann.json"
    with Context(namespaces={items_namespace()}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=annotations_file)._app)

        r = client.put("/api/repositories/items/records/1/class", json={"class": "  "})

    assert r.status_code == 400
    assert not annotations_file.exists()


def test_record_classes_are_disabled_without_a_file():
    with Context(namespaces={items_namespace()}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)

        block = client.get("/api/repositories/items/classes")
        r = client.put("/api/repositories/items/records/1/class", json={"class": "good"})

    assert block.json() == {"classes": [], "records": {}}
    assert r.status_code == 404


def test_record_classes_are_not_served_for_streaming_or_unknown_repositories(tmp_path):
    NS = make_ns()

    @NS
    @Repository(Frame)
    class Cam:
        def stream(self):
            yield Frame(id=1, data=b"jpg")

        def data_view(self):
            return StreamingVideoView(field="data")

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=tmp_path / "ann.json")._app)

        assert client.get("/api/repositories/cam/classes").status_code == 404
        r = client.put("/api/repositories/cam/records/1/class", json={"class": "good"})
        assert r.status_code == 404
        assert client.get("/api/repositories/nope/classes").status_code == 404


def test_annotations_are_not_served_for_other_repositories(tmp_path):
    NS = make_ns()

    @NS
    @Repository(Item)
    class Items:
        def all(self):
            return []

    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", annotations_file=tmp_path / "ann.json")._app)

        assert client.get("/api/repositories/items/annotations").status_code == 404
        assert client.get("/api/repositories/nope/annotations").status_code == 404


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


def test_ui_extensions_reports_iso_grid_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/api/ui/extensions")

    assert r.json()["grid"] == "iso"


def test_ui_extensions_reports_configured_grid():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", grid="flat")._app)
        r = client.get("/api/ui/extensions")

    assert r.json()["grid"] == "flat"


# --- themes --------------------------------------------------------------------


def test_serves_default_theme_by_default():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_serves_named_theme_explicitly():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="default")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_favicon_falls_back_to_theme_default_when_not_overridden():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="default")._app)
        r = client.get("/favicon.svg")

    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]


def test_unknown_theme_raises_value_error_at_construction():
    with Context(namespaces=set()) as ctx:
        with pytest.raises(ValueError, match="Unknown UI theme 'bogus'"):
            UiServer(ctx, "proj", theme="bogus")


def test_selecting_a_different_theme_serves_different_content(tmp_path, monkeypatch):
    alt = tmp_path / "alt"
    alt.mkdir()
    (alt / "theme.css").write_text("/* alt theme marker */")
    (alt / "favicon.svg").write_text("<svg><title>alt favicon</title></svg>")
    monkeypatch.setattr(themes, "_THEMES_DIR", tmp_path)

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="alt")._app)
        r = client.get("/theme.css")

    assert "alt theme marker" in r.text


def make_theme_dir(path, script=True):
    path.mkdir()
    (path / "theme.css").write_text("/* project theme marker */")
    (path / "favicon.svg").write_text("<svg><title>project favicon</title></svg>")
    if script:
        (path / "theme.js").write_text("// project theme script")
    return path


def test_serves_a_project_theme_from_an_absolute_path(tmp_path):
    theme = make_theme_dir(tmp_path / "my-theme")

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme=str(theme))._app)
        responses = {path: client.get(path) for path in ("/theme.css", "/theme.js", "/favicon.svg")}

    assert "project theme marker" in responses["/theme.css"].text
    assert "project theme script" in responses["/theme.js"].text
    assert "project favicon" in responses["/favicon.svg"].text


def test_resolves_a_relative_project_theme_path_against_the_working_directory(
    tmp_path, monkeypatch
):
    make_theme_dir(tmp_path / "my-theme")
    monkeypatch.chdir(tmp_path)

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="./my-theme")._app)
        r = client.get("/theme.css")

    assert "project theme marker" in r.text


def test_project_theme_without_a_script_serves_an_empty_one(tmp_path):
    theme = make_theme_dir(tmp_path / "my-theme", script=False)

    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme=str(theme))._app)
        r = client.get("/theme.js")

    assert r.status_code == 200
    assert r.text == ""


def test_missing_project_theme_directory_raises_value_error(tmp_path):
    with pytest.raises(ValueError, match="UI theme directory .* does not exist"):
        themes.theme_dir(str(tmp_path / "nowhere"))


def test_project_theme_missing_a_required_file_raises_value_error(tmp_path):
    theme = make_theme_dir(tmp_path / "my-theme")
    (theme / "favicon.svg").unlink()

    with pytest.raises(ValueError, match="missing required file 'favicon.svg'"):
        themes.theme_dir(str(theme))


def test_built_in_theme_name_wins_over_a_same_named_directory(tmp_path, monkeypatch):
    make_theme_dir(tmp_path / "default")
    monkeypatch.chdir(tmp_path)

    assert themes.theme_dir("default") == themes.STATIC_DIR / "themes" / "default"


def test_unknown_theme_error_mentions_theme_paths():
    with pytest.raises(ValueError, match='path to a theme directory such as "./my-theme"'):
        themes.theme_dir("bogus")


def test_list_themes_finds_the_built_in_default_theme():
    assert "default" in themes.list_themes()


def test_list_themes_finds_the_built_in_glitch_theme():
    assert "glitch" in themes.list_themes()


def test_list_themes_finds_the_built_in_neo_theme():
    assert "neo" in themes.list_themes()


def test_list_themes_finds_the_built_in_emerald_theme():
    assert "emerald" in themes.list_themes()


def test_list_themes_finds_the_built_in_onyx_theme():
    assert "onyx" in themes.list_themes()


def test_theme_can_draw_the_canvas_coarser():
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "pixelSize: null" in script
    assert "const dpr = canvasScale();" in script
    assert "'pixelSize' in rest" in script


def test_theme_can_set_the_canvas_label_font():
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "labelFont: \"'SF Mono', 'Courier New', monospace\"" in script
    assert "labelSize: 9.5," in script
    assert script.count("px ${THEME_STYLE.labelFont}`") == 2


def test_theme_can_replace_empty_tile_drawing():
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "emptyTile: null" in script
    assert "THEME_STYLE.emptyTile(sx, sy)" in script


def test_theme_can_draw_a_ground_shadow_under_icons():
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "groundShadow: null" in script
    assert "THEME_STYLE.groundShadow(x, y, e, accent, lit)" in script


def test_theme_can_fill_faces_across_the_whole_icon():
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "faceFill: null" in script
    assert "function drawIcon(key, x, y, accent, lit)" in script
    assert "THEME_STYLE.faceFill(side, accent, lit, t, ICON_FRAME)" in script
    # Both the topology and the icon picker's swatches draw through drawIcon,
    # so a face fill spans the icon in both.
    assert "ICONS[iconKey(node)].draw(" not in script
    assert "drawIcon(key, canvasEl.width / 2" in script


def test_ui_has_the_collapsible_sidebar_rail():
    html = (themes.STATIC_DIR / "index.html").read_text()
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert 'id="sb-rail"' in html
    assert "odf-ui-sidebar" in script


def test_ui_header_status_shows_run_activity():
    html = (themes.STATIC_DIR / "index.html").read_text()
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert 'id="hdr-status"' in html
    assert 'class="hdr-status-text"' in html
    assert "function updateHeaderStatus()" in script
    assert "RUN_ACTIVE_VERB" in script
    for name in themes.list_themes():
        css = (themes.STATIC_DIR / "themes" / name / "theme.css").read_text()
        assert ".hdr-status.failed{" in css, name
        assert ".hdr-status.running .dot" in css, name


def test_ui_has_the_lightbox_tool_rail():
    html = (themes.STATIC_DIR / "index.html").read_text()
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert 'id="media-lightbox-rail"' in html
    for tool in ("select", "box", "fixed", "span"):
        assert f'data-tool="{tool}"' in html
    for control in ("image-box-width", "image-box-height"):
        assert f'id="{control}"' in html
    assert "odf-ui-box-size" in script
    assert "odf-ui-lightbox-tool" in script


def test_ui_takes_node_cells_from_the_topology_payload():
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "nodeMap[id].col = pos.col" not in script
    assert "nodeMap[id].row = pos.row" not in script
    assert "nodeMap[id].icon = pos.icon" in script


def test_index_loads_the_shared_script_and_the_theme_files():
    html = (themes.STATIC_DIR / "index.html").read_text()

    assert 'href="/theme.css"' in html
    assert html.index('src="/app.js"') < html.index('src="/theme.js"')


def test_activity_and_chat_toggles_live_in_the_header():
    html = (themes.STATIC_DIR / "index.html").read_text()
    body = html.index('<div id="body">')

    assert html.index('id="hdr"') < html.index('id="activity-toggle"') < body
    assert html.index('id="hdr"') < html.index('id="chat-toggle"') < body
    assert "map-toggle-group" not in html


@pytest.mark.parametrize("theme", themes.list_themes())
def test_no_theme_floats_toggles_over_the_map(theme):
    css = (themes.theme_dir(theme) / "theme.css").read_text()

    assert "map-toggle-group" not in css
    assert ".hdr-icon-btn" in css


@pytest.mark.parametrize("theme", themes.list_themes())
def test_no_theme_ships_its_own_index_html(theme):
    assert not (themes.theme_dir(theme) / "index.html").exists()


def test_serves_the_shared_script():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/app.js")

    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"


ICON_SCRIPTS = sorted(p.name for p in (themes.STATIC_DIR / "icons").glob("*.js"))
DEFAULT_ICONS = {
    "config",
    "component",
    "repository",
    "service",
    "task",
    "pipeline",
    "agent",
    "function",
}


@pytest.mark.parametrize("name", ICON_SCRIPTS)
def test_serves_every_icon_group_script(name):
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get(f"/icons/{name}")

    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
    assert r.text == (themes.STATIC_DIR / "icons" / name).read_text()


def test_unknown_icon_group_script_is_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/icons/nope.js")

    assert r.status_code == 404


def test_index_loads_every_icon_group_script_between_app_and_theme():
    html = (themes.STATIC_DIR / "index.html").read_text()
    positions = {name: html.index(f'src="/icons/{name}"') for name in ICON_SCRIPTS}

    assert "shared.js" in ICON_SCRIPTS
    assert html.index('src="/app.js"') < positions["shared.js"]
    assert all(positions["shared.js"] <= pos for pos in positions.values())
    assert max(positions.values()) < html.index('src="/theme.js"')


GRID_SCRIPTS = sorted(p.name for p in (themes.STATIC_DIR / "grids").glob("*.js"))


@pytest.mark.parametrize("name", GRID_SCRIPTS)
def test_serves_every_grid_script(name):
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get(f"/grids/{name}")

    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
    assert r.text == (themes.STATIC_DIR / "grids" / name).read_text()


def test_unknown_grid_script_is_404():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        r = client.get("/grids/nope.js")

    assert r.status_code == 404


def test_index_loads_every_grid_script_between_app_and_theme():
    html = (themes.STATIC_DIR / "index.html").read_text()
    positions = [html.index(f'src="/grids/{name}"') for name in GRID_SCRIPTS]

    assert "flat.js" in GRID_SCRIPTS
    assert html.index('src="/app.js"') < min(positions)
    assert max(positions) < html.index('src="/theme.js"')


def test_icon_group_scripts_register_unique_keys():
    keys = []
    for name in ICON_SCRIPTS:
        script = (themes.STATIC_DIR / "icons" / name).read_text()
        keys += re.findall(r"\badd\('([^']+)'", script)

    assert len(keys) == len(set(keys))
    assert not DEFAULT_ICONS & set(keys)
    assert {
        "camera",
        "photo-camera",
        "conveyor",
        "conveyor-intake",
        "podium",
        "podium-star",
    } <= set(keys)


def test_app_script_keeps_only_the_default_icons():
    script = (themes.STATIC_DIR / "app.js").read_text()
    registry = script[script.index("const ICONS = {") :]
    registry = registry[: registry.index("};")]

    assert set(re.findall(r"^\s+'?([\w-]+)'?:\s+\{ draw:", registry, re.M)) == DEFAULT_ICONS


@pytest.mark.parametrize("theme", themes.list_themes())
def test_serves_every_theme_stylesheet(theme):
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme=theme)._app)
        r = client.get("/theme.css")

    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
    assert r.text == (themes.theme_dir(theme) / "theme.css").read_text()


def test_theme_script_is_empty_for_a_theme_without_one():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="default")._app)
        r = client.get("/theme.js")

    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.text == ""


@pytest.mark.parametrize("theme", ["glitch", "neo"])
def test_theme_script_is_served_for_a_theme_that_has_one(theme):
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme=theme)._app)
        r = client.get("/theme.js")

    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "ODF.registerTheme(" in r.text


def test_theme_dir_resolves_the_default_theme():
    path = themes.theme_dir("default")

    assert (path / "theme.css").is_file()
    assert (path / "favicon.svg").is_file()


def test_serves_glitch_theme_explicitly():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="glitch")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_theme_dir_resolves_the_glitch_theme():
    path = themes.theme_dir("glitch")

    assert (path / "theme.css").is_file()
    assert (path / "favicon.svg").is_file()


def test_serves_neo_theme_explicitly():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="neo")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_theme_dir_resolves_the_neo_theme():
    path = themes.theme_dir("neo")

    assert (path / "theme.css").is_file()
    assert (path / "favicon.svg").is_file()


def test_serves_emerald_theme_explicitly():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="emerald")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_theme_dir_resolves_the_emerald_theme():
    path = themes.theme_dir("emerald")

    assert (path / "theme.css").is_file()
    assert (path / "favicon.svg").is_file()


def test_serves_onyx_theme_explicitly():
    with Context(namespaces=set()) as ctx:
        client = TestClient(UiServer(ctx, "proj", theme="onyx")._app)
        r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_theme_dir_resolves_the_onyx_theme():
    path = themes.theme_dir("onyx")

    assert (path / "theme.css").is_file()
    assert (path / "favicon.svg").is_file()


def test_theme_dir_raises_on_unknown_theme():
    with pytest.raises(ValueError, match="Unknown UI theme 'bogus'"):
        themes.theme_dir("bogus")
