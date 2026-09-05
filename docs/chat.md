# Chat

An optional chat window in the UI, backed by a local [Ollama](https://ollama.com)
model. It can act on the project by calling the same tools the MCP server
(`odf.mcp.server.McpServer`) exposes — start/stop components, execute tasks
and pipelines, inspect logs — so you can drive the project conversationally
instead of clicking through the UI.

Like the UI and MCP server, chat is not a DI-managed `Component` —
it is started directly by `Server.start()` and requires an optional extra.

## Enabling

```bash
pip install odf[ui,mcp,chat]
```

```python
server = Server.from_config("config.toml")
server.start(ui=True, mcp=True, chat=True)
```

`chat=True` requires `ui=True` — the chat window is served by the topology
UI, on the same host/port, not a separate server. Passing `chat=True`
without `ui=True` raises `ValueError`.

`mcp=True` is optional but recommended: without it, chat still answers
questions as a plain LLM, but has no tool-calling access to the project (no
starting/stopping components, no running tasks).

## Configuration

Connection parameters for the local Ollama daemon come from `[project.chat]`
in config — not from a `start()` kwarg, since these are the kind of
per-environment values that belong in `config.toml`:

```toml
[project.chat]
model = "gpt-oss:20b"
ollama-host = "http://localhost:11434"
```

| Key | Default | Description |
|---|---|---|
| `model` | `"gpt-oss"` | Ollama model name. Must already be pulled (`ollama pull gpt-oss:20b`). |
| `ollama-host` | `"http://localhost:11434"` | URL of the running Ollama daemon (`ollama serve`). |

## How tool-calling works

When `mcp=True` is also passed, `Server.start()` hands the chat engine a
reference to the same `FastMCP` instance the MCP server serves over
streamable HTTP (`McpServer.mcp`) — tool definitions and execution are
shared in-process, not duplicated. On each turn, the model is offered the
current tool list (`list_components`, `start_component`, `stop_component`,
`execute_task`, `component_logs`); if it requests a tool call, the chat
window shows what was called and its result inline, then feeds the result
back to the model for a follow-up reply.

## Prerequisites

1. Install and run [Ollama](https://ollama.com) locally: `ollama serve`.
2. Pull a tool-calling-capable model: `ollama pull gpt-oss:20b`.
3. Start the project with `chat=True` (and `mcp=True` for tool access).

If the Ollama daemon is unreachable, the chat window shows an inline error
rather than hanging.
