# CLI

The `odf` command-line tool scaffolds new projects and runs existing ones. It is
installed alongside the framework:

<!-- termynal -->

```
$ pip install odf
---> 100%
Installed
```

```text
$ odf --help

 Usage: odf [OPTIONS] COMMAND [ARGS]...

 ODF — config-driven Python framework for building data applications.

Commands:
  init  Scaffold a new ODF project: a config.toml and an importable app package.
  run   Start a project: import its app package, load its config, and run until Ctrl+C.
```

---

## `odf init`

Scaffolds a new project — a `config.toml` and an importable `app` package that
registers components via decorators (`@Entity`, `@Component`, `@Repository`, ...).

```text
odf init [NAME] [--template/-t TEMPLATE]
```

* `NAME` — optional. If given, creates and scaffolds a new subdirectory `./NAME`.
  If omitted, scaffolds into the current directory. Either way, the target must not
  already contain files.
* `--template` / `-t` — which starting layout to scaffold. Defaults to `default`.

Every template runs immediately after `pip install odf` — no extra dependencies —
because they're all built on `odf` core plus the Python standard library
(`sqlite3` for storage).

### Templates

Every template starts from [`default`](init-templates/default.md)'s layout (one
`Entity`, one `Repository`, one `sqlite3`-backed `Storage`) and adds one
thing on top. Each has its own page with the full folder layout and what
gets registered:

| Template | Adds on top of `default` |
|---|---|
| [`default`](init-templates/default.md) | — nothing; this is the starting point itself |
| [`data-analytics`](init-templates/data-analytics.md) | An `@Analytics @Task` that aggregates repository data and writes a JSON report |
| [`data-science`](init-templates/data-science.md) | A seed CSV and a notebook that loads it into the repository |
| [`data-engineering`](init-templates/data-engineering.md) | A `SeedItems` → `ExportItemsSummary` `Pipeline` reading `data/raw/` and writing `data/processed/` |
| [`research`](init-templates/research.md) | A `RunExperiment` `Task` that loads `data/items.csv` and writes `results/summary.json`, plus a write-up stub |

`data-science`, `data-engineering`, and `data-analytics` all borrow folder names from
[cookiecutter-data-science](https://github.com/drivendataorg/cookiecutter-data-science),
the most widely used Python data-science project template — each ODF template takes
just the piece relevant to its usecase rather than the whole layout. `data-science`
and `data-engineering` use its `data/raw/` (source data, never edited in place) →
`data/processed/` (derived output) split, expressed here with ODF's own
`Task`/`Pipeline` abstractions instead of a separate orchestration tool.
`data-analytics` uses its `reports/` folder instead, since analytics is
consumption-oriented: it reads repository data and produces a report artifact
rather than ingesting one. `research` follows ["Good Enough Practices in Scientific
Computing"](https://doi.org/10.1371/journal.pcbi.1005510) (Wilson et al., 2017): a
flat `data/` for raw, read-only input, a `results/` for everything generated, and a
`doc/` for the write-up — `app/` plays the role of that layout's `src/`.

<!-- termynal -->

```
$ odf init my-pipeline --template data-engineering
---> 100%
Created 'data-engineering' project 'my-pipeline' in /path/to/my-pipeline
Next steps:
  cd my-pipeline
  odf run
```

---

## `odf run`

Starts an existing project: imports its `app` package (registering all decorated
components as a side effect), loads its config, and runs until `Ctrl+C`.

```text
odf run [CONFIG] [OPTIONS]
```

Run it from the project's root directory — the one containing `config.toml` and
the `app` package, the same layout `odf init` produces.

| Argument / Option | Default | Description |
|---|---|---|
| `CONFIG` | `config.toml` | Path to a config file or a directory of config files (see [Project](https://opendataframework.github.io/opendataframework/project/#from-a-config-directory)) |
| `--app` | `app` | Import name of the package that registers components — see [Server](server.md#the-app-module) for the same convention used when building a `Server` directly in Python |
| `--ui` / `--no-ui` | `--ui` | Start the UI |
| `--ui-host`, `--ui-port` | `127.0.0.1`, `4747` | Interface/port for the UI |
| `--mcp` / `--no-mcp` | `--no-mcp` | Start the MCP server |
| `--mcp-host`, `--mcp-port` | `127.0.0.1`, `4748` | Interface/port for the MCP server |
| `--chat` / `--no-chat` | `--no-chat` | Add a chat window to the UI (requires `--ui`) |

```text
$ odf run
UI running at http://127.0.0.1:4747
Press Ctrl+C to stop
```

The UI (`--ui`, on by default) requires the `odf[ui]` extra
(`fastapi`/`uvicorn`); pass `--no-ui` to run without it.
