# 13 — Timeseries View

A single `Orders` repository implementing `data_view() -> TimeseriesView`
instead of getting the default table. The topology UI plots `Order`'s other
numeric field (`amount`) against the named timestamp field (`created_at`)
as a line chart, one point per record, instead of a grid of columns.

This isolates the last `DataView` variant covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/)
not already covered by
[`06-location-view`](../06-location-view) (`LocationView`) or
[`07`](../07-streaming-video-view)–[`12`](../12-document-view)
(the streaming/video/audio/image/document catalog). Like `LocationView`,
`TimeseriesView` is `ReadableProtocol`-backed — `all()` is all it needs — but
it names one field specially (the timestamp) rather than a set of columns to
hide. Its own `field` already qualifies a repository for the dev UI's replay
scrubber — no separate `ReplayProtocol.replay_field()` opt-in needed, unlike
`LocationView` (see
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/)).

`Orders` comes pre-seeded in-memory with three orders (see
`app/repositories.py`'s `_SEED_ORDERS`) — there's no reason to reach for a
file when the data is this small, and a timeseries chart is a lot more
useful to look at with something already in it.

## Structure

```
13-timeseries-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded orders, prints data_view()
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # Order(id, amount, created_at) — @Entity
    └── repositories.py   # Orders — @Storage @Repository(Order), in-memory, pre-seeded
```

## Run it

```bash
cd examples/13-timeseries-view
python main.py
```

Expected output (the timestamps will vary):

```
All orders:
  Order(id=1, amount=129.99, created_at=1787782427.264908)
  Order(id=2, amount=18.3, created_at=1787868827.264908)
  Order(id=3, amount=275.0, created_at=1787955227.264908)

data_view() -> TimeseriesView(field='created_at')
```

Or start the dev UI and click **View Chart** on `Orders`:

```bash
odf run
```

`GET /api/repositories` reports `Orders`' view as
`{"kind": "timeseries", "field": "created_at"}` — that's what tells the UI
to render a line chart instead of a table.

## Annotating

Time ranges and points can be labelled on the chart, for simple cases where a
one-off script over a plotting library would be more than the job needs:
marking a stretch to train on or to leave out, an event, or a bad reading.

- The tools are beside the legend. The chart opens on **Select** (`V`), which
  adds nothing; the tool picked is remembered in the browser.
- With **Label a range** (`R`), drag across the chart, type the range's label
  and press `Enter`. Labels already used in the repository are listed under
  the input, to click or to pick with `↓`/`↑` and `Enter`; typing narrows the
  list, and the last label is prefilled.
- With **Label a point** (`P`), click the chart. The point goes on the record
  nearest the click, so it can be inside a range.
- Select a range or a point and press `Delete` (or its `×`) to remove it.
  There is no move or resize: delete it and make it again. Select its label
  to change it.
- A range or a point covers every series on the chart, and ranges may overlap.
- The chart plots one page of records, so a range is dragged within the page
  shown; pick a larger page size for a longer one. A saved range or point
  shows on every page whose time span it falls in.
- `Esc` backs out of the label input, then the selection, then the chart.
  Replay shows the labels but takes no new ones.

Every change is saved to `annotations.json` in the directory `odf run` was
started from (`[project] annotations-file` in `config.toml` names another
path). `annotations = false` under `[ui]` in `config.toml` turns annotating
off for a project that doesn't need it. The file looks like this:

```json
{
  "version": 1,
  "repositories": {
    "orders": {
      "labels": ["promo", "outlier"],
      "annotations": [
        {"type": "range", "label": "promo", "start": 1787782427.26, "end": 1787955227.26},
        {"type": "point", "label": "outlier", "at": 1787868827.26, "key": "2"}
      ]
    }
  }
}
```

- `repositories` is keyed by repository id. The labels belong to the
  repository's time axis rather than to one record, so they are one
  `annotations` list, in time order.
- `labels` lists the labels in use, in the order each was first used. A label
  nothing uses any more is dropped.
- A range's `start` and `end` and a point's `at` are values of the timestamp
  field (`created_at` here), in its own units.
- A point's `at` is the timestamp of the record it was made on, and `key`
  that record's key (as a string), so it can be matched either way.

The file is plain JSON, so a pipeline reads it without importing `odf`:

```python
import json

import pandas as pd

block = json.load(open("annotations.json"))["repositories"]["orders"]
df = pd.DataFrame(orders)  # one row per order, with id, amount and created_at
df["label"] = None
for mark in block["annotations"]:
    if mark["type"] == "range":
        rows = df["created_at"].between(mark["start"], mark["end"])
    else:
        rows = df["id"].astype(str) == mark["key"]
    df.loc[rows, "label"] = mark["label"]
```

This example's orders are seeded with timestamps relative to when it starts,
so ranges saved in one run fall elsewhere on the chart in the next. A
repository reading stored timestamps keeps them in place.
