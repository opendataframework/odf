# Release Notes

## 0.3.0

### Added

- **UI**: `onyx` theme, a monochrome graphite take on Material Design 3, in both
  light and dark mode. Select it with `odf run --theme onyx` or
  `[ui] theme = "onyx"` in `config.toml`. See [CLI](cli.md).
- **UI**: 51 more built-in topology icons, and an icon picker split into group tabs:
  `Defaults`, `Devices`, `Buildings`, `Charts`, `Research`, `ML` and `Shop`. Icons added
  through `[ui] icon-scripts` are listed under `Custom`, or under the group named by the
  optional `group` in `ODF.registerIcon(key, draw, meta)`. The helpers the built-in icons
  are drawn with are available to custom icon scripts as `ODF.iconKit`.

- **UI**: selecting a thumbnail in the image view opens that image full size, with the
  record's other fields as a caption, previous/next buttons (or the arrow keys), and
  the close button in the corner or `Esc` to return to the grid. Images are now served with the media type detected from
  their bytes (JPEG, PNG, GIF, WebP, BMP, TIFF, AVIF, HEIC) instead of always
  `image/jpeg`, and an image the browser can't decode, such as HEIC outside Safari, is
  labelled with its type instead of showing a broken-image icon.
- **UI**: labelled boxes can be drawn on an open image in the image view. Pick `Draw a
  box` in the tool rail at the top left of the image, drag to draw a box and type its label, or pick one already used from the list under the input; select a box to delete it,
  or select its label to change it. A box inside a larger one stays on top, so it can
  still be selected. With `Place a fixed-size box` picked in the rail, every new box takes the
  width and height set beside it, in image pixels, for algorithms that need boxes of one
  size: click or drag to place one centred on the pointer, kept whole inside the image. A label no box uses any more is dropped from the list. Boxes are saved to `annotations.json`, or the file
  named by `[project] annotations-file` in `config.toml`, as pixel coordinates with each
  image's size and an ordered label list per repository, for a later pipeline to read
  with `json.load`. The
  [`11-image-view`](https://github.com/opendataframework/odf/tree/main/examples/11-image-view)
  example describes the format. `[ui] annotations = false` in `config.toml` turns
  annotating off.
- **UI**: the video and audio views list their records as cards, like the image view: a
  video card previews a frame of its clip, an audio card its waveform (for clips up to
  10 MB), both with the clip's length. Selecting a card opens the clip in a player and
  starts it, with the record's other fields as a caption, previous/next buttons, and
  the close button in the corner or `Esc` to return to the grid. Clips are now served with the media type detected from
  their bytes (MP4, QuickTime, WebM, Ogg, AVI, WAV, MP3, AAC, FLAC) instead of always
  `video/mp4` or `audio/wav`, and with `Range` requests honored, so a clip can be seeked
  and plays in Safari. A clip the browser can't decode is labelled with its type.
- **UI**: the document view lists its records as cards, like the image view, each
  previewing the start of its document. Selecting a card opens the document, with the
  record's other fields as a caption, previous/next buttons (or the arrow keys), and
  the close button in the corner or `Esc` to return to the grid. A `DocumentView` field can now hold a file as well as a
  JSON-shaped value: `bytes` are shown as a PDF (drawn by pdf.js, loaded from a CDN when
  first needed) or as text, detected from their content, and a `str` as text, while a
  `dict` or `list` is still a collapsible tree. Text that parses as JSON, such as a
  `.json` file, is a tree as well, and text that reads as Markdown is rendered, each with
  a button to switch to its source and back. Bytes of any other type are labelled
  with that type and can be downloaded. The
  [`12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view)
  example shows each kind.
- **UI**: an open document in the document view can be labelled. With `Label text` picked
  in the tool rail, select text to label that span of it, or with `Draw a box` drag on a
  PDF page to draw a labelled box, as on an image; select a
  span or a box to delete it, or select its label to change it. Spans are drawn on text as
  it is written, so `Label text` shows a Markdown or JSON document as its source, and spans
  don't overlap. An image or document opens on the `Select` tool, which adds nothing and
  leaves selected text to be copied; the tool picked is remembered in the browser, and
  `V`, `B`, `F` and `T` pick one from the keyboard. A `dict` or `list` document takes no labels. They are saved to the same
  `annotations.json` as image boxes: a span as its start and end in the text, counted in
  characters as Python indexes a `str`, with the text it covers, and a page box in PDF
  points with its page number and the page's size. The
  [`12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view)
  example describes the format. `[ui] annotations = false` in `config.toml` turns
  annotating off.
- **UI**: time ranges and points can be labelled on the chart of the timeseries view, for
  the simple cases a one-off script would otherwise be written for, such as a stretch to
  train on or leave out, an event, or a bad reading. Pick `Label a range` (`R`) beside the
  legend and drag across the chart, or `Label a point` (`P`) and click to mark the nearest
  record, then type a label or pick one already used; select a mark to delete it, or select
  its label to change it. A mark covers every series and ranges may overlap. They are saved
  to the same `annotations.json` as image boxes, as one list per repository: a range as its
  start and end in the timestamp field's own units, and a point as its record's timestamp
  and key. The
  [`13-timeseries-view`](https://github.com/opendataframework/odf/tree/main/examples/13-timeseries-view)
  example describes the format. `[ui] annotations = false` in `config.toml` turns
  annotating off.
- **UI**: time ranges and points can be labelled on a clip open in the video and audio
  views, for marking its segments and events, such as speech, an action or an onset. A
  timeline under the player spans the clip, with its waveform for audio and a line where
  it is playing. Pick `Label a range` (`R`) in the tool rail and drag on the timeline, or
  `Label a point` (`P`) and click it, then type a label or pick one already used. `M` marks
  where the clip is playing instead, which is finer on a long clip: a point, or one end of
  a range and then the other. Select a mark to delete it, or select its label to change
  it; a click elsewhere on the timeline seeks the clip there. Marks are saved to the same
  `annotations.json`, per record, in seconds from the start of the clip with the clip's
  length beside them. The
  [`10-audio-view`](https://github.com/opendataframework/odf/tree/main/examples/10-audio-view)
  example describes the format. `[ui] annotations = false` in `config.toml` turns
  annotating off.
- **UI**: labelled regions can be drawn on the map of the location view, for "everything
  inside this area", such as a region of interest, a geofence or a split by area. Pick
  `Draw a region` (`B`) at the top right of the map, drag out a rectangle and type its
  label or pick one already used. With `Select` (`V`) the map moves as before: select a
  region to delete it, or select its label to change it. A region inside a larger one
  stays on top. Regions are saved to the same `annotations.json`, as one list per
  repository, each as its south, west, north and east bounds in degrees. The
  [`06-location-view`](https://github.com/opendataframework/odf/tree/main/examples/06-location-view)
  example describes the format. `[ui] annotations = false` in `config.toml` turns
  annotating off.
- **UI**: a record can be given a class, for simple classification such as good or bad,
  relevant or not. Under an image, document, video or audio clip open from its grid there
  is a row of the repository's classes: select one, or press its number (`1` to `9`), to
  give it to the open record, select `+` to add a class, and select the record's own class
  to take it away. The grid shows each record's class on its card. The table view has a
  `class` column with the same choice per row. A record has one class, and a class no
  record has any more is dropped from the list. Classes are saved to the same
  `annotations.json`, apart from box, span and range labels, as a map from record key to
  class with the list of classes in use. The
  [`11-image-view`](https://github.com/opendataframework/odf/tree/main/examples/11-image-view)
  example describes the format. `[ui] annotations = false` in `config.toml` turns
  it off.
- **Agents**: `@Agent` classes (new in `opendataframework` 0.3.0) appear in the topology
  as `agent` nodes, with their own default icon and color, an entry in the type legend
  under the canvas, an `Agents` count in the header, and an `agents` list in `[ui.topology]`. A node's **Invoke** action opens a
  form built from the agent's `invoke()` arguments and shows the result. Over MCP each
  agent is its own tool, `<key>.invoke` (`agent.librarian.invoke`), with `invoke()`'s
  signature as its input schema, and `@agent.librarian` in the chat keeps that tool
  available for the message. Every
  call goes through `context.call()`, so it is logged to the agent's log. See the
  [`19-agent`](https://github.com/opendataframework/odf/tree/main/examples/19-agent)
  example.
- **Functions**: `@Function` functions (new in `opendataframework` 0.3.0) appear in the
  topology as `function` nodes, with their own default icon and color, an entry in the
  type legend under the canvas, and a `Functions` count in the header. They are linked to the components injected into them and to the
  classes and functions that ask for them through `Annotated[Callable[...], func]`. A
  `functions` list in `[ui.topology]` filters them. A node's **Call** action opens the
  same form as an agent's **Invoke**, with one field per argument the function takes
  beyond its injected ones, and calls it through `context.call()`. Over MCP each
  function is its own tool, `<key>.call` (`function.load-data.call`), with the same
  arguments as its input schema, and `@function.load-data` in the chat keeps that tool
  available for the message. `list_components` lists functions, with a `verb` on every
  entry that has such a tool. The logs of their calls are served at
  `/api/functions/{name}/logs` and by `component_logs`. See the
  [`20-function`](https://github.com/opendataframework/odf/tree/main/examples/20-function)
  example.
- **View**: a repository implementing `content_metadata(entity)` (`ContentMetadata`, new
  in `opendataframework` 0.3.0) names and types its records' content in the image,
  video, audio and document views. A declared `content_type` is served instead of the
  type detected from the bytes when it fits the view, and a document is still only ever
  a PDF, plain text or a download. A declared `filename` labels the record's card and
  its caption when open, is sent as `Content-Disposition`, and names the file saved by
  the new **Download** action in the open record's tool rail. A text document declared
  as Markdown (`text/markdown` or a `.md` name) is rendered, and one declared as
  anything else is shown as written, instead of either being judged by its text. The
  records payload
  carries both under a `$content` key. See the
  [`12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view)
  example.

### Changed

- **Deps**: requires `opendataframework >=0.3.0,<0.4.0`. Upstream addresses every
  component by its `<namespace>.<name>` key and adds `@Agent`, `@Function` and
  `ContentMetadata`, which the entries above and below build on.
- **UI**: the Activity and Chat buttons moved from the top-right corner of the map into
  the header bar, as icon buttons next to the theme toggle. They no longer cover a
  view's own controls, such as the table view's timeline dropdown and replay controls,
  and the button of the open drawer stays highlighted.
- **UI**: the popup shown when selecting a component lists its actions as one list of
  full-width rows instead of buttons of different widths. The component's own actions,
  such as View, Start or Execute, come first, followed by Show Logs and Customize. Its
  type, layer and file are shown as labelled rows under the description.
- **CLI**: `odf run` prints a project set-up error as one line instead of a traceback:
  a check in `opendataframework` or `odf` that rejects the project, such as
  `@Repository` on a class with no `@Entity`, an `async def` lifecycle method, a
  dependency declared twice, an `McpTool` without a typed handler or an unknown theme.
  When the error comes from a decorator, the line ends with the file and line of the
  decorated class. An error raised by the project's own code keeps its traceback, and a
  project that fails to start is stopped before `odf run` exits. Set-up errors that
  were reported as `Invalid value` now read `Error`. See [CLI](cli.md#odf-run).
- **Keys** (breaking): components are addressed by their `opendataframework` key,
  `<namespace>.<name>` (`task.load-job`, `service.postgres`), everywhere `odf` names
  one, so same-named classes in different namespaces no longer collide. A topology
  node's `id` is its key, with `name` and `href` alongside. The UI's HTTP API serves
  each execution type as its own collection by registered name, such as
  `POST /api/tasks/load-job/execute` and `GET /api/agents/librarian/parameters`,
  instead of everything under `/api/components/{id}`, and an action that doesn't
  apply to a kind answers `404`. The MCP tools `start_component`, `stop_component`,
  `execute_task`, `component_logs` and `query_repository` take a `key` argument
  instead of `name` or `repo_id`, and a component's own tools are prefixed by its key
  (`component.stock-room.low_stock`). Chat addresses a component as
  `@<namespace>.<name>`. Saved positions, icons and colors in `layout.json` were keyed
  by the old ids, so the topology resets them once after upgrading. See
  [UI](ui.md), [MCP Server](mcp.md) and [Chat](chat.md).
- **Templates**: config sections are named after each class's key, following
  `opendataframework` 0.3.0: `odf init` writes `[component.sqlite]` instead of `[sqlite]`,
  and the `data-analytics` task reads `[task.summarize-items]`. The scaffolded `SQLite`
  storage is registered as `@Component(name="sqlite")`, so its key is
  `component.sqlite` rather than `component.s-q-lite`. The examples follow the same
  layout. A project scaffolded by an earlier version keeps working as it is. See
  [Templates](init-templates/default.md).

## 0.2.0

### Added

- **UI**: selectable themes. `odf run --theme` or `[ui] theme` in `config.toml` picks one
  of `default`, `glitch`, `neo` or `emerald`; `Server.start(theme=)` does the same. An unknown theme
  is reported as a CLI parameter error. See [CLI](cli.md) and [Server](server.md).
- **UI**: collapsible left sidebar with an icon tab rail. The collapsed state and the
  active tab persist per browser.
- **UI**: `[ui.topology]` config controls what the topology shows. `connections = false`
  hides the links between components, `config = false` hides the `Config` node, and
  `repositories`/`services`/`tasks`/`pipelines`/`components` lists restrict which
  components of that kind are shown (a kind without a list shows all of its components).
  Links of hidden components are bridged so the remaining graph keeps its shape, and the
  layout is recomputed on the visible set. An unknown key or a value of the wrong type
  raises `ValueError`; a listed name that matches no component emits a warning. A saved
  node position that collides with another node moves the other node to the nearest free
  row in its column. See [Server](server.md).
- **MCP**: `query_repository` tool for paged/filtered access to a repository's data,
  using the same query pattern as the UI's data table.
- **MCP**: components that expose `mcp_tools()` (new in `opendataframework` 0.2.0) get
  their tools registered as `<kebab(ClassName)>.<tool-name>`, alongside the built-in
  tools. A duplicate tool name within one component raises at construction.
- **Chat**: `@component-id` addressing scopes a turn's tools to that component: its own
  `mcp_tools()`, `query_repository` for a `Repository`, and the lifecycle tools. An
  unrecognized handle falls back to the full tool set, and a message that mentions more
  than one component returns an inline error. The chat input offers `@` autocomplete. See
  [Chat](chat.md).
- **Chat**: `[project.chat] debug` config flag (default `false`). See [Chat](chat.md).
- **Examples**: `18-custom-mcp-tool`, a component exposing a parameterized MCP tool.
  `17-custom-icon` now uses the `neo` theme. See [Examples](examples.md).

### Changed

- **Deps**: requires `opendataframework >=0.2.0,<0.3.0`. Upstream renamed
  `ReplayProtocol.replay_field` to `field` and now raises on `Namespace` name
  collisions instead of silently overwriting.
- **Chat**: `tool_call`/`tool_result` events are only shown in the chat window when
  `[project.chat] debug = true`. They were previously always shown. Tool execution is
  unaffected.

### Fixed

- **UI**: the Customize popover now closes when a data, details, chart or logs view is
  opened. It previously stayed on top of the view.
