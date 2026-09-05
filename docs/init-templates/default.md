# `default` template

```bash
odf init my-project
```

The bare starting point every other template builds on: one `Entity`, one
`Repository`, one `sqlite3`-backed `Storage`. No extra dependencies beyond
`odf` core and the Python standard library.

## Layout

```text
my-project/
├── config.toml
└── app/
    ├── __init__.py
    ├── entities.py       # Item
    ├── repositories.py   # Items(SQLite)
    └── storages.py       # SQLite
```

## What's registered

- **`Item`** (`app/entities.py`) — an `@Entity` `dataclass` with `id`,
  `name`, `quantity`.
- **`Items`** (`app/repositories.py`) — an `@Storage @Repository(Item)`
  backed by `SQLite`, exposing `all()`/`get()`/`save()`/`delete()`.
- **`SQLite`** (`app/storages.py`) — an `@Storage @Component` that opens
  the path from `[sqlite] path` in config (default `"app.db"`) and
  creates the `items` table if it doesn't exist yet.

```toml
# config.toml
[project]
name = "my-project"

[sqlite]
path = "app.db"
```

`app/__init__.py` imports `entities`, `repositories`, and `storages` so
their decorators register as a side effect — see [Server](../server.md#the-app-module)
for why that import matters.

## Run it

<!-- termynal -->

```
$ odf run
UI running at http://127.0.0.1:4747
```

Open the UI — `Items` renders as a plain table with no extra step needed.

---

Every other template starts from exactly this layout and adds one thing
on top — see the [Templates comparison](../cli.md#templates) for
`data-analytics`, `data-science`, `data-engineering`, and `research`.
