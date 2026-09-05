# 17 — Custom Icon

A plain `Beacons` repository (no `data_view()` override — same default
table as [`01-table-view`](../01-table-view)) alongside a custom topology
icon, color swatches, favicon, header logo, brand name, and a pre-seeded
layout override, all registered through `config.toml`/`layout.json`, so
the dev UI's icon picker offers a lighthouse swatch and two lighthouse
color swatches alongside the built-in defaults, the `Beacons` node
already renders with that icon and color the moment the UI loads (no
manual click needed), the browser tab shows a lighthouse favicon and
"Beacon Watch — custom-icon-example" title instead of the built-in ODF
ones, and the header's brand mark/label are swapped for a matching logo
image and name.

Icons are procedural canvas vector art, not image files — `icons/lighthouse.js`
defines a draw function with the same `(sx, sy, accent, lit)` signature and
shared primitives (`drawBox`/`isoBox`, `rgba`, `ctx`, `animT`) as every
built-in icon in `odf`'s UI, and registers it via `ODF.registerIcon(key,
draw, meta)`. `config.toml`'s `[ui] icon-scripts` tells `Server.start(ui=True)`
to serve that file to the browser and load it before the first render.

A registered icon isn't tied to a particular exec type (repository, task,
service, ...) — it's just one more option in the picker, assignable to any
node. Nothing forces a node to actually use it — that's what `layout.json`
is for (see below); `icons/lighthouse.js` alone only makes "Lighthouse" an
available choice.

The same registration is available to framework-extension packages via
`odf.ui.extensions.register_icon_script()`, called at import time instead
of listed in a project's `config.toml` — see `odf.ui.extensions`'s
docstring. `[ui.colors]` (name → hex) registers custom color swatches the
same way, for projects that want a specific accent beyond the curated
palette — this example's `config.toml` registers `lighthouse-amber`
(`#f2c14e`) and `lighthouse-red` (`#c94f3d`), matching the tower's lamp
and stripe colors, so they show up as named swatches in every node's color
picker alongside the 12 built-in ones.

`layout.json` is what actually assigns the icon/color to `Beacons`,
rather than leaving that to a manual click. It's the same file the UI
itself writes to (via `PUT /api/layout`) whenever you drag a node or pick
a new icon/color — `{"beacons": {"col": 0, "row": 0, "icon": "lighthouse",
"color": "#f2c14e"}}` here just pre-seeds that persisted state, so the
node already renders with the lighthouse tower and amber tint on first
load. `col`/`row` still have to be given even though they don't move
anything here — they're only useful if you delete this file and see where
`Beacons` lands by default (a single-node project always starts at
`(0, 0)`, matching the values above); the UI overwrites the whole file
every time it saves, so this is a snapshot of one valid state rather than
a schema this example's own repository defines.

`[ui] favicon` and `[ui] logo` work the same way, but simpler — no
registration function, no picker entry, just a path to an image file.
`favicon` replaces `GET /favicon.svg` (must be an `.svg`, same as the
built-in one it replaces); `logo` is served at `GET /api/ui/logo` and, if
set, the frontend swaps it into the header in place of the default
CSS-drawn diamond mark. Unlike icons (procedural, theme-aware canvas
draws), both are static images — this example's `logo.svg` bakes in its
own dark backdrop circle so it stays legible in both the light and dark
theme, since a plain `<img>` can't react to `--title-accent`/theme changes
the way the built-in mark does.

`[ui] brand` is plainer still — just a string, no file. It replaces the
"ODF" label shown next to the logo and the browser tab title's prefix
(`"{brand} — {project name}"`), for projects that want their own name
instead of the framework's. `project` (from `[project] name`) is left
alone — that's still the specific project being visualized, shown in the
header subtitle and the sidebar's Project stat.

## Structure

```
17-custom-icon/
├── config.toml          # [ui] icon-scripts / colors / favicon / logo / brand
├── layout.json          # pre-seeds Beacons' icon/color override
├── main.py              # entry point — starts the UI, same shape as 01-table-view
├── favicon.svg           # replaces the browser tab's favicon
├── logo.svg               # replaces the header's brand mark
├── icons/
│   └── lighthouse.js     # ODF.registerIcon("lighthouse", drawLighthouse, meta)
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # Beacon(id, name, active) — @Entity
    └── repositories.py   # Beacons — @Storage @Repository(Beacon), in-memory, pre-seeded
```

## Run it

```bash
cd examples/17-custom-icon
odf run
```

Open the UI — the browser tab shows the lighthouse favicon and reads
"Beacon Watch — custom-icon-example", the header's brand mark/label read
"Beacon Watch" with the matching logo image instead of "ODF" and the
default diamond, and `Beacons` already renders with the lighthouse tower
in amber, no clicking required. Click the node, then **Customize**, to
see where that came from — the icon picker highlights "Lighthouse" (a
sweeping-beam tower) and the color picker highlights the amber swatch,
alongside the built-ins and the red swatch this example also registered.
Pick a different icon/color and it persists back to `layout.json`, same
as any other override.

`GET /api/ui/extensions` reports `{"iconScripts": ["/api/ui/icon-scripts/0"],
"colors": {"lighthouse-amber": "#f2c14e", "lighthouse-red": "#c94f3d"},
"logo": "/api/ui/logo", "brand": "Beacon Watch"}` — that's what tells the
browser which extra `.js` files to load before the first topology render,
which named colors to offer in every picker, whether to swap in a custom
logo image, and what name to show instead of "ODF".
