import asyncio
import json
from dataclasses import dataclass

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.namespace import Namespace
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.task import Task

from odf.mcp.server import McpServer


@dataclass
class Widget:
    id: int
    name: str
    color: str


def make_ns():
    class NS(Namespace): ...

    return NS


def call(mcp, name: str, arguments: dict | None = None):
    return asyncio.run(mcp.call_tool(name, arguments or {}))


def structured(result):
    """Unwrap a structured-output tool's result: (content, {"result": value})."""
    _, data = result
    return data["result"]


def text(result):
    """Unwrap an unstructured-output tool's result: a bare content list."""
    return result[0].text


def test_url_reflects_host_and_port():
    with Context(namespaces=set()) as ctx:
        server = McpServer(ctx, "proj", host="127.0.0.1", port=19999)

    assert server.url == "http://127.0.0.1:19999/mcp"


# --- list_components ------------------------------------------------------------


def test_list_components_returns_resolved_graph():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "list_components")

    nodes = structured(result)
    assert any(node["label"] == "Thing" and node["type"] == "component" for node in nodes)


def test_list_components_reports_service_running_state():
    NS = make_ns()

    @NS
    @Service
    class Svc:
        def setup(self) -> None: ...
        def run(self) -> None: ...
        def stop(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "list_components")

    nodes = structured(result)
    svc = next(node for node in nodes if node["label"] == "Svc")
    assert svc["type"] == "service"
    assert svc["running"] is True


# --- start_component / stop_component --------------------------------------------


def test_start_stop_component_toggle_a_service():
    NS = make_ns()

    @NS
    @Service
    class Svc:
        def setup(self) -> None: ...
        def run(self) -> None: ...
        def stop(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp

        assert structured(call(mcp, "stop_component", {"name": "Svc"})) == "Svc stopped"
        assert ctx.is_running("Svc") is False

        assert structured(call(mcp, "start_component", {"name": "Svc"})) == "Svc started"
        assert ctx.is_running("Svc") is True


def test_start_component_rejects_non_service():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not a Service"):
            call(mcp, "start_component", {"name": "Thing"})


def test_start_component_unknown_name_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component named 'Nope'"):
            call(mcp, "start_component", {"name": "Nope"})


# --- execute_task -----------------------------------------------------------------


def test_execute_task_runs_and_returns_result():
    NS = make_ns()
    calls = []

    @NS
    @Task
    class DoStuff:
        def execute(self):
            calls.append("ran")
            return {"count": 3}

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "execute_task", {"name": "DoStuff"})

    assert calls == ["ran"]
    assert json.loads(text(result)) == {"count": 3}


def test_execute_task_rejects_non_executable():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not a Task or Pipeline"):
            call(mcp, "execute_task", {"name": "Thing"})


def test_execute_task_surfaces_exceptions():
    NS = make_ns()

    @NS
    @Task
    class Boom:
        def execute(self) -> None:
            raise RuntimeError("kaboom")

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="kaboom"):
            call(mcp, "execute_task", {"name": "Boom"})


def test_execute_task_unknown_name_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component named 'Nope'"):
            call(mcp, "execute_task", {"name": "Nope"})


# --- component_logs ----------------------------------------------------------------


def test_component_logs_returns_entries(tmp_path):
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "component_logs", {"name": "Thing"})

    entries = structured(result)
    assert any("resolved" in e["message"] for e in entries)


def test_component_logs_empty_without_log_dir():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "component_logs", {"name": "Thing"})

    assert structured(result) == []


def test_component_logs_unknown_component_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component named 'Nonexistent'"):
            call(mcp, "component_logs", {"name": "Nonexistent"})


# --- query_repository ---------------------------------------------------------------


def _widgets():
    return [
        Widget(1, "gadget", "red"),
        Widget(2, "gizmo", "blue"),
        Widget(3, "widget", "red"),
    ]


def test_query_repository_returns_page_and_total():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return _widgets()

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "query_repository", {"repo_id": "widgets"})

    _, data = result
    assert data["total"] == 3
    assert [r["name"] for r in data["records"]] == ["gadget", "gizmo", "widget"]


def test_query_repository_applies_limit_and_offset():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return _widgets()

    with Context(namespaces={NS}) as ctx:
        result = call(
            McpServer(ctx, "proj")._mcp,
            "query_repository",
            {"repo_id": "widgets", "limit": 1, "offset": 1},
        )

    _, data = result
    assert data["total"] == 3
    assert [r["name"] for r in data["records"]] == ["gizmo"]


def test_query_repository_clamps_limit_to_max():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return _widgets()

    with Context(namespaces={NS}) as ctx:
        result = call(
            McpServer(ctx, "proj")._mcp,
            "query_repository",
            {"repo_id": "widgets", "limit": 10_000},
        )

    _, data = result
    assert len(data["records"]) == 3
    assert data["total"] == 3


def test_query_repository_applies_filters():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return _widgets()

    with Context(namespaces={NS}) as ctx:
        result = call(
            McpServer(ctx, "proj")._mcp,
            "query_repository",
            {"repo_id": "widgets", "filters": {"color": "red"}},
        )

    _, data = result
    assert data["total"] == 2
    assert {r["name"] for r in data["records"]} == {"gadget", "widget"}


def test_query_repository_ignores_unknown_filter_keys():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return _widgets()

    with Context(namespaces={NS}) as ctx:
        result = call(
            McpServer(ctx, "proj")._mcp,
            "query_repository",
            {"repo_id": "widgets", "filters": {"nonexistent_field": "anything"}},
        )

    _, data = result
    assert data["total"] == 3


def test_query_repository_unknown_repo_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved repository named 'nope'"):
            call(mcp, "query_repository", {"repo_id": "nope"})


def test_query_repository_rejects_non_readable_repository():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def save(self, entity): ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not readable"):
            call(mcp, "query_repository", {"repo_id": "widgets"})
