# Open Data Framework — CLI, UI & MCP (`odf`)

The CLI, UI server, MCP server, and chat surface for
Open Data Framework. Depends on `opendataframework` for the core abstractions (`Entity`,
`Repository`, `Component`, `Service`, `Task`, `Pipeline`, `Layer`,
`Context`, `Project`) — see that package for those.

---

# Install

```bash
pip install odf              # CLI + scaffolding only
pip install odf[ui]           # + UI dev server
pip install odf[mcp]          # + MCP server
pip install odf[chat]         # + chat window (requires [ui])
```

---

# CLI

Scaffold a new project:

```bash
odf init --template default my-project
```

Available templates: `default`, `data-analytics`, `data-engineering`,
`data-science`, `research` — each scaffolds a `config.toml` and folder
layout tailored to that use case.

Run a project, optionally with the UI / MCP server / chat:

```bash
odf run
odf run --ui --mcp --chat
```

---

# UI

A small FastAPI dev server (backgrounded, like any `Service`) that
visualizes the resolved object graph — every `Component`/`Service`/
`Repository`, grouped by `Layer`, with lifecycle actions (start/stop/
execute) available from the UI. Grid positions persist across reloads.
Repositories can declare a `data_view()` to pick how their data renders
(table, map, timeseries, streaming video/audio, ...) instead of the
default table.

```python
server.start(ui=True)
print(server.ui_url)  # http://127.0.0.1:4747
```

Icons and colors can be extended beyond the built-in isometric set via
`[ui] icon-scripts` / `[ui.colors]` in config, or by packages registering
into `odf.ui.extensions`.

---

# MCP Server

Exposes the same actions available in the UI — component
start/stop, task/pipeline execution, log inspection — as MCP tools for
any MCP-speaking client.

```python
server.start(mcp=True)
print(server.mcp_url)  # http://127.0.0.1:4748/mcp
```

New components can be added to an existing project from within an AI
chat: the MCP service knows the available component library and the
project's current structure, generates the config delta and any needed
code, and the project rebuilds.

---

# Chat

An optional chat window added to the UI, backed by a local
Ollama model. Requires `ui=True`; if `mcp=True` is also passed, the chat
model gets tool-calling access to the same actions exposed as MCP tools.

```python
server.start(ui=True, mcp=True, chat=True)
```

Connection parameters come from `[project.chat]` in config: `model`
(default `"gpt-oss"`) and `ollama-host` (default
`"http://localhost:11434"`).

---

# Examples

See [`examples/`](examples/README.md) for the UI-server surface built on
top of `opendataframework`. For the core abstractions themselves, see the
`opendataframework` package and its own `examples/`.
