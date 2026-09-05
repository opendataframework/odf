# 14 — Chart

A single `SalesByStore` component implementing `chart() -> str` — a
self-contained HTML document (an inline base64 PNG here) that the dev UI
serves verbatim from `GET /api/components/{id}/chart` and renders inside a
same-origin `<iframe>` behind a **View Chart** button.

This isolates the concept covered in [`docs/component.md`](../../docs/component.md)'s
"Chart (dev UI)" section: `ChartProtocol` is a `Component`-level capability,
independent of `DataView` ([`06-location-view`](../06-location-view),
[`07`](../07-streaming-video-view)–[`13`](../13-timeseries-view)), which
lives on `Repository` instead. Because the chart lives on a normal
DI-managed `Component`, it gets constructor-injected access to
`Sales` — no separate data-fetching layer needed — and rebuilds the figure
on every `chart()` call rather than caching it, so it reflects live
repository state each time it's opened.

Deliberately a single static matplotlib PNG with no light/dark theme
handling — see [`15-chart-plotly`](../15-chart-plotly) for a Plotly-backed
sibling with real hover tooltips instead of a static image. Neither example
here adds theme-sync polish (an iframe script that follows the parent
topology UI's theme).

`Sales` comes pre-seeded in-memory with three sales (see
`app/repositories.py`'s `_SEED_SALES`) — there's no reason to reach for a
file when the data is this small, and a bar chart is a lot more useful to
look at with something already in it.

## Structure

```
14-chart/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded sales, calls chart() directly
└── app/
    ├── __init__.py      # imports all modules so decorators register at startup
    ├── entities.py       # Sale(id, store, amount) — @Entity
    ├── repositories.py   # Sales — @Storage @Repository(Sale), in-memory, pre-seeded
    └── components.py     # SalesByStore — @Analytics @Component, implements chart()
```

## Dependencies

Needs the `examples` extra (`pip install odf[examples]`) for `matplotlib` to
render the bar chart — already in the repo's `dev` dependency group, so a
plain `poetry install` covers it (see [`CLAUDE.md`](../../CLAUDE.md)).

## Run it

```bash
cd examples/14-chart
python main.py
```

Expected output (the exact byte count and base64 prefix will vary):

```
chart() -> 16864 bytes of self-contained HTML, starting with:
<html><body><img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAlgAAAGQCAYA...
```

Or start the dev UI and click **View Chart** on `SalesByStore`:

```bash
odf run
```

A component with no `chart()` method simply gets no **View Chart** button —
`ChartProtocol` is entirely optional, detected structurally
(`opendataframework.component.ChartProtocol`, `@runtime_checkable`), no base
class or decorator required.
