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


class FakeMcp:
    def __init__(self, tool_result: dict | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._tool_result = tool_result or {"result": "ok"}

    async def list_tools(self):
        return [
            SimpleNamespace(
                name="start_component",
                description="Start a service",
                inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
            )
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._tool_result


def build_engine(monkeypatch, client: FakeAsyncClient, mcp=None) -> ChatEngine:
    monkeypatch.setattr(engine_module, "AsyncClient", lambda host: client)
    return ChatEngine(model="test-model", host="http://fake", mcp=mcp)


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
    chat_engine = build_engine(monkeypatch, client, mcp=fake_mcp)

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
    chat_engine = build_engine(monkeypatch, client, mcp=None)

    events = collect(chat_engine, [{"role": "user", "content": "start postgres"}])

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert "no tools available" in tool_result["result"]
