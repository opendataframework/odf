# `research` template

```bash
odf init my-project --template research
```

[`default`](default.md) (`Item`/`Items`/`SQLite`) plus a single
`RunExperiment` `@Task` and a write-up stub, following ["Good Enough
Practices in Scientific Computing"](https://doi.org/10.1371/journal.pcbi.1005510)
(Wilson et al., 2017): a flat `data/` for raw, read-only input, a
`results/` for everything generated, and a `doc/` for the write-up —
`app/` plays the role of that layout's `src/`.

## Layout

```text
my-project/
├── config.toml
├── app/
│   ├── __init__.py
│   ├── entities.py       # Item
│   ├── storages.py       # SQLite
│   ├── repositories.py   # Items(SQLite)
│   └── experiments.py    # RunExperiment
├── data/
│   └── items.csv          # source data — read, never edited in place
├── results/                # starts empty — RunExperiment writes here
└── doc/
    └── notes.md            # hypothesis / method / results stub
```

## What's added

```python
# app/experiments.py
@Task
class RunExperiment:
    def execute(self) -> dict:
        if not self.items.all():
            ...  # seeds data/items.csv into Items, first run only

        all_items = self.items.all()
        summary = {
            "item_count": len(all_items),
            "total_quantity": sum(item.quantity for item in all_items),
        }
        ...  # written to results/summary.json
        return summary
```

`doc/notes.md` is a lab-notebook stub — hypothesis, method, results,
notes — pre-filled with a pointer back to `RunExperiment` so the write-up
and the code that produces its numbers stay next to each other.

## Run it

<!-- termynal -->

```
$ odf run
UI running at http://127.0.0.1:4747
```

Trigger `RunExperiment` from the UI (or `execute_task` over MCP), then
check `results/summary.json` and fill in `doc/notes.md`.
