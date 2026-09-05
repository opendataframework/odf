# 04 — Data Engineering

The project shape `odf init --template data-engineering` scaffolds: a
raw-to-processed ETL flow over `data/raw/` and `data/processed/`.
`SeedReadings` ingests `data/raw/readings.csv` into the `Readings`
repository (idempotently — it skips ingestion if rows already exist, so
re-running against a persisted `app.db` doesn't double-seed); it feeds an
independent `ExportReadingsSummary` Task that aggregates the table and
writes `data/processed/readings_summary.json`. `SetupPipeline` composes
both — same shape as `opendataframework`'s `examples/04-task-and-pipeline/`,
applied to the raw/processed data-folder convention instead of an
in-memory buffer.

## Structure

```
04-data-engineering/
├── config.toml                    # SQLite path
├── main.py                         # entry point — runs SetupPipeline
├── app/
│   ├── __init__.py                 # imports all modules so decorators register at startup
│   ├── entities.py                 # Reading — @Entity @dataclass
│   ├── storages.py                  # SQLite — @Storage @Component
│   ├── repositories.py             # Readings — @Storage @Repository(Reading)
│   ├── tasks.py                     # SeedReadings, ExportReadingsSummary — @Task
│   └── pipelines.py                # SetupPipeline — @Pipeline
└── data/
    ├── raw/readings.csv            # source data, never edited in place
    └── processed/                  # written by ExportReadingsSummary, not checked in
```

## Run it

```bash
cd examples/04-data-engineering
python main.py
```

```
Seeded 5 reading(s).
Exported summary to data/processed/readings_summary.json.
```

Run it again and `SeedReadings` skips ingestion — `app.db` already has the
rows — while `ExportReadingsSummary` still re-writes the summary from
whatever `Readings` currently holds.

Or start the dev UI and run `SetupPipeline` from there (or via the MCP
`execute_task` tool with `--mcp`):

```bash
odf run
```
