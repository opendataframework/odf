# Open Data Framework CLI

Open Data Framework (ODF) is a Python framework for building data
applications — small services that read, transform, and serve data —
without the usual boilerplate. You write your data model and logic as
plain Python classes; the framework wires them together and runs them.
This package, `odf`, adds the tools for working with those projects: a
CLI to scaffold and run them, a UI to see and drive what's running, an
MCP server so AI tools can act on a project too, and a chat window to
talk to it directly.

!!! info "Looking for the core abstractions?"
    `Entity`, `Repository`, `Component`, `Service`, `Task`, `Pipeline`,
    `Agent`, `Function`, `Context`, `Project`, and `Config` all live in the sibling
    [`opendataframework`](https://opendataframework.github.io/opendataframework/)
    package, which this one depends on. This site covers the CLI, UI,
    MCP server, and chat only.

## Install

```bash
pip install odf                # CLI + scaffolding only
pip install "odf[ui]"          # + UI dev server
pip install "odf[mcp]"         # + MCP server
pip install "odf[ui,chat]"     # + chat window (served by the UI)
```

`odf run` starts the UI by default, so most projects want at least `odf[ui]`.

## Quickstart

<!-- termynal -->

```
$ pip install "odf[ui]"
---> 100%
$ odf init my-project
Created 'default' project 'my-project' in /path/to/my-project
$ cd my-project
$ odf run
UI running at http://127.0.0.1:4747
```

Open <http://127.0.0.1:4747> and select the `Items` node, then **View**, to see
its records. The scaffolded `app/` package is where your own entities,
repositories and tasks go.

## What's in the package

- **[CLI](cli.md)**: `odf init` scaffolds a project from one of six
  templates, and `odf run` starts one, optionally with the UI, MCP server and
  chat.
- **[Server](server.md)**: `odf.server.Server` wraps an
  `opendataframework.Project` and is what `odf run` boots under the hood. Use
  it directly to run a project from Python: embedded in a larger app, a test
  fixture, a notebook.
- **[UI](ui.md)**: the topology of every component, grouped by `Layer`, with
  its actions, a view of each repository's data (table, map, timeseries,
  image, video, audio, document), and labelling of that data for later
  pipelines.
- **[MCP Server](mcp.md)**: the same actions as MCP tools, plus each agent,
  function and component's own tools, for any MCP-speaking client.
- **[Chat](chat.md)**: a chat window in the UI, backed by a local Ollama
  model, that acts on the project through the MCP tools.

```python
from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True, chat=True)
server.wait()  # blocks until Ctrl+C/SIGTERM
```

## The UI, live

!!! tip "This is the actual UI, live — not a screenshot"
    Pointed at a static snapshot of
    [`examples/01-table-view`](https://github.com/opendataframework/odf/tree/main/examples/01-table-view),
    the smallest example in the repo (one `@Storage @Repository`, no
    other components). Only the topology graph and data view are shown
    here. Click the `Books` node, then **View**, to see its records as a
    table; it's a static snapshot with no server behind it, so edits
    (Add/Save/Delete) won't persist.

<iframe class="topology-demo-frame" src="assets/topology-demo/index.html" title="ODF UI — live topology demo"></iframe>

## Examples

See [Examples](examples.md) for 25 small projects, one concept each,
including the five that mirror `odf init --template` layouts.
