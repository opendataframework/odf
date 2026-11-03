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

# Matches an `@<namespace>.<name>` mention of a component's key anywhere in a
# message, as long as the `@` is preceded by whitespace or the start of the
# string (so `user@example.com` doesn't get mistaken for one). Every dot must
# be followed by a name character, so a sentence's closing period is left out.
_MENTION_RE = re.compile(r"(?:^|\s)@([A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9][A-Za-z0-9-]*)+)")

# Fixed lifecycle tools that stay available, scoped to just the addressed
# component, when a message addresses one (see `_tool_allowed`).
_LIFECYCLE_TOOLS = frozenset(
    {
        "start_component",
        "stop_component",
        "execute_task",
        "component_logs",
        "recent_notifications",
    }
)

# Sent first in a turn that has tools, unless the conversation brings its own
# system message: without it, a small model fills out an answer with records
# and activity it never looked up, and runs tools that change things to answer
# a question.
SYSTEM_PROMPT = (
    "You answer questions about a running project, using its tools to look things up. "
    "Say only what the tools returned in this conversation: never add records, numbers "
    "or activity they didn't show, and if they don't show something, say so. "
    "Answer in plain words, or a short table, not the tools' raw output. "
    "Only start, stop, run, invoke or import something when the user asks for that."
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
        context_length: The model's context window, in tokens (Ollama's
            ``num_ctx``). ``None`` leaves Ollama's default, which can be too
            small for a project with many tools: the turn's question falls
            out of the window and the model answers something else.
        system_prompt: What the model is told first in a turn that has
            tools, unless the conversation has its own system message.
            ``None`` sends ``SYSTEM_PROMPT``; ``""`` sends none.

    A tool name the model gets slightly wrong (``function_margins`` or
    ``margins_call`` for ``function.margins.call``) is resolved when exactly
    one tool matches it once dots, dashes and underscores are ignored, as the
    whole name, its start or a part of it; otherwise the model is told the
    closest names, so it can correct itself.
    """

    def __init__(
        self,
        model: str,
        host: str,
        mcp: FastMCP | None = None,
        debug: bool = False,
        context_length: int | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.model = model
        self._client = AsyncClient(host=host)
        self._mcp = mcp
        self._debug = debug
        self._options = {"num_ctx": int(context_length)} if context_length else None
        self._system = SYSTEM_PROMPT if system_prompt is None else system_prompt

    async def stream(self, messages: list[dict], context: str | None = None) -> AsyncIterator[dict]:
        """Yield ``{"type": ..., ...}`` events for one chat turn.

        ``context`` is what the turn is about, sent as a system message after
        the system prompt and before the conversation: a channel's thread
        the user asks in (see ``odf.ui.conversations.thread_context``), say.

        Event types: ``token`` (a chunk of assistant text), ``tool_call``
        (about to invoke an MCP tool), ``tool_result`` (its outcome), and
        ``error`` (the turn failed or was cut short) — the caller (an HTTP
        route) just forwards each event to the client, it never raises.
        ``tool_call``/``tool_result`` are only yielded when ``debug=True``
        was passed to the constructor; the tool call itself still always
        executes and its result is always fed back to the model.

        If the latest user message addresses a component by its key
        (e.g. ``"@service.postgres how many rows..."``), the turn's tool access is
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
            if context:
                history.insert(0, {"role": "system", "content": context})
            # Only a system message the conversation brings replaces the
            # prompt; the turn's context goes after it.
            if (
                tools is not None
                and self._system
                and not any(m.get("role") == "system" for m in messages)
            ):
                history.insert(0, {"role": "system", "content": self._system})
            for _ in range(_MAX_TOOL_ROUNDTRIPS):
                content = ""
                tool_calls: list = []
                extra = {"options": self._options} if self._options else {}
                async for chunk in await self._client.chat(
                    model=self.model, messages=history, tools=tools, stream=True, **extra
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
        """Whether ``name`` may be offered/called while a turn addresses ``addressed``.

        The addressed component's own ``<id>.``-prefixed tools stay available:
        its ``mcp_tools()``, an agent's ``<id>.invoke`` and a function's
        ``<id>.call``.
        """
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
        names = [tool.name for tool in await self._mcp.list_tools()]
        if name not in names:
            matches = _near(name, names)
            if len(matches) != 1:
                hint = f"; did you mean {' or '.join(repr(m) for m in matches)}?" if matches else ""
                return f"error: there is no tool {name!r}{hint}"
            name = matches[0]
        if addressed is not None:
            if not self._tool_allowed(name, addressed):
                return f"error: tool {name!r} is not available while addressing {addressed['id']!r}"
            if name == "query_repository" or name in _LIFECYCLE_TOOLS:
                arguments = {**arguments, "key": addressed["id"]}
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


def _squash(name: str) -> str:
    """Return a tool name with only its letters and digits, lowercased."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _near(name: str, names: list[str]) -> list[str]:
    """Return the tools ``name`` could mean, once squashed: the same, then starting, then within.

    ``function_margins`` squashes to the start of ``function.margins.call``,
    and ``margins`` or ``margins_call`` to a part of it. The first kind of
    match that finds any wins, so an exact one beats a longer one.
    """
    squashed = _squash(name)
    if not squashed:
        return []
    for found in (
        [n for n in names if _squash(n) == squashed],
        [n for n in names if _squash(n).startswith(squashed)],
        [n for n in names if squashed in _squash(n)],
    ):
        if found:
            return found[:5]
    return []
