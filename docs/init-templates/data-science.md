# `data-science` template

```bash
odf init my-project --template data-science
```

[`default`](default.md) (`Item`/`Items`/`SQLite`), no `app/` changes at
all — just a seed CSV and a notebook that loads it into the repository
*outside* the running `Project`, to show a `Repository` works standalone
in a notebook kernel the same way it does DI-resolved inside one.

## Choosing between `data-science` and `ml`

Both are for data work. They differ in what the project is about:

- **`data-science`** is for exploring data: source data in `data/raw/`,
  derived data in `data/processed/`, and a notebook to work through it. The
  records are the data itself, and the question is "what's in this data?".
- **[`ml`](ml.md)** is for training and comparing models: runs, their
  parameters, per-step metrics and per-run artifacts, a sweep and a
  comparison chart. The records are runs and what they measured, and the
  question is "which run did best, and why?".

Pick `data-science` when you're still finding out what the data holds, and
`ml` when you'll train something more than once and compare the results.

## Layout

```text
my-project/
├── config.toml
├── app/
│   ├── __init__.py
│   ├── entities.py       # Item
│   ├── repositories.py   # Items(SQLite)
│   └── storages.py       # SQLite
├── data/
│   ├── raw/
│   │   └── items.csv      # source data — read, never edited in place
│   └── processed/         # starts empty
└── notebooks/
    └── example.ipynb
```

## What's added

`example.ipynb` builds the same `SQLite → Items` dependency chain the
`Context` would normally wire up for you, but by hand — since a notebook
kernel runs outside the resolved object graph:

```python
from opendataframework import Config

from app.entities import Item
from app.repositories import Items
from app.storages import SQLite

config = Config({"component": {"sqlite": {"path": "../app.db"}}})
sqlite = SQLite(config)
items = Items(sqlite)
```

Then it reads `data/raw/items.csv` and calls `items.save(...)` per row —
the same ingestion a real `Task` would do, just exploratory. Anything
derived (cleaned, joined, aggregated) belongs in `data/processed/`, never
written back to `raw/`.

## Run it

<!-- termynal -->

```
$ jupyter notebook notebooks/example.ipynb
```

Or start the UI as usual (`odf run`) to browse `Items` once the notebook
has seeded it.
