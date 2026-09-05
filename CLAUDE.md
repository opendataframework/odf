# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`odf` is the **CLI, MCP server, UI server, and chat** package of
Open Data Framework (ODF). It contains no core abstractions of its
own — `Entity`, `Repository`, `Component`, `Service`, `Task`, `Pipeline`,
`Layer`, `Context`, `Project`, `Config` all live in the `opendataframework`
package, which this one depends on. If a task looks like it needs a new
core concept (a new lifecycle hook, a new DI primitive, a new decorator
type), it almost certainly belongs upstream in `opendataframework`, not
here — flag that to the user rather than reimplementing it locally.

## Commands

```bash
# Install dependencies (including dev)
poetry install

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/path/to/test_file.py

# Run a single test
poetry run pytest tests/path/to/test_file.py::test_name

# Try the CLI
poetry run odf --help
poetry run odf init --template default /tmp/scratch-project
poetry run odf run
```

Requires Python >=3.14, managed with Poetry. `pyproject.toml` depends on
`opendataframework (>=0.1.0,<0.2.0)` by version — **`poetry install` will
not resolve until `opendataframework` is published somewhere reachable**
(PyPI or a private/local index), or the dependency is temporarily
overridden to a local path/git source while developing both repos side
by side. If `poetry install` fails here, check that first before
assuming something is broken in this repo.

## Architecture

This package wraps `opendataframework.Project` with everything that
needs a third-party dependency:

| Subpackage/module | Role | Pulls in |
|---|---|---|
| `server.py` | `Server` — composes an `opendataframework.Project` and adds `start(ui=, mcp=, chat=)` orchestration on top | (imports the rest of this table lazily) |
| `cli.py`, `scaffold.py`, `templates/` | `odf init`/`odf run` CLI | `typer`, `rich` |
| `mcp/server.py` | MCP server exposing component lifecycle + task/pipeline execution as tools | `mcp`, `uvicorn` |
| `ui/server.py`, `ui/topology.py`, `ui/data.py`, `ui/layout.py`, `ui/extensions.py` | UI dev server | `fastapi`, `uvicorn` |
| `chat/engine.py` | Chat window backing a `Server`'s UI | `ollama` |

None of `ui`/`mcp`/`chat` are imported eagerly by `odf/__init__.py` or
`odf/server.py` (keep it that way — `import odf` alone must not pull in
fastapi/mcp/ollama). They're activated by
`odf.server.Server.start(ui=True, mcp=True, chat=True)`, which lazily
imports them (function-local, gated behind those flags) from inside this
same package — `opendataframework.Project` itself has no knowledge of any
of this; it only exposes a plain `start()`/`stop()`.

### Core symbols come from `opendataframework`

```python
from opendataframework import Project, Component, Repository, Storage

from odf import scaffold  # sibling submodule within this package — not a core symbol
from odf.server import Server  # wraps Project with ui/mcp/chat orchestration — used by cli.py
```

Never write `from odf import Entity`/`Component`/`Repository`/etc. — those
don't exist in this package anymore. If an import like that shows up
(e.g. while adapting old code or a template), it needs to become
`from opendataframework import ...`.

### Templates (`odf init`)

`templates/{default,data-analytics,data-engineering,data-science,research}/`
are scaffolded onto disk by `scaffold.py` via
`importlib.resources.files("odf") / "templates" / template`. Each
template's `app/*.py` imports core symbols from `opendataframework`, not
`odf`. When adding a new template, follow that same import convention.

## Relationship to `opendataframework`

- **`opendataframework`** (sibling repo, dependency) — the core framework.
  See its `CLAUDE.md` for abstractions/lifecycle/DI details. This repo
  should never duplicate those concepts locally.

## Docs

`docs/` holds this package's own mkdocs-material narrative documentation:
`docs/cli.md` (this package's `cli.py`), `docs/chat.md`
(`chat/engine.py`), plus `docs/index.md`/`docs/examples.md`. The topology
UI and MCP server don't currently have their own dedicated doc pages
(check `mkdocs.yml`'s nav before assuming one exists). Built with
`mkdocs.yml` at the repo root and deployed to GitHub Pages by
`.github/workflows/docs.yml` on every push to `main`
(`https://opendataframework.github.io/odf/`). It links out to the sibling
`opendataframework` package's own separately-deployed docs site
(`https://opendataframework.github.io/opendataframework/`) rather than
bundling that content here — each package's docs redeploy independently,
on its own push, with no cross-repo CI needed. Changing this package's CLI
flags, MCP tool surface, or UI behavior should come with a matching update
to the relevant page here in the same change, since there's no separate
docs repo to flag it to anymore.

## Examples

`examples/` has 16 examples. `01-table-view/` (a repository with no
`data_view()` at all, so the UI falls back to the implicit default table)
and `06-location-view/` (`data_view() -> LocationView` overriding that
default with a map) are the two ends of the `data_view()` concept.
`02-data-analytics/`, `03-data-science/`, `04-data-engineering/`,
`05-research/` were moved here from `opendataframework/examples/` (they
each mirror one `odf init --template <name>` scaffold layout, so they
belong with the CLI that describes them, not the core package).
`07-streaming-video-view/` through `16-mcp-chat/` are the UI-only surface
(streaming/video/audio/image/document/timeseries views, chart, chart via
Plotly, MCP + chat) ported from the original monorepo's `demo/` project —
treat new examples here as small and focused, one concept each, matching
`opendataframework/examples/`'s style rather than `demo/`'s
everything-at-once approach.
