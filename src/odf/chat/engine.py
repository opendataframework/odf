"""Chat engine: an Ollama-backed agent loop, optionally wired to MCP tools.

Not a DI-managed component — like ``UiServer``/``McpServer``, it is built and
owned by ``Server.start(chat=True)`` and handed to ``UiServer`` to serve.
"""

import json
import re
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

# Matches an `@handle` mention anywhere in a message, as long as the `@` is
# preceded by whitespace or the start of the string (so `user@example.com`
# doesn't get mistaken for one).
_MENTION_RE = re.compile(r"(?:^|\s)@([A-Za-z][A-Za-z0-9-]*)")

# Fixed lifecycle tools that stay available, scoped to just the addressed
# component, when a message addresses one (see `_tool_allowed`).
_LIFECYCLE_TOOLS = frozenset(
    {"start_component", "stop_component", "execute_task", "component_logs"}
)


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
        debug: Whether to yield ``tool_call``/``tool_result`` events so
            the chat window shows them inline. Tool calls are always
            executed and fed back to the model either way; this only
            controls whether that exchange is surfaced to the client.
    """

    def __init__(
        self, model: str, host: str, mcp: FastMCP | None = None, debug: bool = False
    ) -> None:
        self.model = model
        self._client = AsyncClient(host=host)
        self._mcp = mcp
        self._debug = debug

    async def stream(self, messages: list[dict]) -> AsyncIterator[dict]:
        """Yield ``{"type": ..., ...}`` events for one chat turn.

        Event types: ``token`` (a chunk of assistant text), ``tool_call``
        (about to invoke an MCP tool), ``tool_result`` (its outcome), and
        ``error`` (the turn failed or was cut short) — the caller (an HTTP
        route) just forwards each event to the client, it never raises.
        ``tool_call``/``tool_result`` are only yielded when ``debug=True``
        was passed to the constructor; the tool call itself still always
        executes and its result is always fed back to the model.

        If the latest user message addresses a component with ``@id``
        (e.g. ``"@postgres how many rows..."``), the turn's tool access is
        scoped to just that component for its whole tool-call loop — see
        ``_resolve_addressed``/``_tool_allowed``. Addressing more than one
        distinct component in the same message rejects the turn with an
        ``error`` event instead of picking one.
        """
        try:
            last_content = messages[-1].get("content", "") if messages else ""
            addressed = await self._resolve_addressed(last_content)
            tools = await self._tool_specs(addressed)
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
                    if self._debug:
                        yield {"type": "tool_call", "name": name, "arguments": arguments}
                    result = await self._call_tool(name, arguments, addressed)
                    if self._debug:
                        yield {"type": "tool_result", "name": name, "result": result}
                    history.append({"role": "tool", "content": result})
            yield {"type": "error", "message": "tool-call limit reached"}
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}

    async def _resolve_addressed(self, text: str) -> dict | None:
        """Resolve the ``@handle``(s) in ``text`` that name a known component.

        Returns that component's ``list_components()`` node (with ``id``,
        ``label``, ``type``, ...), or ``None`` if there's no mention, no MCP
        access, or no mention matches a known component id — addressing is
        opt-in, so an unrecognized ``@handle`` is just left as plain text.

        Raises:
            ValueError: If the message addresses more than one distinct
                component — a turn can only be scoped to one at a time.
        """
        if self._mcp is None:
            return None
        handles = {match.group(1).lower() for match in _MENTION_RE.finditer(text)}
        if not handles:
            return None
        by_id = {node["id"]: node for node in await self._list_components()}
        matched_ids = sorted(handles & by_id.keys())
        if len(matched_ids) > 1:
            mentions = ", ".join(f"@{component_id}" for component_id in matched_ids)
            raise ValueError(
                f"multiple components addressed in one message ({mentions}) — "
                "address one component per message"
            )
        return by_id[matched_ids[0]] if matched_ids else None

    async def _list_components(self) -> list[dict]:
        """Fetch ``list_components()``'s nodes directly, for internal @-resolution."""
        result = await self._mcp.call_tool("list_components", {})
        structured = result[1] if isinstance(result, tuple) else result
        if isinstance(structured, dict):
            structured = structured.get("result", [])
        return structured if isinstance(structured, list) else []

    @staticmethod
    def _tool_allowed(name: str, addressed: dict) -> bool:
        """Whether ``name`` may be offered/called while a turn addresses ``addressed``."""
        if name.startswith(f"{addressed['id']}."):
            return True
        if name == "query_repository":
            return addressed.get("type") == "repository"
        return name in _LIFECYCLE_TOOLS

    async def _tool_specs(self, addressed: dict | None) -> list[dict] | None:
        if self._mcp is None:
            return None
        tools = await self._mcp.list_tools()
        if addressed is not None:
            tools = [tool for tool in tools if self._tool_allowed(tool.name, addressed)]
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

    async def _call_tool(self, name: str, arguments: dict, addressed: dict | None) -> str:
        if self._mcp is None:
            return "error: no tools available (mcp=True was not passed to Project.start())"
        if addressed is not None:
            if not self._tool_allowed(name, addressed):
                return f"error: tool {name!r} is not available while addressing {addressed['id']!r}"
            if name == "query_repository":
                arguments = {**arguments, "repo_id": addressed["id"]}
            elif name in _LIFECYCLE_TOOLS:
                arguments = {**arguments, "name": addressed["label"]}
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
