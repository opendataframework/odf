# 01 — Table View

The smallest `odf` project there is: one `@Entity`, one `@Storage
@Repository`, and a `config.toml` with nothing but a project name — nothing
else to define. `odf run` resolves `Books` and shows it as a node on the
UI's topology graph; because `Books` implements no `data_view()`,
opening that node renders a plain table, one column per entity field, in
declaration order, with no extra step. See
[`06-location-view`](../06-location-view) for the same repository shape
with `data_view() -> LocationView` overriding that default instead, and
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/)
for the full `data_view()` concept.

## Structure

```
01-table-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # alternative to `odf run` — boots the same UI via odf.server.Server directly
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py      # Book(id, title, author) — @Entity
    └── repositories.py  # Books — @Storage @Repository(Book), in-memory, no data_view()
```

## Run it

```bash
cd examples/01-table-view
odf run
```

`odf run` is a thin CLI wrapper around three steps: import `app` so `Books`
registers, build a `Server` from `config.toml`, and `start(ui=True)`.
`main.py` does the same three steps directly in Python — same UI, same
in-memory `Books` — to show that booting it isn't tied to the CLI:

```bash
python main.py
```

Either way, open the UI: `Books` shows up as a node on the topology
graph — that's everything this project defines. Click into it and it's a
plain table, no `data_view()` implemented, no view type imported. It
starts empty (fresh in-memory process), so use the table's **Add Row**
control to create a book or two — `id` is assigned automatically,
`title`/`author` are plain text inputs — and watch the rows appear
immediately.
