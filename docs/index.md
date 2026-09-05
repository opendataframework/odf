# Open Data Framework (`odf`)

Open Data Framework (ODF) is a Python framework for building data
applications — small services that read, transform, and serve data —
without the usual boilerplate. You write your data model and logic as
plain Python classes; the framework wires them together and runs them.
This package, `odf`, is the toolbelt around that: a CLI to scaffold and
run projects, a UI to see and drive what's running, an MCP server so AI
tools can act on your project too, and a chat window to talk to it
directly.

!!! info "Looking for the core abstractions?"
    `Entity`, `Repository`, `Component`, `Service`, `Task`, `Pipeline`,
    `Context`, `Project`, and `Config` all live in the sibling
    [`opendataframework`](https://opendataframework.github.io/opendataframework/)
    package, which this one depends on. This site covers the CLI, UI,
    MCP server, and chat only.

## Install

```bash
pip install odf              # CLI + scaffolding only
pip install odf[ui]           # + UI dev server
pip install odf[mcp]          # + MCP server
pip install odf[chat]         # + chat window (requires [ui])
```

## CLI

Scaffold a new project:

```bash
odf init --template default my-project
```

Available templates: `default`, `data-analytics`, `data-engineering`,
`data-science`, `research` — each scaffolds a `config.toml` and folder
layout tailored to that use case. See [CLI](cli.md) for the full flag
reference.

Run a project, optionally with the UI / MCP server / chat:

```bash
odf run
odf run --ui --mcp --chat
```

## Server

`odf.server.Server` wraps an `opendataframework.Project` and is what
`odf run` boots under the hood — use it directly to run a project from
Python instead of the CLI (embedded in a larger app, a test fixture, a
notebook, ...). See [Server](server.md) for a full walkthrough, including
what the `app` module `start()` imports by default is expected to look
like.

```python
server = Server.from_config("config.toml")
server.start(ui=True)
server.wait()  # blocks until Ctrl+C/SIGTERM
```

## UI

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
into `odf.ui.extensions`. The favicon, header logo, and "ODF" brand label
can likewise be overridden with `[ui] favicon` / `[ui] logo` / `[ui] brand`
(see
[`examples/17-custom-icon`](https://github.com/opendataframework/odf/tree/main/examples/17-custom-icon)).

!!! tip "This is the actual UI, live — not a screenshot"
    Pointed at a static snapshot of
    [`examples/01-table-view`](https://github.com/opendataframework/odf/tree/main/examples/01-table-view),
    the smallest example in the repo (one `@Storage @Repository`, no
    other components). Only the topology graph and data view are shown
    here. Click the `Books` node, then **View**, to see its records as a
    table; it's a static snapshot with no server behind it, so edits
    (Add/Save/Delete) won't persist.

<iframe class="topology-demo-frame" src="assets/topology-demo/index.html" title="ODF UI — live topology demo"></iframe>

## MCP Server

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

## Chat

An optional chat window added to the UI, backed by a local
Ollama model. Requires `ui=True`; if `mcp=True` is also passed, the chat
model gets tool-calling access to the same actions exposed as MCP tools.
See [Chat](chat.md) for the full walkthrough.

```python
server.start(ui=True, mcp=True, chat=True)
```

## Examples

See [Examples](examples.md) for the UI-server surface built on top of
`opendataframework`, including the four that mirror `odf init --template`
layouts.
