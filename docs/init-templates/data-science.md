# `data-science` template

```bash
odf init my-project --template data-science
```

[`default`](default.md) (`Item`/`Items`/`SQLite`), no `app/` changes at
all — just a seed CSV and a notebook that loads it into the repository
*outside* the running `Project`, to show a `Repository` works standalone
in a notebook kernel the same way it does DI-resolved inside one.

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

config = Config({"sqlite": {"path": "../app.db"}})
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
