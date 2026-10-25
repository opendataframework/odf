# UI

A small FastAPI dev server (backgrounded, like any `Service`) that
visualizes the resolved object graph — every `Component`/`Service`/
`Repository`, grouped by `Layer`, with lifecycle actions (start/stop/
execute) available from the UI. Grid positions persist across reloads.
The left sidebar collapses to an icon rail to give the canvas more
room; its collapsed/expanded state is remembered per browser.

```bash
pip install "odf[ui]"
odf run                # the UI is on by default
```

```python
server.start(ui=True)
print(server.ui_url)  # http://127.0.0.1:4747
```

The [home page](index.md) embeds a live, static snapshot of the UI.

## Topology

Each node is identified by its `opendataframework` key, `<namespace>.<name>`
(`task.load-job`, `agent.librarian`), so two classes with the same name in
different namespaces stay apart.

Dragging a node to a new cell, changing its icon or color, and adding cells to
the grid are saved to `layout.json` in the working directory, or the file named
by `[project] layout-file`. Commit it to share a layout. Icons are stored by key,
so a node whose icon key no longer exists falls back to its type's default.

### Flat grid

`[ui] grid = "flat"` draws the topology as a flat, top-down schematic instead of
the isometric grid: square cells marked by a faint dot where a node snaps, and
every node a rounded square in its type's color with that type's glyph on it
(sliders for config, a package for a component, a rack for a repository, and so
on), which keeps a large topology readable. Columns run right and rows down, so
a node keeps its cell in both grids and switching never moves anything.

**Customize** on the flat grid picks one of the flat glyphs (the type defaults
plus a few symbols: database, cloud, bolt, star, flag, lock, user, chart) and a
color. The glyph is saved in `layout.json` as `flatIcon`, apart from the
isometric `icon`, so each grid keeps its own choice. The color is shared by
both grids. The theme still applies through its colors and icon face style.
See
[`examples/25-flat-grid`](https://github.com/opendataframework/odf/tree/main/examples/25-flat-grid).

### Run activity

The topology shows what the project is doing as it happens, whoever started
the work: a button in the UI, an MCP client, chat, a pipeline running its
steps, or a service's `run()` loop.

- An edge animates only while a call goes through it: a pipeline running one
  of its steps, a task calling a function, or a task, pipeline, agent or
  function using a repository, component or service it depends on. Idle edges
  stay still.
- A node running a call (a task's or pipeline's `execute()`, an agent's
  `invoke()`, a function call, a service's `setup()` or `stop()`) gets a ring
  around its tile. When the call completes, the ring and a ✓ fade out after a
  few seconds. A failed call leaves a red ring and a `!` (with a count if it
  keeps failing), which stays until you select the node.
- A failure also pops a notice in the top-right corner, with the error and a
  **Show logs** button that opens the node's logs at the run, highlighting its
  lines. It stays until closed. A step's failure is reported by its pipeline
  when the pipeline fails too. A success pops a notice only for an action you
  started in that tab, from its buttons or its chat, and closes by itself.
- The header status, **System Nominal** when idle, tells the same story where
  nothing covers it, such as when the chat drawer hides the notices. It shows
  the call that's running (`Loader executing`, with `+2` when others run
  alongside it), a failure until the node is selected (click it to open the
  node's logs at the run), and a completed call for a few seconds
  (`Loader executed in 1.2 s`).
- A service's **Start**/**Stop** button follows the service, so it's correct
  after a start or stop over MCP or chat too.

With the system's reduced-motion setting on, nothing moves: edges in use are
drawn brighter instead of carrying a pulse, and a running node's ring holds
still. The run state comes from `GET /api/events` (see [HTTP API](#http-api)).

### Choosing what the topology shows

By default the topology shows every component and every connection between
them. The `[ui.topology]` table in config narrows that:

```toml
[ui.topology]
connections = false                  # default true: draw links between components
config = false                       # default true: show the Config node
repositories = ["readings"]          # only these repositories
tasks = ["seed-readings"]            # only these tasks
agents = []                          # no agents
functions = ["load-data"]            # only these functions
components = []                      # no plain components (e.g. a Storage component)
```

`repositories`, `services`, `tasks`, `pipelines`, `agents`, `functions` and `components` each take
registered names, the name part of each key (`seed-readings` for
`task.seed-readings`), in any casing. A kind without a list shows all of its
components; a kind with a list shows only the listed ones, and an empty list
hides the kind. A component added later to a kind that has a list stays hidden
until it is added to that list. A `Storage` component counts as a plain
`component`.

When a component is hidden, the components that depend on it are linked to
whatever it depends on, so the remaining graph keeps its shape. The remaining
nodes are laid out again without gaps. A node whose saved grid position is
taken by another node moves to the nearest free row in its column; those
adjustments are not written to the layout file. Hidden components keep
running and stay available through MCP and chat; only the topology view
changes. Unknown keys and values of the wrong type raise a `ValueError` when
the UI starts, and a listed name that matches no component produces a warning.
See
[`examples/04-data-engineering`](https://github.com/opendataframework/odf/tree/main/examples/04-data-engineering).

## Data views

Repositories can declare a `data_view()` to pick how their data renders
(table, map, timeseries, image, video, audio, document, streaming video/audio)
instead of the default table. The view types themselves are documented upstream
in [View](https://opendataframework.github.io/opendataframework/view/); the
[Examples](examples.md) page has one example per view (01, 06–13, 21).

A repository whose view shows content (an image, video, audio or document
view) can also implement
[`content_metadata(entity)`](https://opendataframework.github.io/opendataframework/view/)
to name and type each record's content. A declared `content_type` is served
instead of the type worked out from the bytes, as long as it fits the view:
an image view only takes an image type, never SVG, and a document is still
only ever served as a PDF, plain text or a download. A declared `filename`
labels the record's card and its caption, is sent as `Content-Disposition`,
and names the file the **Download** action saves. A text document declared
as Markdown, by a `text/markdown` type or a `.md` name, is rendered, and one
declared as anything else is shown as written. Records list it, under a
`$content` key, so the UI has it without a request per record. See
[`examples/12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view).

### Grouped timeseries

A timeseries view plots numeric fields against an ordering `field`: a
timestamp, or any number records are ordered by, such as a training step.
`fields` names which numeric fields to plot (every other numeric field when
unset), and `group` names a field whose distinct values each get their own
line:

```python
def data_view(self) -> TimeseriesView:
    return TimeseriesView(field="step", fields=("loss", "accuracy"), group="run_id")
```

Grouped, the chart colors each group and dashes each field, and every group
shares its field's y axis, so groups compare on one chart. The legend lists
the fields and then the groups. Click one to hide or show it. The chart
shows one page of records, like the table, so a group can be split across
pages. Returning records sorted by group, then by `field`, keeps whole groups
together where a page can hold them, and a larger page size shows more at
once. See the [`ml` template](init-templates/ml.md) and
[`examples/22-ml`](https://github.com/opendataframework/odf/tree/main/examples/22-ml).

### Notebooks

A Jupyter notebook in a document view opens as its cells and their saved
outputs: Markdown cells rendered, code as written, images inline, and HTML
outputs such as a DataFrame shown with anything that could run removed.
**View source** shows its JSON. A record counts as a notebook when its content
parses as one; declaring an `.ipynb` name or the `application/x-ipynb+json`
type also makes its card preview the cells instead of the JSON.

When the `notebook` package is installed in the project's environment
(`pip install odf[notebook]`), a notebook kept as a file (`bytes`) in a
writable repository can also be edited in place: **Edit in Jupyter** in the
reader's rail swaps the rendered notebook for Jupyter Notebook's own editor,
with kernels and extensions as in a local notebook server. Jupyter is
started the first time a notebook is edited, by the same interpreter as the
UI, on a free port of `127.0.0.1` with a random token, and is stopped with
the UI. The browser never reaches that port: the UI forwards `/proxy/jupyter/`
to Jupyter, HTTP and WebSockets, so the editor is served on the UI's own
address, and Jupyter is never exposed on the network, whatever host the UI
binds to. Kernels' traffic to Jupyter is encrypted (CurveZMQ) when pyzmq and
the kernel support it, as they do with `odf[notebook]`'s Python kernel. Kernels start in the directory `odf run` was started from, so a cell
can `import app` or open `data/...` the same way the project does.

Jupyter reads and saves each notebook through the repository, as
`PUT /api/repositories/{name}/records/{key}/media`, which calls `save()` with
the record's document field replaced. Where a notebook ends up is therefore up
to the repository: a file, a database row, an object store. Notebooks autosave
every 5 seconds unless your Jupyter settings say otherwise, since closing the
editor or moving to another record drops it. Notebooks can't be created,
renamed or deleted from Jupyter; that is done to the records, in the UI. In
Jupyter's file browser each repository is a folder, with a folder per record
holding its notebook. The editor opens in JupyterLab Light or JupyterLab Dark,
whichever matches the UI's mode, and toggling the mode while it's open saves
the notebook and reloads the editor in the other one; its kernel keeps
running. A `theme` in your own Jupyter settings wins over both, and the UI
saves nothing to them. `[ui] notebooks = false` turns editing off. See
[`examples/21-notebook-view`](https://github.com/opendataframework/odf/tree/main/examples/21-notebook-view).

Behind a reverse proxy (HTTPS, a login), Jupyter needs nothing of its own: a
login in front of the UI covers it too. Jupyter's token never reaches the
browser: the UI adds it to each request it forwards to Jupyter, and Jupyter
accepts no other, so its pages send no `Authorization` header of their own
that would replace a Basic auth login's. See [Deploying](#deploying) for what
the proxy has to pass on.

Since Jupyter's pages share the UI's origin, script output of a notebook
Jupyter trusts (one you ran yourself) can call the UI's HTTP API. That doesn't
give a notebook more than its kernel has, which already runs code as the
project, but open in Jupyter only notebooks you would run anyway.

A component implementing `details()` gets a details panel, and one implementing
`chart()` a **View Chart** button (see
[`examples/14-chart`](https://github.com/opendataframework/odf/tree/main/examples/14-chart)).

## Labelling data

The views can label records for the simple cases a one-off script would
otherwise be written for: training data, events, regions of interest, a
good/bad split. Labels are picked from a tool rail (or the keyboard), typed once
and then picked from a list, and a label no mark uses any more is dropped.

| View | What can be labelled | Keys | Format described in |
|---|---|---|---|
| Image | Boxes, freely drawn or of one fixed size | `B` box, `F` fixed-size box | [`11-image-view`](https://github.com/opendataframework/odf/tree/main/examples/11-image-view#annotating) |
| Document | Text spans, and boxes on a PDF page | `T` text, `B` box | [`12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view#annotating) |
| Video, audio | Time ranges and points on the clip's timeline | `R` range, `P` point, `M` mark at the playhead | [`10-audio-view`](https://github.com/opendataframework/odf/tree/main/examples/10-audio-view#annotating) |
| Timeseries | Time ranges and points on the chart | `R` range, `P` point | [`13-timeseries-view`](https://github.com/opendataframework/odf/tree/main/examples/13-timeseries-view#annotating) |
| Location | Rectangular regions on the map | `B` region | [`06-location-view`](https://github.com/opendataframework/odf/tree/main/examples/06-location-view#annotating) |

In every view `V` picks the **Select** tool, which adds nothing: it moves the
map, or leaves text to be selected and copied. Select a mark to delete it, or its
label to change it.

A record can also be given one **class**: from the row of classes under an
open image, document or clip (`1` to `9` pick one), or from the table view's
`class` column. See
[`11-image-view`](https://github.com/opendataframework/odf/tree/main/examples/11-image-view#classifying).

Everything is saved to `annotations.json` in the working directory, or the file
named by `[project] annotations-file`, as one block per repository, keyed by
its registered name. The file is plain JSON, so a later pipeline reads it with
`json.load` and no `odf` import. Images use pixel coordinates with the image's
size, document spans character offsets into the text, PDF boxes points with the
page's size, clips seconds with the clip's length, timeseries the timestamp
field's own units, and map regions degrees. `[ui] annotations = false` turns
labelling off.

## Arguments: Invoke and Call

An `@Agent`'s node has an **Invoke** action, and an `@Function`'s node a
**Call** action. Each opens a form with one field per argument, prefilled with
the defaults, and shows the result under it. An agent's arguments are those of
its `invoke()`. A function's are its own, less the parameters the `Context`
injects. A `str`, number or `bool` argument gets an input of that kind, and
any other type a JSON field. Values are converted to the annotated types
before `context.call()` makes the call, and a value that doesn't fit is
reported under the form without making it. See
[`examples/19-agent`](https://github.com/opendataframework/odf/tree/main/examples/19-agent)
and
[`examples/20-function`](https://github.com/opendataframework/odf/tree/main/examples/20-function).

## Themes, icons and branding

The UI ships four themes: `default`, `glitch`, `emerald` and `onyx`.
Pick one with `odf run --theme <name>`, `server.start(theme=...)`, or
`[ui] theme` in config. A theme only restyles the UI; markup and behavior are
the same in every theme. An unknown theme name raises a `ValueError` at start.

Each theme also has its own icon look: `default` keeps thin outlines over
faint faces, `emerald` tints faces more strongly with a soft shadow under a
lit icon, `glitch` draws near-black solids with bright edges, and `onyx`
tonal solids with no
outlines at all. A theme's `theme.js` sets this through
`ODF.registerTheme({ faces: {...} })`, whose knobs are listed on
`THEME_STYLE.faces` in `app.js`. It can also replace how empty grid tiles are
drawn with `emptyTile(sx, sy)`, and fill opaque faces with its own style, such
as a gradient spanning the whole icon, with
`faceFill(side, accent, lit, t, frame)`, where `frame` is the icon's
`{x, top, bottom}` on the canvas. It can draw on the floor under each icon,
such as a shadow, with `groundShadow(x, y, e, accent, lit)`, where `e` is the
icon's registry entry (its `widthExtent` and `scale` give the footprint).

### Custom themes

A project can bring its own theme by giving `[ui] theme` (or `--theme` /
`theme=`) a path to a directory instead of a name:

```toml
[ui]
theme = "./my-theme"
```

The value counts as a path when it contains a `/` or `\`, or starts with `.`
or `~`. A built-in theme's name always selects that built-in theme. A relative
path is resolved against the working directory, like `[ui] favicon` and
`[ui] logo`. The directory holds the same files as a built-in theme:

| File | Required | Contents |
|---|---|---|
| `theme.css` | yes | The whole stylesheet. Themes share no styles, so it has to style everything |
| `favicon.svg` | yes | The theme's favicon (`[ui] favicon` still overrides it) |
| `theme.js` | no | Canvas styling through `ODF.registerTheme()`, as described above |

The easiest start is to copy a built-in theme, such as
[`themes/default/`](https://github.com/opendataframework/odf/tree/main/src/odf/ui/static/themes/default),
and edit it. A missing directory or required file raises a `ValueError` at
start.

For pixel art, `theme.js` can set `ODF.registerTheme({ pixelSize: 2 })` to
draw the topology canvas with one canvas pixel per 2×2 CSS pixels. Pair it
with `#canvas { image-rendering: pixelated }` in `theme.css`, so the canvas
is scaled back up without smoothing. Without `pixelSize`, the canvas is
drawn at the screen's own resolution. At a coarse `pixelSize`, the node
labels drawn on the canvas get hard to read, so a theme can also set
`labelFont` (a CSS font family) and `labelSize` (in CSS pixels, default
`9.5`) for them, such as a pixel font at a size it was designed for.
`labelSnap: true` keeps that size at any zoom and puts the labels and run
badges on whole canvas pixels, so a pixel font stays crisp. Pick a
`labelSize` at which one of the font's pixels is one canvas pixel. Three more
knobs help labels read over busy tiles: `labelAlpha` (the opacity of a label
whose node isn't hovered or selected, default `0.45`), `labelShadow: true`
(a hard one-pixel drop shadow in the tile-stroke color) and
`labelBold: false` (no bold for lit labels, for a font without a bold face,
since a synthesized bold smears it). See
[`examples/24-custom-theme`](https://github.com/opendataframework/odf/tree/main/examples/24-custom-theme),
which ships eleven themes in its own directories: a pixel-art one in
`themes/pixel/`, a late-90s theme-park one in `themes/park/`, a 1980s
neon-coast one in `themes/neon/`, and `themes/terminal/`, `themes/y2k/`,
`themes/meadow/`, `themes/beacon/`, `themes/ledger/`, `themes/clay/`,
`themes/workbench/` and `themes/brutalist/`. Only the first two set `pixelSize`.

A node's icon and color can be changed from its "Customize" popover, which
lists the built-in isometric icons by group (devices, buildings, charts,
research, ML, shop). Icons and colors can be extended beyond the built-in
set via `[ui] icon-scripts` / `[ui.colors]` in config, or by packages
registering into `odf.ui.extensions`. The favicon, header logo, and "ODF" brand
label can likewise be overridden with `[ui] favicon` / `[ui] logo` /
`[ui] brand`. A custom icon drawn with `ODF.iconKit`'s solids (`block`,
`stepped`, `gable`, `wedge`, `cylinder`) or with `paintFace()` takes on each
theme's icon look; details drawn on a solid's wall inside `iconKit.onFace()`
use the theme's face ink (`faceInk(accent)`), so they stay visible on opaque
faces. See
[`examples/17-custom-icon`](https://github.com/opendataframework/odf/tree/main/examples/17-custom-icon).

## Configuration

Every key `odf` reads from `config.toml`:

| Key | Default | Description |
|---|---|---|
| `[ui] theme` | `"default"` | UI theme name, or a path to a theme directory (see [Custom themes](#custom-themes)); `--theme` / `theme=` override it |
| `[ui] grid` | `"iso"` | Topology grid: `"iso"` or `"flat"` (see [Flat grid](#flat-grid)); any other value raises a `ValueError` |
| `[ui] icon-scripts` | `[]` | `.js` files registering extra icons |
| `[ui.colors]` | — | Named color swatches added to the color picker |
| `[ui] favicon`, `[ui] logo` | built-in | Image files replacing the favicon and header logo |
| `[ui] brand` | `"ODF"` | Brand label in the header |
| `[ui] annotations` | `true` | Allow labelling data in the views |
| `[ui] notebooks` | `true` if `notebook` is installed | Edit notebooks in the document view with Jupyter (see [Notebooks](#notebooks)); `true` without `notebook` installed raises an `ImportError` |
| `[ui.topology]` | show everything | What the topology shows (see [above](#choosing-what-the-topology-shows)) |
| `[project] layout-file` | `"layout.json"` | Where node positions, icons and colors are saved |
| `[project] annotations-file` | `"annotations.json"` | Where labels and classes are saved |
| `[project.chat]` | — | Chat model and Ollama host (see [Chat](chat.md#configuration)) |

## Deploying

The UI has no login of its own. To serve a project beyond your machine, put
it behind a reverse proxy that does HTTPS and the login, and keep the UI's
port off the network: `--ui-host 127.0.0.1` (the default) with the proxy on
the same machine, or a port only the proxy's container network reaches. The
embedded Jupyter is served through the UI on the same origin (see
[Notebooks](#notebooks)), so the login covers it too, with nothing
Jupyter-specific in the proxy.
[`examples/23-reverse-proxy`](https://github.com/opendataframework/odf/tree/main/examples/23-reverse-proxy)
runs all of this with `docker compose up`: odf in one container, Traefik in
front of it with HTTPS, a login, and MCP at `/mcp`.

Serve the UI at the root of a host: it can't run under a subpath such as
`example.com/odf/` yet. If the domain serves other things, give odf its own
subdomain, such as `odf.example.com`.

The proxy has to pass WebSocket upgrades on (Jupyter's kernels use them),
pass the host the browser asked for on as `X-Forwarded-Host` (the UI refuses
saves, Runs and Jupyter's WebSockets otherwise, see below), stream responses
as they come (`GET /api/events` is a long-lived stream), and accept request
bodies as large as your notebooks, since saving one sends it whole.
[Traefik](https://doc.traefik.io/traefik/) does all of that by default, so a
route to the UI is all it needs, here in its file provider's TOML:

```toml
[http.routers.odf]
rule = "Host(`odf.example.com`)"
entryPoints = ["websecure"]
service = "odf"
[http.routers.odf.tls]

[http.services.odf.loadBalancer]
passHostHeader = false
[[http.services.odf.loadBalancer.servers]]
url = "http://127.0.0.1:4747"
```

`passHostHeader = false` leaves `Host` to the upstream's own,
`127.0.0.1:4747`, with the browser's host in `X-Forwarded-Host`: a UI bound to
a loopback address only answers loopback hosts (see below). In a container,
with `--ui-host 0.0.0.0`, the server's `url` names the UI's container instead
(`http://odf:4747`); the rest stays the same.

### Adding a login

The simplest login is the proxy's own Basic auth, a browser prompt checked
against a password file (`htpasswd -cB /etc/traefik/users alice`). Add a
`basicAuth` middleware to the router above:

```toml
[http.routers.odf]
# ...
middlewares = ["login"]

[http.middlewares.login.basicAuth]
usersFile = "/etc/traefik/users"
```

For a login with your identity provider (any OpenID Connect one: Google,
GitHub, Microsoft Entra, Keycloak, ...), run an authenticating proxy such as
[oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) next to Traefik,
here at `oauth2-proxy:4180` started with `--reverse-proxy` and
`--upstream=static://202`. Traefik asks it about every request with
`forwardAuth`, shows its sign-in page to a browser that isn't signed in, and
routes its own pages to it:

```toml
[http.routers.odf]
# ...
middlewares = ["sign-in", "login"]

[http.routers.oauth2]
rule = "Host(`odf.example.com`) && PathPrefix(`/oauth2/`)"
entryPoints = ["websecure"]
service = "oauth2-proxy"
[http.routers.oauth2.tls]

[http.middlewares.login.forwardAuth]
address = "http://oauth2-proxy:4180/oauth2/auth"

[http.middlewares.sign-in.errors]
status = ["401"]
service = "oauth2-proxy"
query = "/oauth2/sign_in?rd={url}"

[[http.services.oauth2-proxy.loadBalancer.servers]]
url = "http://oauth2-proxy:4180"
```

Only 401, the login's answer, gets the sign-in page, so the UI's own 403s
(below) pass through as they are. Authelia, Authentik and Cloudflare Access
work the same way.

### Cross-site requests and DNS rebinding

A login at the proxy is a cookie, or credentials the browser remembers, which
the browser sends with every request to the UI, including requests a page on
another site makes it send. So the UI refuses a request that could change
something (any method but `GET`, `HEAD` and `OPTIONS`, and every WebSocket,
Jupyter's included) when its `Origin` isn't the host the UI was reached by:
the `Host` header, or `X-Forwarded-Host` if the proxy sets it. HTTP requests
get a 403, WebSockets are closed before they open. Requests with no `Origin`,
from scripts or `curl`, aren't affected.

A page can also point its own name at your machine (DNS rebinding), so that
to the browser its requests to a local UI are same-origin ones. So a UI bound
to a loopback address (`127.0.0.1`, the default) only answers requests whose
`Host` is `127.0.0.1`, `localhost` or `[::1]`, on any port; any other answers
421. Bound to any other address, as in a container, the UI answers every
`Host`. Behind a proxy on the same machine this is why the proxy leaves `Host`
to the upstream, as `passHostHeader = false` does, and passes the browser's
host as `X-Forwarded-Host` instead.

### MCP

The [MCP server](mcp.md) listens on its own port and has no login either, but
the same proxy can serve it next to the UI, on the same certificate, at
`https://odf.example.com/mcp`:

```toml
[http.routers.mcp]
rule = "Host(`odf.example.com`) && PathPrefix(`/mcp`)"
entryPoints = ["websecure"]
middlewares = ["login"]
service = "mcp"
[http.routers.mcp.tls]

[http.services.mcp.loadBalancer]
passHostHeader = false
[[http.services.mcp.loadBalancer.servers]]
url = "http://127.0.0.1:4748"
```

Traefik streams the MCP server's event streams with no setting of its own.
`Host` is left to the upstream (`127.0.0.1:4748`), which the MCP server
accepts: like the UI, bound to a loopback address it only answers loopback
hosts. MCP clients can't go through a browser login, so this router checks a
header the client sends itself instead. With Basic auth, as above, that's
credentials configured in the client:

```bash
claude mcp add --transport http my-project https://odf.example.com/mcp \
  --header "Authorization: Basic $(printf 'alice:secret' | base64)"
```

With oauth2-proxy, use the `login` middleware here too, without `sign-in`,
and start oauth2-proxy with `--skip-jwt-bearer-tokens`, so a client sending a
token from your identity provider (`Authorization: Bearer ...`) is let
through. In a container, with `--mcp-host 0.0.0.0`, the server's `url` names
the MCP server's container instead.

### nginx and other proxies

Other proxies need set by hand what Traefik does by default. With nginx, the
UI's `location` passes upgrades on, sets `X-Forwarded-Host` (`proxy_pass`
already leaves `Host` to the upstream) and raises the request body limit:

```nginx
location / {
    proxy_pass http://127.0.0.1:4747;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header X-Forwarded-Host $http_host;
    client_max_body_size 100m;
    auth_basic "odf";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

`GET /api/events` needs nothing more: the UI sends `X-Accel-Buffering: no`
with it, so nginx passes events on as they happen. The MCP server's `location`
turns buffering off itself, since its responses can be event streams, and
keeps a client's stream open:

```nginx
location /mcp {
    proxy_pass http://127.0.0.1:4748;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 1h;
    auth_basic "odf MCP";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

nginx's `auth_request` to oauth2-proxy takes the place of `forwardAuth`, with
`error_page 401 = /oauth2/sign_in;` as the sign-in page. Caddy
(`forward_auth`) and other proxies need the same: upgrades, `X-Forwarded-Host`
with `Host` left to the upstream, no buffering on the event streams, and a
body limit as large as your notebooks.

## HTTP API

The UI's HTTP API serves each execution type as its own collection, by
registered name:

| Route | For |
|---|---|
| `GET /api/{collection}/{name}/logs` | any component (`components`, `repositories`, `services`, `tasks`, `pipelines`, `agents`, `functions`) |
| `GET /api/{collection}/{name}/details`, `.../chart` | a component implementing `details()` / `chart()` |
| `POST /api/services/{name}/start`, `.../stop` | a `@Service` |
| `POST /api/tasks/{name}/execute`, `/api/pipelines/{name}/execute` | a `@Task` / `@Pipeline` |
| `GET /api/agents/{name}/parameters`, `POST .../invoke` | an `@Agent` |
| `GET /api/functions/{name}/parameters`, `POST .../call` | an `@Function` |
| `/api/repositories/{name}/records`, `.../stream`, ... | a `@Repository`'s data |
| `PUT /api/repositories/{name}/records/{key}/media` | replacing a document file through `save()` (see [Notebooks](#notebooks)) |
| `POST /api/notebooks/session` | starting Jupyter for notebook editing; returns the `url` it is served at through the UI (`/proxy/jupyter/`) |
| `/proxy/jupyter/...` | Jupyter itself, HTTP and WebSockets, while notebook editing is on |
| `GET /api/events` | every protocol call the project makes, as server-sent events (see below) |

The collection comes from the execution type, not the key's namespace: a `@Task`
registered as `loader` is `/api/tasks/loader`, whatever its key. An action that
doesn't apply to a kind has no route, so it answers `404`.

`GET /api/events` streams `opendataframework`'s
[`Event`s](https://opendataframework.github.io/opendataframework/events/) as
`text/event-stream`, one `data:` line of JSON per call state change, from the
moment the client connects:

```json
{"type": "call", "key": "task.load-job", "protocol": "TaskProtocol", "method": "execute",
 "state": "completed", "call_id": "…", "parent": "…", "ts": 1792776224.61,
 "elapsed_ms": 203.7, "error": null}
```

`state` is `started`, `completed` or `failed`. A call's `started` and its
`completed`/`failed` share a `call_id`, and `parent` is the `call_id` of the
call it was made from (`null` for a top-level call). A client that falls more
than 1000 events behind gets `{"type": "reset"}` in place of what it missed.
