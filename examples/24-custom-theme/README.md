# 24 — Custom Theme

A plain `Accounts` repository and a `Revenue` task, shown in a UI theme that
this project ships itself instead of one of `odf`'s built-in themes:
"Glitch", in `themes/glitch/`, a dark look with a "signal glitch" edge.
Panels, tags, the header title and lit icons carry a thin chromatic-split
fringe, one pixel of cyan to one side and magenta to the other, as if the
RGB channels were misregistered. Light mode keeps the same fringe in deeper
tones.

`config.toml` selects the theme by path rather than by name:

```toml
[ui]
theme = "./themes/glitch"
```

A value with a `/` or `\` in it, or starting with `.` or `~`, is a path to
a theme directory, relative to the directory `odf run` is started from,
like `[ui] favicon` and `[ui] logo`. A built-in theme's name, such as
`default` or `ink`, still selects that built-in theme. The same path
works as `odf run --theme ./themes/glitch` and
`server.start(theme="./themes/glitch")`.

## The theme directory

A project's theme has the same files as a built-in one:

| File | Required | What it does here |
|---|---|---|
| `theme.css` | yes | The whole stylesheet: colors as CSS custom properties for dark (`:root`) and light (`[data-theme="light"]`) mode, then every rule the UI's shared markup needs |
| `favicon.svg` | yes | A purple pixel face with pale eyes on a near-black tile. The header shows it next to the brand too |
| `theme.js` | no | How the topology canvas is drawn, through `ODF.registerTheme()` |

Themes share no stylesheet, so `theme.css` has to style the whole UI. The
palette is the two blocks of custom properties at the top. Besides the
variables every theme sets, it adds two of its own, `--split-a` (cyan) and
`--split-b` (magenta), the fringe's two channel colors. `--tag-shadow` and
`--panel-shadow` build the fringe out of them as one-pixel offset shadows,
and the rest of the stylesheet reuses those on tags, panels, rings and
text. The top bar and the scrollbar thumbs run from one channel color to
the other, and a faint static scanline texture lies over the whole app.

The header mark next to "Acme" is drawn by `theme.css` from `/favicon.svg`,
so it is the same logo as the browser tab's.

`theme.js` draws icons as dark solids: faces nearly the canvas color with a
trace of their kind's color, under bright edges. On a lit icon it strokes
each shape twice more, a pixel to each side, in `--split-a` and `--split-b`
(read in `onReadTheme`, drawn in `litFringe`), so the canvas gets the same
fringe as the chrome. It sets no `pixelSize`, so the canvas is drawn at the
screen's own resolution. Every knob it can set is listed on `THEME_STYLE` in
`odf`'s `app.js`.

## Structure

```
24-custom-theme/
├── config.toml          # [ui] theme = "./themes/glitch", brand
├── main.py              # entry point — starts the UI, same shape as 01-table-view
├── themes/
│   └── glitch/
│       ├── theme.css    # palette, split colors and every UI rule
│       ├── theme.js     # ODF.registerTheme({ faces, onReadTheme, litFringe })
│       └── favicon.svg  # purple pixel face on a dark tile
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

Open the UI. The header reads "Acme" next to the purple pixel face, the
browser tab shows the same logo, and `Accounts` and `Revenue` stand on a
near-black grid as dark solids with bright edges, fringed in cyan and
magenta when lit. Toggle light mode for the same look on white. Run
`odf run --theme ink` to compare the same project in a built-in theme.
