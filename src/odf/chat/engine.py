"""Chat engine: an Ollama-backed agent loop, optionally wired to MCP tools.

Not a DI-managed component — like ``UiServer``/``McpServer``, it is built and
owned by ``Server.start(chat=True)`` and handed to ``UiServer`` to serve.
"""

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

try:
    from ollama import AsyncClient
except ImportError as exc:
    raise ImportError(
        "server.start(chat=True) requires the 'chat' extra. Install with: pip install odf[chat]"
    ) from exc

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_MAX_TOOL_ROUNDTRIPS = 6


class ChatEngine:
    """Streams chat replies from a local Ollama model, executing MCP tool calls.

    Args:
        model: Ollama model name (e.g. ``"gpt-oss:20b"``).
        host: Ollama daemon URL (e.g. ``"http://localhost:11434"``).
        mcp: The running project's ``FastMCP`` instance (from
            ``McpServer.mcp``), used in-process to list and call tools —
            the same tools exposed over MCP's streamable HTTP transport.
            ``None`` disables tool-calling; the model still answers, it
            just can't act on the project.
    """

    def __init__(self, model: str, host: str, mcp: FastMCP | None = None) -> None:
        self.model = model
        self._client = AsyncClient(host=host)
        self._mcp = mcp

    async def stream(self, messages: list[dict]) -> AsyncIterator[dict]:
        """Yield ``{"type": ..., ...}`` events for one chat turn.

        Event types: ``token`` (a chunk of assistant text), ``tool_call``
        (about to invoke an MCP tool), ``tool_result`` (its outcome), and
        ``error`` (the turn failed or was cut short) — the caller (an HTTP
        route) just forwards each event to the client, it never raises.
        """
        try:
            tools = await self._tool_specs()
            history = list(messages)
            for _ in range(_MAX_TOOL_ROUNDTRIPS):
                content = ""
                tool_calls: list = []
                async for chunk in await self._client.chat(
                    model=self.model, messages=history, tools=tools, stream=True
                ):
                    piece = chunk.message.content
                    if piece:
                        content += piece
                        yield {"type": "token", "content": piece}
                    if chunk.message.tool_calls:
                        tool_calls = chunk.message.tool_calls
                if not tool_calls:
                    return
                history.append(self._assistant_message(content, tool_calls))
                for call in tool_calls:
                    name = call.function.name
                    arguments = call.function.arguments or {}
                    yield {"type": "tool_call", "name": name, "arguments": arguments}
                    result = await self._call_tool(name, arguments)
                    yield {"type": "tool_result", "name": name, "result": result}
                    history.append({"role": "tool", "content": result})
            yield {"type": "error", "message": "tool-call limit reached"}
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}

    async def _tool_specs(self) -> list[dict] | None:
        if self._mcp is None:
            return None
        tools = await self._mcp.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools
        ]

    async def _call_tool(self, name: str, arguments: dict) -> str:
        if self._mcp is None:
            return "error: no tools available (mcp=True was not passed to Project.start())"
        try:
            result = await self._mcp.call_tool(name, arguments)
        except Exception as exc:
            return f"error: {exc}"
        return self._stringify(result)

    @staticmethod
    def _stringify(result: Any) -> str:
        if isinstance(result, dict):
            return json.dumps(result)
        parts = [getattr(block, "text", None) or str(block) for block in result]
        return "\n".join(parts)

    @staticmethod
    def _assistant_message(content: str, tool_calls: list) -> dict:
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"function": {"name": call.function.name, "arguments": call.function.arguments}}
                for call in tool_calls
            ],
        }
