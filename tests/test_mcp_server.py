import asyncio
import json
from dataclasses import dataclass

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from opendataframework.component import Component, McpTool
from opendataframework.context import Context
from opendataframework.entity import Entity
from opendataframework.function import Function
from opendataframework.namespace import Namespace
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.task import Task

from odf.mcp.server import McpServer


@Entity(name="mcp-widget")
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


def test_list_components_lists_functions():
    NS = make_ns()

    @NS
    @Function
    def double(value: int) -> int:
        return value * 2

    with Context(namespaces={NS}) as ctx:
        nodes = structured(call(McpServer(ctx, "proj")._mcp, "list_components"))

    node = next(node for node in nodes if node["label"] == "double")
    assert node["id"] == "n-s.double"
    assert node["type"] == "function"


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

        key = ctx.key(Svc)
        assert structured(call(mcp, "stop_component", {"key": key})) == f"{key} stopped"
        assert ctx.is_running(key) is False

        assert structured(call(mcp, "start_component", {"key": key})) == f"{key} started"
        assert ctx.is_running(key) is True


def test_start_component_rejects_non_service():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not a Service"):
            call(mcp, "start_component", {"key": ctx.key(Thing)})


def test_lifecycle_tools_reject_a_function_by_type():
    NS = make_ns()

    @NS
    @Function
    def double(value: int) -> int:
        return value * 2

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="n-s.double is not a Service"):
            call(mcp, "start_component", {"key": "n-s.double"})
        with pytest.raises(ToolError, match="n-s.double is not a Service"):
            call(mcp, "stop_component", {"key": "n-s.double"})
        with pytest.raises(ToolError, match="n-s.double is not a Task or Pipeline"):
            call(mcp, "execute_task", {"key": "n-s.double"})
        with pytest.raises(ToolError, match="is not a repository"):
            call(mcp, "query_repository", {"key": "n-s.double"})


def test_component_logs_reads_a_function_s_calls(tmp_path):
    NS = make_ns()

    @NS
    @Function
    def double(value: int) -> int:
        return value * 2

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        ctx.call("n-s.double", value=2)
        result = call(McpServer(ctx, "proj")._mcp, "component_logs", {"key": "n-s.double"})

    assert any("completed" in entry["message"] for entry in structured(result))


def test_start_component_unknown_key_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component with key 'service.nope'"):
            call(mcp, "start_component", {"key": "service.nope"})


def test_a_bare_name_is_rejected_with_the_key_hint():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not a key"):
            call(mcp, "start_component", {"key": "Nope"})
        with pytest.raises(ToolError, match="is not a key"):
            call(mcp, "component_logs", {"key": "Nope"})


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
        result = call(McpServer(ctx, "proj")._mcp, "execute_task", {"key": ctx.key(DoStuff)})

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
            call(mcp, "execute_task", {"key": ctx.key(Thing)})


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
            call(mcp, "execute_task", {"key": ctx.key(Boom)})


def test_execute_task_unknown_key_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component with key 'task.nope'"):
            call(mcp, "execute_task", {"key": "task.nope"})


# --- component_logs ----------------------------------------------------------------


def test_component_logs_returns_entries(tmp_path):
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "component_logs", {"key": ctx.key(Thing)})

    entries = structured(result)
    assert any("resolved" in e["message"] for e in entries)


def test_component_logs_empty_without_log_dir():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "component_logs", {"key": ctx.key(Thing)})

    assert structured(result) == []


def test_component_logs_unknown_component_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component with key 'component.nope'"):
            call(mcp, "component_logs", {"key": "component.nope"})


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
        result = call(McpServer(ctx, "proj")._mcp, "query_repository", {"key": ctx.key(Widgets)})

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
            {"key": ctx.key(Widgets), "limit": 1, "offset": 1},
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
            {"key": ctx.key(Widgets), "limit": 10_000},
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
            {"key": ctx.key(Widgets), "filters": {"color": "red"}},
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
            {"key": ctx.key(Widgets), "filters": {"nonexistent_field": "anything"}},
        )

    _, data = result
    assert data["total"] == 3


def test_query_repository_unknown_repo_raises():
    with Context(namespaces=set()) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="No resolved component with key 'repository.nope'"):
            call(mcp, "query_repository", {"key": "repository.nope"})


def test_query_repository_rejects_a_component_that_is_not_a_repository():
    NS = make_ns()

    @NS
    @Component
    class Thing: ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not a repository"):
            call(mcp, "query_repository", {"key": ctx.key(Thing)})


def test_query_repository_rejects_non_readable_repository():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def save(self, entity): ...

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        with pytest.raises(ToolError, match="is not readable"):
            call(mcp, "query_repository", {"key": ctx.key(Widgets)})


# --- component-exposed MCP tools (McpToolsProtocol) -------------------------------


def test_component_mcp_tool_is_registered_and_callable():
    NS = make_ns()

    @NS
    @Component
    class Thing:
        def status(self) -> str:
            return "ok"

        def mcp_tools(self) -> list[McpTool]:
            return [McpTool(name="status", description="Report status.", handler=self.status)]

    with Context(namespaces={NS}) as ctx:
        result = call(McpServer(ctx, "proj")._mcp, "n-s.thing.status")

    assert structured(result) == "ok"


def test_two_components_with_same_local_tool_name_stay_distinct():
    NS = make_ns()

    @NS
    @Component
    class Alpha:
        def status(self) -> str:
            return "alpha"

        def mcp_tools(self) -> list[McpTool]:
            return [McpTool(name="status", description="Alpha status.", handler=self.status)]

    @NS
    @Component
    class Beta:
        def status(self) -> str:
            return "beta"

        def mcp_tools(self) -> list[McpTool]:
            return [McpTool(name="status", description="Beta status.", handler=self.status)]

    with Context(namespaces={NS}) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        assert structured(call(mcp, "n-s.alpha.status")) == "alpha"
        assert structured(call(mcp, "n-s.beta.status")) == "beta"


def test_duplicate_full_tool_name_within_one_component_raises_at_construction():
    NS = make_ns()

    @NS
    @Component
    class Thing:
        def first(self) -> str:
            return "first"

        def second(self) -> str:
            return "second"

        def mcp_tools(self) -> list[McpTool]:
            return [
                McpTool(name="status", description="First.", handler=self.first),
                McpTool(name="status", description="Second.", handler=self.second),
            ]

    with Context(namespaces={NS}) as ctx:
        with pytest.raises(ValueError, match="Duplicate MCP tool name: 'n-s.thing.status'"):
            McpServer(ctx, "proj")


# --- agents ------------------------------------------------------------------------


def _librarian(NS):
    from opendataframework.agent import Agent

    @NS
    @Agent
    class Librarian:
        """Answers questions about the catalogue.

        Searches by keyword.
        """

        def invoke(self, question: str, limit: int = 3) -> dict:
            return {"question": question, "limit": limit}

    return Librarian


def test_agent_is_registered_as_its_own_invoke_tool_with_a_typed_schema():
    NS = make_ns()
    _librarian(NS)

    with Context(namespaces={NS}) as ctx:
        tools = asyncio.run(McpServer(ctx, "proj")._mcp.list_tools())

    tool = next(t for t in tools if t.name == "n-s.librarian.invoke")
    assert tool.description == "Answers questions about the catalogue."
    assert tool.inputSchema["properties"] == {
        "question": {"title": "Question", "type": "string"},
        "limit": {"default": 3, "title": "Limit", "type": "integer"},
    }
    assert tool.inputSchema["required"] == ["question"]


def test_agent_invoke_tool_calls_the_agent_through_the_context(tmp_path):
    NS = make_ns()
    _librarian(NS)

    with Context(namespaces={NS}, log_dir=tmp_path) as ctx:
        mcp = McpServer(ctx, "proj")._mcp
        result = call(mcp, "n-s.librarian.invoke", {"question": "Dune?", "limit": 2})
        logs = ctx.tail_logs("n-s.librarian")

    assert json.loads(text(result)) == {"question": "Dune?", "limit": 2}
    assert any("invoke() completed" in entry["message"] for entry in logs)


def test_agent_invoke_tool_is_listed_as_an_agent_component():
    NS = make_ns()
    _librarian(NS)

    with Context(namespaces={NS}) as ctx:
        nodes = structured(call(McpServer(ctx, "proj")._mcp, "list_components"))

    node = next(n for n in nodes if n["label"] == "Librarian")
    assert node["type"] == "agent"
    assert node["decorator"] == "@Agent"


def test_agent_invoke_tool_clashing_with_its_own_mcp_tool_raises():
    NS = make_ns()

    from opendataframework.agent import Agent

    @NS
    @Agent
    class Librarian:
        def invoke(self) -> str:
            return "agent"

        def other(self) -> str:
            return "tool"

        def mcp_tools(self) -> list[McpTool]:
            return [McpTool(name="invoke", description="Clash.", handler=self.other)]

    with Context(namespaces={NS}) as ctx:
        with pytest.raises(ValueError, match="Duplicate MCP tool name: 'n-s.librarian.invoke'"):
            McpServer(ctx, "proj")
