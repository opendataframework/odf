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
The left sidebar collapses to an icon rail to give the canvas more
room; its collapsed/expanded state is remembered per browser.
Repositories can declare a `data_view()` to pick how their data renders
(table, map, timeseries, streaming video/audio, ...) instead of the
default table.

A repository whose view shows content (an image, video, audio or document
view) can also implement
[`content_metadata(entity)`](https://opendataframework.github.io/opendataframework/view/)
to name and type each record's content. A declared `content_type` is served
instead of the type worked out from the bytes, as long as it fits the view:
an image view only takes an image type, never SVG, and a document is still
only ever served as a PDF, plain text or a download. A declared `filename`
labels the record's card and its caption, is sent as `Content-Disposition`,
and names the file the **Download** action saves. Records list it, under a
`$content` key, so the UI has it without a request per record. See
[`examples/12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view).

```python
server.start(ui=True)
print(server.ui_url)  # http://127.0.0.1:4747
```

Each node is identified by its `opendataframework` key, `<namespace>.<name>`
(`task.load-job`, `agent.librarian`), so two classes with the same name in
different namespaces stay apart. The UI's HTTP API serves each execution type
as its own collection, by registered name:

| Route | For |
|---|---|
| `GET /api/{collection}/{name}/logs` | any component (`components`, `repositories`, `services`, `tasks`, `pipelines`, `agents`, `functions`) |
| `GET /api/{collection}/{name}/details`, `.../chart` | a component implementing `details()` / `chart()` |
| `POST /api/services/{name}/start`, `.../stop` | a `@Service` |
| `POST /api/tasks/{name}/execute`, `/api/pipelines/{name}/execute` | a `@Task` / `@Pipeline` |
| `GET /api/agents/{name}/parameters`, `POST .../invoke` | an `@Agent` |
| `GET /api/functions/{name}/parameters`, `POST .../call` | an `@Function` |
| `/api/repositories/{name}/records`, `.../stream`, ... | a `@Repository`'s data |

An action that doesn't apply to a kind has no route, so it answers `404`.

An `@Agent`'s node has an **Invoke** action, and an `@Function`'s node a
**Call** action. Each opens a form with one field per argument, prefilled with
the defaults, and shows the result under it. An agent's arguments are those of
its `invoke()`. A function's are its own, less the parameters the `Context`
injects. A `str`, number or `bool` argument gets an input of that kind, and
any other type a JSON field. Values are converted to the annotated types
before `context.call()` makes the call, and a value that doesn't fit is
reported under the form without making it. See
[`examples/19-agent`](https://github.com/opendataframework/odf/tree/main/examples/19-agent).

A node's icon and color can be changed from its "Customize" popover, which
lists the built-in isometric icons by group (devices, buildings, charts,
research, ML, shop). Icons and colors can be extended beyond the built-in
set via `[ui] icon-scripts` / `[ui.colors]` in config, or by packages
registering into `odf.ui.extensions`. The favicon, header logo, and "ODF" brand label
can likewise be overridden with `[ui] favicon` / `[ui] logo` / `[ui] brand`
(see
[`examples/17-custom-icon`](https://github.com/opendataframework/odf/tree/main/examples/17-custom-icon)).

### Choosing what the topology shows

By default the topology shows every component and every connection between
them. The `[ui.topology]` table in config narrows that:

```toml
[ui.topology]
connections = false                  # default true: draw links between components
config = false                       # default true: show the Config node
repositories = ["readings"]          # only these repositories
tasks = ["seed-readings"]            # only these tasks
agents = []                          # no agents
functions = ["load-data"]            # only these functions
components = []                      # no plain components (e.g. a Storage component)
```

`repositories`, `services`, `tasks`, `pipelines`, `agents`, `functions` and `components` each take
registered names, the name part of each key (`seed-readings` for
`task.seed-readings`), in any casing. A kind without a list shows all of its
components; a kind with a list shows only the listed ones, and an empty list
hides the kind. A component added later to a kind that has a list stays hidden
until it is added to that list. A `Storage` component counts as a plain
`component`.

When a component is hidden, the components that depend on it are linked to
whatever it depends on, so the remaining graph keeps its shape. The remaining
nodes are laid out again without gaps. A node whose saved grid position is
taken by another node moves to the nearest free row in its column; those
adjustments are not written to the layout file. Hidden components keep
running and stay available through MCP and chat; only the topology view
changes. Unknown keys and values of the wrong type raise a `ValueError` when
the UI starts, and a listed name that matches no component produces a warning.
See
[`examples/04-data-engineering`](https://github.com/opendataframework/odf/tree/main/examples/04-data-engineering).

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
start/stop, task/pipeline execution, agent invocation, log inspection — as
MCP tools for any MCP-speaking client. Each tool takes a component's key,
`<namespace>.<name>`, as its `key` argument (`start_component(key="service.postgres")`),
and `list_components` returns it as each entry's `id`. Any resolved component can
contribute its own tools alongside these by implementing
`opendataframework.component.McpToolsProtocol`'s `mcp_tools()`; they are prefixed
by the component's key, so a `@Component class StockRoom`'s `low_stock` tool is
`component.stock-room.low_stock`.

```python
server.start(mcp=True)
print(server.mcp_url)  # http://127.0.0.1:4748/mcp
```

An `McpTool` needs a non-empty `description` and a fully typed handler: every
parameter annotated, a return annotation (`-> None` counts), no
`*args`/`**kwargs`, a method or function rather than a lambda, and no
`from __future__ import annotations` in its module. The MCP server passes the
description and the handler's signature to the client as the tool's
description and input schema, which is all a model sees of the tool.
`opendataframework` raises when a tool doesn't meet this, and `odf run`
reports it as a start-up error. See
[`examples/18-custom-mcp-tool`](https://github.com/opendataframework/odf/tree/main/examples/18-custom-mcp-tool).

Each resolved `@Agent` becomes its own tool, `<key>.invoke` (`agent.librarian.invoke`), prefixed
like a component's own tools. Its input schema is `invoke()`'s signature and
its description is the first paragraph of the class docstring, so a client
is told what the agent takes rather than guessing at a generic `arguments`
object. The tool calls the agent through `context.call()`, which logs the call
to the agent's log. `list_components` lists agents with the type `agent`. An
argument that can't be passed by keyword (positional-only, `*args`,
`**kwargs`) is left out of the schema. See
[`examples/19-agent`](https://github.com/opendataframework/odf/tree/main/examples/19-agent).

Each resolved `@Function` becomes its own tool the same way, `<key>.call`
(`function.load-data.call`). Its input schema is the function's signature,
less the parameters the `Context` injects, and its description is the first
paragraph of the function's docstring. `list_components` lists functions with
the type `function`, and gives every entry a `verb`, `invoke` or `call`, when
it has one of these tools. See
[`examples/20-function`](https://github.com/opendataframework/odf/tree/main/examples/20-function).

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
