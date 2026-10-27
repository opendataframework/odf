# 25 — Flat Grid

A small parcel depot shown on the flat grid. `config.toml`'s `[ui] grid =
"flat"` draws the topology as a top-down schematic instead of the isometric
grid: square cells marked by a faint dot, and every node a rounded square in
its type's color with that type's glyph on it. The depot has one node of each
kind, so the glyphs sit side by side:

| Node | Type | Glyph |
|---|---|---|
| `Config` | config | sliders |
| `Parcels` | `@Repository` | rack |
| `Tracker` | `@Service` | broadcast arcs |
| `shipping_cost` | `@Function` | lambda |
| `SortParcels` | `@Task` | cog |
| `NightlyRun` | `@Pipeline` | chevrons |
| `Couriers` | `@Repository` | user (customized, see below) |

## Structure

```
25-flat-grid/
├── config.toml          # [ui] grid = "flat"
├── layout.json          # gives Couriers the "user" glyph and a blue color
├── main.py              # alternative to `odf run` — boots the same UI via odf.server.Server directly
└── app/
    ├── __init__.py      # imports every module so decorators register at startup
    ├── entities.py      # Parcel(id, destination, weight_kg, sorted), Courier(id, name) — @Entity
    ├── repositories.py  # Parcels, Couriers — @Storage @Repository, in-memory, seeded
    ├── services.py      # Tracker — @Service ticking in the background
    ├── functions.py     # shipping_cost(weight_kg) — @Function
    ├── tasks.py         # SortParcels — @Task marking unsorted parcels sorted
    └── pipelines.py     # NightlyRun — @Pipeline running SortParcels
```

## Run it

```bash
cd examples/25-flat-grid
odf run
```

or `python main.py`, which boots the same UI. Columns run right and rows down:
`SortParcels` sits right of the repository it depends on, and `NightlyRun`
right of that.

## Customizing a node

Select a node and click **Customize**. On the flat grid it lists the flat
glyphs: the type defaults, plus a few symbols (database, cloud, bolt, star,
flag, lock, user, chart). It also has the color swatches. `layout.json` here
pre-applies one such choice to `Couriers`, keyed by its node id:

```json
{"repository.couriers": {"col": 0, "row": 1, "flatIcon": "user", "color": "#5aa8e0"}}
```

That is what the UI writes itself when you pick a glyph and color. The glyph
is saved as `flatIcon`, apart from the isometric grid's `icon`, so each grid
keeps its own choice. The color is shared by both grids. Set `grid = "iso"`
in `config.toml` (or remove the line) to compare: `Couriers` keeps its blue
color and every node keeps its cell, while the isometric icon stays the
type's default.

See [UI](https://opendataframework.github.io/odf/ui/#flat-grid) for the
flat grid in full.
