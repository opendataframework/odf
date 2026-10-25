# 24 — Custom Theme

A plain `Accounts` repository and a `Revenue` task, shown in a UI theme that
this project ships itself instead of one of `odf`'s built-in themes:
"Mono", in `themes/mono/`, a monochrome SaaS-dashboard look. Dark mode is
white on black and light mode black on white, with grey borders and
surfaces, and white (black by day) kept for the active, focused and primary
state.

`config.toml` selects the theme by path rather than by name:

```toml
[ui]
theme = "./themes/mono"
```

A value with a `/` or `\` in it, or starting with `.` or `~`, is a path to
a theme directory, relative to the directory `odf run` is started from,
like `[ui] favicon` and `[ui] logo`. A built-in theme's name, such as
`default` or `emerald`, still selects that built-in theme. The same path
works as `odf run --theme ./themes/mono` and
`server.start(theme="./themes/mono")`.

## The theme directory

A project's theme has the same files as a built-in one:

| File | Required | What it does here |
|---|---|---|
| `theme.css` | yes | The whole stylesheet: colors as CSS custom properties for dark (`:root`) and light (`[data-theme="light"]`) mode, then every rule the UI's shared markup needs |
| `favicon.svg` | yes | The built-in themes' stacked-layers logo, in white on a black tile. The header shows it next to the brand too |
| `theme.js` | no | How the topology canvas is drawn, through `ODF.registerTheme()` |

Themes share no stylesheet, so `theme.css` has to style the whole UI. This
one started as a copy of `odf`'s built-in
[`emerald` theme](https://github.com/opendataframework/odf/tree/main/src/odf/ui/static/themes/emerald),
which already has the SaaS chrome: sans-serif sentence-case labels, soft
radii, and no decorative top bar or corner brackets. The palette is the two
blocks of custom properties at the top, where emerald's green
`--title-accent` became white in dark mode and black in light mode. Since
the accent is now as light (or as dark) as the text, primary buttons draw
their label in `--bg`. The kind and layer colors are emerald's hues, muted,
so nodes stay told apart on the grey grid.

The header mark next to "Acme" is drawn by `theme.css` from `/favicon.svg`,
so it is the same logo as the browser tab's.

`theme.js` draws icons as tonal solids: opaque shades of their kind's color
with no outlines, and a lit icon raised a step in tone over a soft black
shadow instead of a glow in its color. It sets no `pixelSize`, so the canvas
is drawn at the screen's own resolution. Every knob it can set is listed on
`THEME_STYLE` in `odf`'s `app.js`.

## Structure

```
24-custom-theme/
├── config.toml          # [ui] theme = "./themes/mono", brand
├── main.py              # entry point — starts the UI, same shape as 01-table-view
├── themes/
│   └── mono/
│       ├── theme.css    # palette and every UI rule
│       ├── theme.js     # ODF.registerTheme({ faces, litShadow })
│       └── favicon.svg  # stacked layers on a black tile
└── app/
    ├── __init__.py      # imports every module so decorators register at startup
    ├── entities.py      # Account(id, name, plan, mrr) — @Entity
    ├── repositories.py  # Accounts — @Storage @Repository(Account), in-memory, pre-seeded
    └── tasks.py         # Revenue — @Task totalling MRR per plan
```

## Run it

```bash
cd examples/24-custom-theme
odf run
```

Open the UI. The header reads "Acme" next to the white stacked-layers mark,
the browser tab shows the same logo, and `Accounts` and `Revenue` stand on
a black grid as muted tonal solids. Toggle light mode for black on white.
Run `odf run --theme default` to compare the same project in a built-in
theme.
