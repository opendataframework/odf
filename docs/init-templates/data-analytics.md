# `data-analytics` template

```bash
odf init my-project --template data-analytics
```

[`default`](default.md) (`Item`/`Items`/`SQLite`) plus one `@Analytics
@Task`: `SummarizeItems`, which aggregates the repository into a JSON
report. Analytics is consumption-oriented — it reads repository data and
produces a report artifact, rather than ingesting one the way
`data-engineering`/`research` do.

## Layout

```text
my-project/
├── config.toml
├── app/
│   ├── __init__.py
│   ├── analytics.py      # SummarizeItems (@Analytics @Task)
│   ├── entities.py       # Item
│   ├── repositories.py   # Items(SQLite)
│   └── storages.py       # SQLite
└── reports/               # starts empty — SummarizeItems writes here
```

## What's added

```python
# app/analytics.py
@Analytics
@Task
class SummarizeItems:
    def execute(self) -> dict:
        all_items = self.items.all()
        summary = {
            "item_count": len(all_items),
            "total_quantity": sum(item.quantity for item in all_items),
        }
        ...  # written to reports/summary.json
        return summary
```

The report path comes from `[summarize-items] report-path` in config
(default `"reports/summary.json"`). `@Analytics` marks it for the
`Layer` the UI groups analytics-style tasks under; `@Task` is what makes
it executable from the UI's Execute action or the MCP `execute_task`
tool.

## Run it

<!-- termynal -->

```
$ odf run
UI running at http://127.0.0.1:4747
```

Trigger `SummarizeItems` from the UI (or `execute_task` over MCP) and
check `reports/summary.json`.
