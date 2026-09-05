import asyncio
import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.namespace import Namespace
from opendataframework.service import Service
from opendataframework.task import Task

from odf.mcp.server import McpServer


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
