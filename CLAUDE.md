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

# Lint (same hooks as CI); run inside the project's environment so the
# hooks pinned to python3.14 can find it
poetry run pre-commit run --all-files

# Try the CLI
poetry run odf --help
poetry run odf init --template default /tmp/scratch-project
poetry run odf run
```

Requires Python >=3.14, managed with Poetry. `pyproject.toml` depends on
`opendataframework (>=0.3.0,<0.4.0)` by version, resolved from PyPI. When
developing both repos side by side against unreleased `opendataframework`
changes, temporarily override the dependency to a local path/git source —
and revert that override (and regenerate `poetry.lock`) before releasing a
new version of `odf`.

## Architecture

This package wraps `opendataframework.Project` with everything that
needs a third-party dependency:

| Subpackage/module | Role | Pulls in |
|---|---|---|
| `server.py` | `Server` — composes an `opendataframework.Project` and adds `start(ui=, mcp=, chat=)` orchestration on top | (imports the rest of this table lazily) |
| `cli.py`, `scaffold.py`, `templates/` | `odf init`/`odf run` CLI | `typer`, `rich` |
| `mcp/server.py` | MCP server exposing component lifecycle + task/pipeline execution + repository data queries as tools | `mcp`, `uvicorn` |
| `ui/server.py`, `ui/topology.py`, `ui/keys.py`, `ui/data.py`, `ui/arguments.py`, `ui/layout.py`, `ui/extensions.py`, `ui/themes.py` | UI dev server | `fastapi`, `uvicorn` |
| `ui/static/` | The UI itself: `index.html` + `app.js` shared by every theme, `icons/` holding the built-in topology icons (one file per picker group, plus `shared.js`), and `themes/<name>/` holding each theme's `theme.css`, `favicon.svg` and optional `theme.js` | (Leaflet from a CDN; no build step) |
| `chat/engine.py` | Chat window backing a `Server`'s UI | `ollama` |

Every component is addressed by its upstream key, `<namespace>.<name>`
(`context.key(cls)`): it is the topology node id, the argument to every
`Context` call and MCP tool, the prefix of a component's MCP tools, and what
chat's `@` mentions. Never address one by `cls.__name__` or
`kebab(cls.__name__)`. The key's namespace is the one the object was gathered
from, so a node's type and its HTTP route collection come from its execution
type instead (`ui/keys.py`): a `@Task` registered as `loader` is
`/api/tasks/loader`, whatever its key.

UI markup and behavior changes go in the shared `ui/static/index.html` and
`ui/static/app.js`, never in a theme. A theme only restyles: all of its CSS
lives in its own `theme.css` (themes share no stylesheet), and canvas
drawing CSS can't express goes in its `theme.js` through
`ODF.registerTheme()`, overriding `THEME_STYLE` in `app.js`. `app.js` must
stay a classic script, since custom icon scripts use its top-level names as
globals.

`app.js` holds only the eight exec-type default icons. Every other built-in
icon goes in its group's file under `ui/static/icons/` (a new group is a new
file plus a `<script>` tag in `index.html`, after `icons/shared.js`), where
it registers through `ODF.registerIcon` with that file's `group` and draws
with the `ODF.iconKit` helpers from `icons/shared.js`. Icon keys are stored
in projects' `layout.json`, so renaming one resets it to the type default
there.

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

## Commit messages and releases

Follow `CONTRIBUTING.md`, including its branching and release process
(PRs into the current `release/<version>` branch, not `main`; PyPI
publishing is manual for now). In particular, never add Claude or other model
references (no "Generated with …" line, no `Co-Authored-By` trailer) or
external links to commit messages.

## Relationship to `opendataframework`

- **`opendataframework`** (sibling repo, dependency) — the core framework.
  See its `CLAUDE.md` for abstractions/lifecycle/DI details. This repo
  should never duplicate those concepts locally.

## Docs

`docs/` holds this package's own mkdocs-material narrative documentation:
`docs/cli.md` (`cli.py`) and `docs/init-templates/`, `docs/server.md`
(`server.py`), `docs/ui.md` (`ui/`, including the `config.toml` reference
for every `[ui]`/`[project]` key `Server.start()` reads), `docs/mcp.md`
(`mcp/server.py`), `docs/chat.md` (`chat/engine.py`), plus `docs/index.md`
(an overview linking to each) and `docs/examples.md`. Built with
`mkdocs.yml` at the repo root and deployed to GitHub Pages by
`.github/workflows/docs.yml` when a version tag is pushed — only for the
highest tag, so tagging an older patch doesn't overwrite the site
(`https://opendataframework.github.io/odf/`). It links out to the sibling
`opendataframework` package's own separately-deployed docs site
(`https://opendataframework.github.io/opendataframework/`) rather than
bundling that content here — each package's docs redeploy independently,
on its own push, with no cross-repo CI needed. Changing this package's CLI
flags, MCP tool surface, or UI behavior should come with a matching update
to the relevant page here in the same change, since there's no separate
docs repo to flag it to anymore. User-visible changes also get an entry in
`docs/release-notes.md` under the in-progress version (one entry per feature,
not per commit; format mirrors `opendataframework`'s release notes).

## Examples

`examples/` has 20 examples. `01-table-view/` (a repository with no
`data_view()` at all, so the UI falls back to the implicit default table)
and `06-location-view/` (`data_view() -> LocationView` overriding that
default with a map) are the two ends of the `data_view()` concept.
`02-data-analytics/`, `03-data-science/`, `04-data-engineering/`,
`05-research/` were moved here from `opendataframework/examples/` (they
each mirror one `odf init --template <name>` scaffold layout, so they
belong with the CLI that describes them, not the core package).
`07-streaming-video-view/` through `16-mcp-chat/` are the UI-only surface
(streaming/video/audio/image/document/timeseries views, chart, chart via
Plotly, MCP + chat) ported from the original monorepo's `demo/` project.
`17-custom-icon/`, `18-custom-mcp-tool/`, `19-agent/` (an `@Agent`
invoked from the UI, over MCP and from chat) and `20-function/` (plain
functions adopted with `@Function`) were added here since. Treat new examples here as small and focused, one concept each, matching
`opendataframework/examples/`'s style rather than `demo/`'s
everything-at-once approach.
