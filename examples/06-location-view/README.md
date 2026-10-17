# 06 — Location View

A single `Stores` repository implementing `data_view() -> LocationView`
instead of getting the default table, so the UI renders it as a map — one
marker per record — instead of a grid of columns.

`Stores` still supports `all()`/`save()`/`delete()` as normal — `data_view()`
only picks which widget the UI shows, it doesn't restrict what the
repository does.

`Stores` comes pre-seeded in-memory with six real store locations spread
across the US (see `app/repositories.py`'s `_SEED_STORES`) — a map is a lot
more useful to look at with real spread on it than one or two hand-typed
pins, and there's no reason to reach for a file when the data is this
small.

A repository declares exactly one view, but that's just metadata handed to
the UI — the UI is still free to layer a fallback on top. Alongside the
declared map, it offers a one-click toggle back to the same plain table
that any readable repository gets by default when it implements no
`data_view()` at all — see [`01-table-view`](../01-table-view) for that
default with nothing overriding it.

## Structure

```
06-location-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded stores, prints data_view()
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # Store(id, name, lat, lon) — @Entity
    └── repositories.py   # Stores — @Storage @Repository(Store), in-memory, pre-seeded
```

## Run it

```bash
cd examples/06-location-view
python main.py
```

Expected output:

```
All stores:
  Store(id=1, name='San Francisco Downtown', lat=37.7749, lon=-122.4194)
  Store(id=2, name='Seattle Downtown', lat=47.6062, lon=-122.3321)
  Store(id=3, name='Austin Downtown', lat=30.2672, lon=-97.7431)
  Store(id=4, name='Chicago Loop', lat=41.8781, lon=-87.6298)
  Store(id=5, name='New York Midtown', lat=40.7549, lon=-73.984)
  Store(id=6, name='Miami Downtown', lat=25.7617, lon=-80.1918)

data_view() -> LocationView(fields=('lat', 'lon'))
```

Or start the dev UI and click **View Map** on `Stores`:

```bash
odf run
```

`GET /api/repositories` reports `Stores`' view as
`{"kind": "location", "fields": ["lat", "lon"]}` — that's what tells the UI
to render a map instead of a table. Once you're on the map, the same panel
has a **Table** toggle back to the default grid.

## Annotating

Labelled regions can be drawn on the map, for simple cases where a one-off
script would be more than the job needs: a region of interest, a geofence, a
split of the records by area.

- The tools are at the top right of the map. It opens on **Select** (`V`),
  which leaves the map to be moved as usual; the tool picked is remembered in
  the browser.
- With **Draw a region** (`B`), drag out a rectangle, type its label and press
  `Enter`. Labels already used in the repository are listed under the input,
  and the last one is prefilled. The map doesn't move under a drag while this
  tool is picked; the mouse wheel still zooms it.
- With **Select**, select a region and press `Delete` (or its `×`) to remove
  it, or select the label at its corner to change it. There is no move or
  resize, and no other shape.
- A region inside a larger one stays on top, so it can still be selected.
- `Esc` backs out of the label input, then the selection, then the map.
  Replay shows the regions but takes no new ones.

Every change is saved to `annotations.json` in the directory `odf run` was
started from (`[project] annotations-file` in `config.toml` names another
path). `annotations = false` under `[ui]` in `config.toml` turns annotating
off. The file looks like this:

```json
{
  "version": 1,
  "repositories": {
    "stores": {
      "labels": ["downtown"],
      "annotations": [
        {"type": "box", "label": "downtown",
         "south": 50.44, "west": 30.5, "north": 50.46, "east": 30.54}
      ]
    }
  }
}
```

- Regions belong to the repository's map rather than to one record, so they
  are one `annotations` list.
- `south` and `north` are latitudes and `west` and `east` longitudes, in
  degrees as `lat` and `lon` are, to six decimal places. A region doesn't
  cross the antimeridian, so `west` is less than `east`.
- `labels` lists the labels in use, in the order each was first used. A label
  no region uses any more is dropped.

The file is plain JSON, so a pipeline reads it without importing `odf`, for
example to label the stores inside each region:

```python
import json

block = json.load(open("annotations.json"))["repositories"]["stores"]
for region in block["annotations"]:
    inside = df["lat"].between(region["south"], region["north"]) & df["lon"].between(
        region["west"], region["east"]
    )
    df.loc[inside, "region"] = region["label"]
```
