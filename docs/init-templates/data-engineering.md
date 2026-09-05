# `data-engineering` template

```bash
odf init my-project --template data-engineering
```

[`default`](default.md) (`Item`/`Items`/`SQLite`) plus two `@Task`s
composed by a `@Pipeline`: `SeedItems` ingests `data/raw/` into the
repository, `ExportItemsSummary` aggregates it back out to
`data/processed/` — a raw-to-processed ETL flow expressed with ODF's own
`Task`/`Pipeline` abstractions instead of a separate orchestration tool.

## Layout

```text
my-project/
├── config.toml
├── app/
│   ├── __init__.py
│   ├── entities.py       # Item
│   ├── storages.py       # SQLite
│   ├── repositories.py   # Items(SQLite)
│   ├── tasks.py          # SeedItems, ExportItemsSummary
│   └── pipelines.py      # SetupPipeline
└── data/
    ├── raw/
    │   └── items.csv      # source data — read, never edited in place
    └── processed/         # starts empty — ExportItemsSummary writes here
```

## What's added

```python
# app/tasks.py
@Task
class SeedItems:
    def execute(self) -> int:
        if self.items.all():
            return 0  # dedup guard — skip if already seeded
        ...  # reads data/raw/items.csv, calls items.save(...) per row


@Task
class ExportItemsSummary:
    def execute(self) -> str: ...  # aggregates Items, writes data/processed/items_summary.json
```

```python
# app/pipelines.py
@Pipeline
class SetupPipeline:
    def __init__(self, seed: SeedItems, export: ExportItemsSummary) -> None:
        self.seed = seed
        self.export = export

    def execute(self) -> None:
        self.seed.execute()
        self.export.execute()
```

`SetupPipeline` composes both tasks by declaring them as constructor
dependencies — the `Context` resolves and injects them, the same way it
would any other `@Component`.

## Run it

<!-- termynal -->

```
$ odf run
UI running at http://127.0.0.1:4747
```

Trigger `SetupPipeline` from the UI (or `execute_task` over MCP), then
check `data/processed/items_summary.json`.
