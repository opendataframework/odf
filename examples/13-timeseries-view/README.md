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
