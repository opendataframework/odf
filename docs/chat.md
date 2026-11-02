# Chat

An optional chat window in the UI, backed by a local [Ollama](https://ollama.com)
model. It can act on the project by calling the same tools the MCP server
(see [MCP Server](mcp.md)) exposes — start/stop services, execute tasks
and pipelines, query repositories, inspect logs — so you can drive the project conversationally
instead of clicking through the UI.

Like the UI and MCP server, chat is not a DI-managed `Component` —
it is started directly by `Server.start()` and requires an optional extra.

## Enabling

```bash
pip install "odf[ui,mcp,chat]"
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
debug = false
context-length = 32768
```

| Key | Default | Description |
|---|---|---|
| `model` | `"gpt-oss:20b"` | Ollama model name. Must already be pulled (`ollama pull gpt-oss:20b`). |
| `ollama-host` | `"http://localhost:11434"` | URL of the running Ollama daemon (`ollama serve`). |
| `debug` | `false` | Show tool-call/tool-result debug info inline in the chat window. |
| `context-length` | Ollama's default | The model's context window in tokens, sent as Ollama's `num_ctx`. Raise it once a project has many tools (see below). |
| `system-prompt` | built in | What the model is told first in a turn that has tools (see below). `""` sends none. |

### Context length

Every turn offers the model every tool's name, description and argument
schema, and `list_components` returns every node of the project. In a project
with a couple of dozen components that's over ten thousand tokens, and
when it no longer fits Ollama's default window, the oldest part of the turn
(the question itself) falls out of it, and the model answers something else.
Set `context-length` to a window that holds it; 32768 is plenty for a few
dozen tools, at the cost of more memory on the Ollama host.

### System prompt

Unless the conversation brings its own system message, a turn with tools
starts with a short one: answer from what the tools returned in this
conversation, and say so when they don't show something, rather than adding
records or activity they didn't show; answer in plain words or a short
table, not the tools' raw output; and start, stop, run, invoke or import
something only when asked. Small local models need saying it. Set
`system-prompt` to replace it with your own, such as one naming the
project's domain.

## How tool-calling works

When `mcp=True` is also passed, `Server.start()` hands the chat engine a
reference to the same `FastMCP` instance the MCP server serves over
streamable HTTP (`McpServer.mcp`) — tool definitions and execution are
shared in-process, not duplicated. On each turn, the model is offered the
current tool list — the seven [fixed tools](mcp.md#tools) (`list_components`,
`query_repository`, `start_component`, `stop_component`, `execute_task` for a
task or pipeline, `component_logs`, `recent_notifications`) plus, for every resolved component that exposes its own
MCP tools (prefixed by its key, `<namespace>.<name>.<tool>`), that
component's own tools, for every resolved `@Agent` its `<key>.invoke` tool, and
for every resolved `@Function` its `<key>.call` tool;
these are dynamic per project, so they aren't enumerated here by name. If
the model requests a tool call, it's always executed and its result fed
back to the model for a follow-up reply; the chat window additionally
shows what was called and its result inline only when `[project.chat]`'s
`debug` is `true`.

A model sometimes gets a tool's name slightly wrong: `function_margins` or
`margins_call` for `function.margins.call`. Ignoring case, dots, dashes and
underscores, a name that matches exactly one tool, as the whole name, its
start or a part of it, calls that tool. Otherwise the model is told there's
no such tool, along with the closest names, and can try again.

## Addressing a component with `@`

Mentioning a component's key, `@<namespace>.<name>`, anywhere in a message
scopes that turn's tool access to just that component — its own exposed
tools (for an `@Agent`, its `<key>.invoke`, and for an `@Function`, its
`<key>.call`), its own repository data (if it's a `Repository`), and
its own lifecycle actions and what it announced
(`start_component`/`stop_component`/`execute_task`/`component_logs`/`recent_notifications`,
forced to that component regardless of what the model passes) — instead
of offering every tool in the project. This is useful once a project has
several repositories/services: instead of the model guessing which
repository a data question is about, `@repository.users how many rows are
there?` scopes `query_repository` to just that repository's data, and
`@agent.librarian anything by Herbert?` hands the question to the `Librarian`
agent's `agent.librarian.invoke`, with the arguments the model fills in from
the agent's schema. `@function.load-data load data.csv` does the same through
`function.load-data.call`.

The key is the node id the topology graph uses, and the prefix of the
component's own tools (e.g. a `@Task class MetricsFetcher` is addressed as
`@task.metrics-fetcher`). Always writing the namespace keeps a mention
unambiguous as a project grows: a `@Task class Loader` and an
`@Agent class Loader` are `@task.loader` and `@agent.loader`. The chat input
autocompletes the key as you type `@`, matching the name or class name too. A
mention that doesn't match any resolved component's key, such as a bare
`@loader`, is just left as plain text — the turn falls back to the full, unscoped tool
set. A message can only address one component at a time — mentioning
more than one distinct component's key in the same message rejects the
turn with an inline error instead of guessing which one you meant.

## Prerequisites

1. Install and run [Ollama](https://ollama.com) locally: `ollama serve`.
2. Pull a tool-calling-capable model: `ollama pull gpt-oss:20b`.
3. Start the project with `chat=True` (and `mcp=True` for tool access).

If the Ollama daemon is unreachable, the chat window shows an inline error
rather than hanging.
