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
[Examples](examples.md) page has one example per view (01, 06–13).

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

The UI ships five themes: `default`, `glitch`, `neo`, `emerald` and `onyx`.
Pick one with `odf run --theme <name>`, `server.start(theme=...)`, or
`[ui] theme` in config. A theme only restyles the UI; markup and behavior are
the same in every theme. An unknown theme name raises a `ValueError` at start.

A node's icon and color can be changed from its "Customize" popover, which
lists the built-in isometric icons by group (devices, buildings, charts,
research, ML, shop). Icons and colors can be extended beyond the built-in
set via `[ui] icon-scripts` / `[ui.colors]` in config, or by packages
registering into `odf.ui.extensions`. The favicon, header logo, and "ODF" brand
label can likewise be overridden with `[ui] favicon` / `[ui] logo` /
`[ui] brand`. See
[`examples/17-custom-icon`](https://github.com/opendataframework/odf/tree/main/examples/17-custom-icon).

## Configuration

Every key `odf` reads from `config.toml`:

| Key | Default | Description |
|---|---|---|
| `[ui] theme` | `"default"` | UI theme; `--theme` / `theme=` override it |
| `[ui] icon-scripts` | `[]` | `.js` files registering extra icons |
| `[ui.colors]` | — | Named color swatches added to the color picker |
| `[ui] favicon`, `[ui] logo` | built-in | Image files replacing the favicon and header logo |
| `[ui] brand` | `"ODF"` | Brand label in the header |
| `[ui] annotations` | `true` | Allow labelling data in the views |
| `[ui.topology]` | show everything | What the topology shows (see [above](#choosing-what-the-topology-shows)) |
| `[project] layout-file` | `"layout.json"` | Where node positions, icons and colors are saved |
| `[project] annotations-file` | `"annotations.json"` | Where labels and classes are saved |
| `[project.chat]` | — | Chat model and Ollama host (see [Chat](chat.md#configuration)) |

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

The collection comes from the execution type, not the key's namespace: a `@Task`
registered as `loader` is `/api/tasks/loader`, whatever its key. An action that
doesn't apply to a kind has no route, so it answers `404`.
