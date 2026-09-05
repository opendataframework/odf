# 15 — Chart (Plotly)

The same `SalesByStore`/`ChartProtocol` contract as
[`14-chart`](../14-chart), backed by Plotly instead of matplotlib —
`chart() -> str` still returns a single self-contained HTML document (no
external file references), but an interactive JS chart needs the charting
library's own JS bundle inlined, not just an image.

This isolates the wrinkle `docs/component.md`'s "Chart (dev UI)" section
only mentions in passing ("whatever Python charting library it likes —
matplotlib, plotly, ..."): `plotly.offline.get_plotlyjs()` returns Plotly's
JS bundle as a string, embedded once in the page's `<head>`;
`fig.to_html(include_plotlyjs=False)` then emits only the chart's own
`<div>`/`<script>`, assuming that bundle is already present. In return for
the extra inlining step, the chart gets real hover tooltips instead of a
static PNG — see [`14-chart`](../14-chart) for the matplotlib-backed sibling
this one mirrors.

`Sales` comes pre-seeded in-memory with three sales (see
`app/repositories.py`'s `_SEED_SALES`, same seed data as `14-chart`'s) —
there's no reason to reach for a file when the data is this small, and a
bar chart is a lot more useful to look at with something already in it.

## Structure

```
15-chart-plotly/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded sales, calls chart() directly
└── app/
    ├── __init__.py      # imports all modules so decorators register at startup
    ├── entities.py       # Sale(id, store, amount) — @Entity
    ├── repositories.py   # Sales — @Storage @Repository(Sale), in-memory, pre-seeded
    └── components.py     # SalesByStore — @Analytics @Component, implements chart()
```

## Dependencies

Needs the `examples` extra (`pip install odf[examples]`) for `plotly` to
render the bar chart — already in the repo's `dev` dependency group, so a
plain `poetry install` covers it (see [`CLAUDE.md`](../../CLAUDE.md)).

## Run it

```bash
cd examples/15-chart-plotly
python main.py
```

Expected output (the exact byte count will vary; it's large because
Plotly's JS bundle is inlined in full):

```
chart() -> 4565896 bytes of self-contained HTML, starting with:
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script>/**
* plotly.js v2....
```

Or start the dev UI and click **View Chart** on `SalesByStore`, and hover
over a bar to see the tooltip:

```bash
odf run
```
