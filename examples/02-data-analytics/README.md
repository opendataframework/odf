# 02 — Data Analytics

The project shape `odf init --template data-analytics` scaffolds: a
`Readings` repository backed by `SQLite`, and a `SummarizeReadings`
`@Analytics @Task` that aggregates the table and writes the result to
`reports/summary.json` instead of back into the database. No new core
concept over `opendataframework`'s `examples/04-task-and-pipeline/` and
`examples/05-layer/` — this example is about the *layout*: a
`reports/` folder for derived, human-readable artifacts, kept separate
from raw data.

## Structure

```
02-data-analytics/
├── config.toml          # SQLite path + the report's output path
├── main.py               # alternative to `odf run` — seeds readings, runs the report Task, then boots the UI
├── app/
│   ├── __init__.py       # imports all modules so decorators register at startup
│   ├── entities.py       # Reading — @Entity @dataclass
│   ├── storages.py        # SQLite — @Storage @Component
│   ├── repositories.py   # Readings — @Storage @Repository(Reading)
│   └── analytics.py      # SummarizeReadings — @Analytics @Task
└── reports/              # written by SummarizeReadings, not checked in
```

## Run it

```bash
cd examples/02-data-analytics
odf run
```

`odf run` is a thin CLI wrapper around three steps: import `app` so
`Readings`/`SQLite`/`SummarizeReadings` register, build a `Server` from
`config.toml`, and `start(ui=True)`. `main.py` does the same three steps
directly in Python — same UI, same SQLite-backed `Readings` — to show that
booting it isn't tied to the CLI, then goes further: it seeds three
readings across two sensors and runs `SummarizeReadings` headlessly via
`server.context.get(...)` before the UI even starts — `Server` wraps a
plain `opendataframework.Project` rather than subclassing it, and
`.context` is delegated straight through, so `server.context` here *is*
the wrapped `Project`'s `Context`:

```bash
python main.py
```

```
Report: {'reading_count': 3, 'average_celsius_by_sensor': {'kitchen': 21.75, 'garage': 17.25}}
```

That's the same dict written to `reports/summary.json`. Readings live in
SQLite, not in-memory, so whatever `main.py` seeded is still there once you
open the UI — `Readings` shows up as a node on the topology graph, already
populated. Re-running `SummarizeReadings` from the UI (or via the MCP
`execute_task` tool with `--mcp`) recomputes the same report from whatever
is in `app.db` at the time.
