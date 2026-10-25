# 24 — Custom Theme

A plain `HighScores` repository and a `Tally` task, shown in UI themes
that this project ships itself instead of one of `odf`'s built-in themes.
It ships eleven, one directory each under `themes/`: "Arcade" in `pixel/`,
selected by `config.toml`, a late-90s theme park in `park/` (see
[A second theme](#a-second-theme)), a 1980s neon coast in `neon/` (see
[A third theme](#a-third-theme)), and eight more in `terminal/`, `y2k/`,
`meadow/`, `beacon/`, `ledger/`, `clay/`, `workbench/` and `brutalist/`
(see [More themes](#more-themes)).
Arcade is pixel art. It uses a PICO-8 palette in dark mode and a
Game Boy palette in light mode, with pixel fonts, square corners and hard
offset shadows. The topology canvas is drawn at half resolution and scaled
back up in hard pixels.

`config.toml` selects the theme by path rather than by name:

```toml
[ui]
theme = "./themes/pixel"
```

A value with a `/` or `\` in it, or starting with `.` or `~`, is a path to
a theme directory, relative to the directory `odf run` is started from,
like `[ui] favicon` and `[ui] logo`. A built-in theme's name, such as
`default` or `glitch`, still selects that built-in theme. The same path works
as `odf run --theme ./themes/pixel` and `server.start(theme="./themes/pixel")`.

## The theme directory

A project's theme has the same files as a built-in one:

| File | Required | What it does here |
|---|---|---|
| `theme.css` | yes | The whole stylesheet: colors as CSS custom properties for dark (`:root`) and light (`[data-theme="light"]`) mode, then every rule the UI's shared markup needs |
| `favicon.svg` | yes | A 16×16 pixel sprite, drawn with `<rect>`s and `shape-rendering="crispEdges"` |
| `theme.js` | no | How the topology canvas is drawn, through `ODF.registerTheme()` |

Themes share no stylesheet, so `theme.css` has to style the whole UI. This
one started as a copy of `odf`'s built-in
[`default` theme](https://github.com/opendataframework/odf/tree/main/src/odf/ui/static/themes/default)
and was restyled from there. The palette is the two blocks of custom
properties at the top. The pixel-art rules are in the section at the bottom.
Its first line imports two pixel fonts from Google Fonts: Silkscreen for
headings, tags and buttons, and VT323 for everything else. Without a
network connection, both fall back to the system monospace.

`theme.js` sets `pixelSize: 2`, so the canvas is drawn with one canvas pixel
per 2×2 CSS pixels, and `theme.css` sets `image-rendering: pixelated` on
`#canvas` to scale it up without smoothing. At that resolution the default
9.5px node labels would be under 5 canvas pixels tall, so `theme.js` also
sets `labelFont` to Silkscreen and `labelSize` to 16. Silkscreen is drawn on
an 8px grid, so 16 CSS pixels land on exactly 8 canvas pixels. `labelSnap`
keeps them there: labels keep their size at any zoom and sit on whole canvas
pixels, so they stay crisp. `labelShadow` adds an ink drop shadow and
`labelAlpha` raises unlit labels' opacity, so they read over the tiles. The
rest of `theme.js` makes
icons flat three-tone sprites outlined in ink, turns off every glow, and
draws each empty tile with a dithered checker at its center. Every knob
it can set is listed on `THEME_STYLE` in `odf`'s `app.js`.

## A second theme

`themes/park/` styles the same project as a late-90s isometric theme-park
game. Select it with `--theme` instead of editing `config.toml`, since the
flag takes a path too:

```bash
odf run --theme ./themes/park
```

Its `theme.css` started from the same `default` copy, and adds:

- tan windows with a dark outline, a raised 3D bevel and a dark title bar
  over each panel
- buttons that sink in while pressed
- fields that sit sunken
- a red and cream striped awning along the top
- Pixelify Sans for the whole UI, with VT323 kept for data, logs and code

Light mode is the park by day and dark mode the park at night.

Its `theme.js` also sets `pixelSize: 2`, with snapped node labels in
Micro 5, a pixel font on an 11px em, at 22px so each of its pixels is one
canvas pixel. It has no bold, so `labelBold` is off. Icons are sprite-like solids lit
from above, and links are drawn as sandy footpaths through the theme's
`--wire` color. Each empty tile is grass in one of two tones that alternate
tile by tile. `theme.js` reads those tones from the `--grass-a` and
`--grass-b` custom properties in its `onReadTheme(v)` hook, which runs
whenever the colors are read, so day and night each get their own lawn.

## A third theme

`themes/neon/` styles the project as a 1980s beach city at sunset:

```bash
odf run --theme ./themes/neon
```

Its `theme.css` started from the same `default` copy, and adds:

- a sunset stripe along the top, gold into pink into violet
- windows edged in pink neon tubing, which glows at night
- buttons edged in cyan that light up on hover
- a setting sun cut into bands in place of the brand mark
- the brand and panel headings in Yellowtail, a pink script, over Rajdhani
  for the UI and Share Tech Mono for data, logs and code

Dark mode is the strip at night, in hot pink and cyan over a violet dusk.
Light mode is the Art Deco front by day, in salmon, mint and turquoise.

It is the one theme here that is not pixel art. Its `theme.js` sets no
`pixelSize`, so the canvas stays at the screen's resolution and the glows
stay smooth. Instead it turns the glow knobs the other two switch off up:
`litShadow`, `runRingShadow` and `flowLine` all glow in the node's accent.
Icons are drawn as neon tubing, bright outlines over a faint tint, and
`groundShadow` lays a soft pool of each icon's light on the floor under it.
Empty tiles are a checkered floor in `--tile-a` and `--tile-b`, edged in
`--tile-grid`, so night gets a dark floor with a pink grid and day a pastel
terrazzo. `onReadTheme(v)` also reads `--glow`, which scales every glow,
so day mode keeps only a hint of it.

## More themes

Each of these is selected with `--theme` too, and none sets `pixelSize`:

| Theme | Run it with | Look |
|---|---|---|
| Terminal | `odf run --theme ./themes/terminal` | Green phosphor on black with scanlines at night, green ink on line-printer paper by day, a monospace font, double-ruled panels and `[ bracketed ]` buttons. Icons are glowing line art on a dotted grid, drawn by `emptyTile(sx, sy)` |
| Y2K | `odf run --theme ./themes/y2k` | Frosted glass panels, glossy pill buttons and iridescent edges, over midnight blue at night and brushed silver by day. Icons are liquid chrome, one reflection across each, filled by `faceFill(side, accent, lit, t, frame)` |
| Meadow | `odf run --theme ./themes/meadow` | An open blue sky with drifting clouds (stars at dusk), a glossy title bar and rounded panels edged in sky blue. Icons are glossy solids on a lawn in diagonal stripes, each on a soft shadow from `groundShadow(x, y, e, accent, lit)` |
| Beacon | `odf run --theme ./themes/beacon` | A tactical map: square slate panels framed by orange corner ticks, condensed uppercase labels and faint scanlines. Icons are translucent holograms over a grid of city blocks, each inside a segmented marker ring |
| Ledger | `odf run --theme ./themes/ledger` | Utility-first: square corners and hairline rules, surfaces told apart by tone, dense striped tables and a visible focus ring, over near-black at night and white paper by day. Muted kind colors and one blue for focus. Icons are flat silhouettes outlined in ink on a hairline grid, with no glows |
| Clay | `odf run --theme ./themes/clay` | Matte surfaces under one soft key light: raised cards and buttons that press in when clicked, recessed fields and a faint film grain, over graphite at night and warm grey by day. Icons are matte solids lit from the top-left, each on a soft contact shadow |
| Workbench | `odf run --theme ./themes/workbench` | A code editor: charcoal panes on hairlines, a side rail styled as an activity bar, one blue for selection and focus, and JSON in syntax colors, which the kind and layer colors come from too. Icons are flat solids outlined in ink on a hairline grid |
| Brutalist | `odf run --theme ./themes/brutalist` | Neobrutalism: thick ink borders, hard offset shadows instead of soft glows, and Archivo Black for the headings. Icons are flat solid faces in three tones, outlined in the same ink |

## Structure

```
24-custom-theme/
├── config.toml          # [ui] theme = "./themes/pixel", brand
├── main.py              # entry point — starts the UI, same shape as 01-table-view
├── themes/
│   ├── pixel/
│   │   ├── theme.css    # palette, fonts and every UI rule
│   │   ├── theme.js     # ODF.registerTheme({ pixelSize: 2, ... })
│   │   └── favicon.svg  # 16×16 pixel sprite
│   ├── park/            # selected with --theme ./themes/park
│   │   ├── theme.css    # bevels, title bars, day and night palettes
│   │   ├── theme.js     # pixelSize, sprite faces, two-tone grass tiles
│   │   └── favicon.svg  # 16×16 striped tent
│   ├── neon/            # selected with --theme ./themes/neon
│   │   ├── theme.css    # neon edges, sunset stripe, night and day palettes
│   │   ├── theme.js     # no pixelSize: glows, light pools, checkered floor
│   │   └── favicon.svg  # a palm against a setting sun
│   ├── terminal/        # selected with --theme ./themes/terminal
│   ├── y2k/             # selected with --theme ./themes/y2k
│   ├── meadow/          # selected with --theme ./themes/meadow
│   ├── beacon/          # selected with --theme ./themes/beacon
│   ├── ledger/          # selected with --theme ./themes/ledger
│   ├── clay/            # selected with --theme ./themes/clay
│   ├── workbench/       # selected with --theme ./themes/workbench
│   └── brutalist/       # selected with --theme ./themes/brutalist
└── app/
    ├── __init__.py      # imports every module so decorators register at startup
    ├── entities.py      # Score(id, player, game, points) — @Entity
    ├── repositories.py  # HighScores — @Storage @Repository(Score), in-memory, pre-seeded
    └── tasks.py         # Tally — @Task totalling each player's points
```

## Run it

```bash
cd examples/24-custom-theme
odf run
```

Open the UI. The header reads "Arcade" in Silkscreen over a striped top
bar, the browser tab shows the invader favicon, and `HighScores` and `Tally`
stand on the grid as chunky pixel sprites. Toggle light mode for the Game
Boy greens. Run `odf run --theme ./themes/park` for the theme park, where
both nodes stand on a checkered lawn joined by a footpath,
`odf run --theme ./themes/neon` for the neon coast, where they glow in pink
and cyan on a dark floor, any of the [more themes](#more-themes),
or `odf run --theme default` to compare the same project in a built-in theme.
