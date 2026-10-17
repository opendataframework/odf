import asyncio
from types import SimpleNamespace

from odf.chat import engine as engine_module
from odf.chat.engine import ChatEngine


def collect(chat_engine: ChatEngine, messages: list[dict]) -> list[dict]:
    async def _collect():
        return [event async for event in chat_engine.stream(messages)]

    return asyncio.run(_collect())


def make_chunk(content: str = "", tool_calls: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls or []))


def make_tool_call(name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class FakeAsyncClient:
    """Stand-in for ``ollama.AsyncClient`` — one canned chunk list per call to
    ``chat()``, reusing the last one once exhausted (for loop-cap tests)."""

    def __init__(self, responses: list[list[SimpleNamespace]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def chat(self, model, messages, tools, stream):
        self.calls.append({"model": model, "messages": list(messages), "tools": tools})
        chunks = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

        async def gen():
            for chunk in chunks:
                yield chunk

        return gen()


_DEFAULT_TOOLS = [
    SimpleNamespace(
        name="start_component",
        description="Start a service",
        inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    )
]

_DEFAULT_COMPONENTS = [
    {"id": "component.widget", "label": "Widget", "type": "component"},
    {"id": "repository.logs", "label": "Logs", "type": "repository"},
]


class FakeMcp:
    def __init__(
        self,
        tool_result: dict | None = None,
        tools: list[SimpleNamespace] | None = None,
        components: list[dict] | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._tool_result = tool_result or {"result": "ok"}
        self._tools = tools if tools is not None else _DEFAULT_TOOLS
        self._components = components if components is not None else _DEFAULT_COMPONENTS

    async def list_tools(self):
        return self._tools

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "list_components":
            return self._components
        return self._tool_result


def build_engine(monkeypatch, client: FakeAsyncClient, mcp=None, debug: bool = False) -> ChatEngine:
    monkeypatch.setattr(engine_module, "AsyncClient", lambda host: client)
    return ChatEngine(model="test-model", host="http://fake", mcp=mcp, debug=debug)


def test_stream_yields_tokens_for_plain_reply(monkeypatch):
    client = FakeAsyncClient([[make_chunk("Hi"), make_chunk(" there")]])
    chat_engine = build_engine(monkeypatch, client)

    events = collect(chat_engine, [{"role": "user", "content": "hello"}])

    assert events == [
        {"type": "token", "content": "Hi"},
        {"type": "token", "content": " there"},
    ]
    assert client.calls[0]["tools"] is None


def test_stream_executes_tool_call_and_feeds_result_back(monkeypatch):
    tool_call = make_tool_call("start_component", {"name": "Postgres"})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("Started it.")],
        ]
    )
    fake_mcp = FakeMcp(tool_result={"result": "Postgres started"})
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp, debug=True)

    events = collect(chat_engine, [{"role": "user", "content": "start postgres"}])

    assert events == [
        {"type": "tool_call", "name": "start_component", "arguments": {"name": "Postgres"}},
        {
            "type": "tool_result",
            "name": "start_component",
            "result": '{"result": "Postgres started"}',
        },
        {"type": "token", "content": "Started it."},
    ]
    assert fake_mcp.calls == [("start_component", {"name": "Postgres"})]
    # The follow-up call's tools list reflects list_tools(), same as the first.
    assert client.calls[1]["tools"][0]["function"]["name"] == "start_component"


def test_stream_suppresses_tool_events_by_default(monkeypatch):
    tool_call = make_tool_call("start_component", {"name": "Postgres"})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("Started it.")],
        ]
    )
    fake_mcp = FakeMcp(tool_result={"result": "Postgres started"})
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    events = collect(chat_engine, [{"role": "user", "content": "start postgres"}])

    assert events == [{"type": "token", "content": "Started it."}]
    # The tool still actually ran and its result still fed the follow-up turn.
    assert fake_mcp.calls == [("start_component", {"name": "Postgres"})]
    assert client.calls[1]["tools"][0]["function"]["name"] == "start_component"


def test_stream_yields_error_on_connection_failure(monkeypatch):
    class BrokenClient:
        async def chat(self, *args, **kwargs):
            raise ConnectionError("connection refused")

    chat_engine = build_engine(monkeypatch, BrokenClient())

    events = collect(chat_engine, [{"role": "user", "content": "hi"}])

    assert events == [{"type": "error", "message": "connection refused"}]


def test_stream_stops_after_tool_call_limit(monkeypatch):
    tool_call = make_tool_call("start_component", {"name": "Postgres"})
    client = FakeAsyncClient([[make_chunk("", tool_calls=[tool_call])]])
    fake_mcp = FakeMcp()
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    events = collect(chat_engine, [{"role": "user", "content": "loop forever"}])

    assert events[-1] == {"type": "error", "message": "tool-call limit reached"}
    assert len(fake_mcp.calls) == engine_module._MAX_TOOL_ROUNDTRIPS


def test_stream_without_mcp_reports_tools_unavailable(monkeypatch):
    tool_call = make_tool_call("start_component", {"name": "Postgres"})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("Can't do that.")],
        ]
    )
    chat_engine = build_engine(monkeypatch, client, mcp=None, debug=True)

    events = collect(chat_engine, [{"role": "user", "content": "start postgres"}])

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert "no tools available" in tool_result["result"]


_SCOPED_TOOLS = [
    SimpleNamespace(
        name="query_repository",
        description="Query a repository",
        inputSchema={"type": "object", "properties": {}},
    ),
    SimpleNamespace(
        name="start_component",
        description="Start a service",
        inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    ),
    SimpleNamespace(
        name="stop_component",
        description="Stop a service",
        inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    ),
    SimpleNamespace(
        name="execute_task",
        description="Execute a task",
        inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    ),
    SimpleNamespace(
        name="component_logs",
        description="Read logs",
        inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    ),
    SimpleNamespace(
        name="component.widget.status",
        description="Widget's own status tool",
        inputSchema={"type": "object", "properties": {}},
    ),
]


def test_addressing_component_scopes_tool_specs(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@component.widget what's your status?"}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert tool_names == {
        "component.widget.status",
        "start_component",
        "stop_component",
        "execute_task",
        "component_logs",
    }


def test_addressing_repository_includes_query_repository_and_forces_its_key(monkeypatch):
    tool_call = make_tool_call("query_repository", {"key": "repository.other", "limit": 10})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("done")],
        ]
    )
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS, tool_result={"records": [], "total": 0})
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@repository.logs how many rows?"}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "query_repository" in tool_names
    forced_call = next(c for c in fake_mcp.calls if c[0] == "query_repository")
    assert forced_call == ("query_repository", {"key": "repository.logs", "limit": 10})


def test_addressing_forces_lifecycle_tool_key_to_addressed_key(monkeypatch):
    tool_call = make_tool_call("start_component", {"key": "service.something-else"})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("done")],
        ]
    )
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS, tool_result={"result": "Widget started"})
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@component.widget please start"}])

    forced_call = next(c for c in fake_mcp.calls if c[0] == "start_component")
    assert forced_call == ("start_component", {"key": "component.widget"})


def test_addressing_agent_keeps_its_invoke_tool_and_passes_arguments_through(monkeypatch):
    tools = [
        *_SCOPED_TOOLS,
        SimpleNamespace(
            name="agent.librarian.invoke",
            description="Answers questions about the catalogue.",
            inputSchema={"type": "object", "properties": {"question": {"type": "string"}}},
        ),
    ]
    components = [
        *_DEFAULT_COMPONENTS,
        {"id": "agent.librarian", "label": "Librarian", "type": "agent"},
    ]
    tool_call = make_tool_call("agent.librarian.invoke", {"question": "Anything by Herbert?"})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("Dune.")],
        ]
    )
    fake_mcp = FakeMcp(tools=tools, components=components, tool_result={"result": "Dune"})
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@agent.librarian anything by Herbert?"}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert tool_names == {
        "agent.librarian.invoke",
        "start_component",
        "stop_component",
        "execute_task",
        "component_logs",
    }
    assert ("agent.librarian.invoke", {"question": "Anything by Herbert?"}) in fake_mcp.calls


def test_addressing_function_keeps_its_call_tool(monkeypatch):
    tools = [
        *_SCOPED_TOOLS,
        SimpleNamespace(
            name="function.load-data.call",
            description="Load rows from a file.",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
        ),
    ]
    components = [
        *_DEFAULT_COMPONENTS,
        {"id": "function.load-data", "label": "load_data", "type": "function", "verb": "call"},
    ]
    tool_call = make_tool_call("function.load-data.call", {"path": "data.csv"})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("Loaded 42 rows.")],
        ]
    )
    fake_mcp = FakeMcp(tools=tools, components=components, tool_result={"result": 42})
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@function.load-data load data.csv"}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "function.load-data.call" in tool_names
    assert "query_repository" not in tool_names
    assert ("function.load-data.call", {"path": "data.csv"}) in fake_mcp.calls


def test_addressing_rejects_tool_outside_scope(monkeypatch):
    tool_call = make_tool_call("other.thing", {})
    client = FakeAsyncClient(
        [
            [make_chunk("", tool_calls=[tool_call])],
            [make_chunk("done")],
        ]
    )
    tools = [
        *_SCOPED_TOOLS,
        SimpleNamespace(
            name="other.thing", description="", inputSchema={"type": "object", "properties": {}}
        ),
    ]
    fake_mcp = FakeMcp(tools=tools)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp, debug=True)

    events = collect(
        chat_engine, [{"role": "user", "content": "@component.widget do the other thing"}]
    )

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert "not available while addressing" in tool_result["result"]
    assert not any(call[0] == "other.thing" for call in fake_mcp.calls)


def test_unknown_mention_falls_back_to_full_tool_set(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@nonexistent what now?"}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert tool_names == {tool.name for tool in _SCOPED_TOOLS}


def test_a_bare_name_does_not_address_a_component(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "@widget what's your status?"}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert tool_names == {tool.name for tool in _SCOPED_TOOLS}


def test_a_closing_period_is_not_part_of_the_mention(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(chat_engine, [{"role": "user", "content": "Report on @Component.Widget."}])

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "component.widget.status" in tool_names
    assert "query_repository" not in tool_names


def test_mid_message_mention_resolves(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    collect(
        chat_engine, [{"role": "user", "content": "can you ask @component.widget about its state"}]
    )

    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "component.widget.status" in tool_names
    assert "query_repository" not in tool_names


def test_repeated_mention_of_same_component_is_not_multiple(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    events = collect(
        chat_engine,
        [
            {
                "role": "user",
                "content": "@component.widget, seriously, @component.widget, are you there?",
            }
        ],
    )

    assert not any(e["type"] == "error" for e in events)
    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "component.widget.status" in tool_names


def test_addressing_multiple_distinct_components_rejects_turn(monkeypatch):
    client = FakeAsyncClient([[make_chunk("ok")]])
    fake_mcp = FakeMcp(tools=_SCOPED_TOOLS)
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

    events = collect(
        chat_engine,
        [{"role": "user", "content": "@component.widget and @repository.logs, compare your data"}],
    )

    assert events == [
        {
            "type": "error",
            "message": (
                "multiple components addressed in one message "
                "(@component.widget, @repository.logs) — address one component per message"
            ),
        }
    ]
    assert client.calls == []
