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
- **UI**: labelled boxes can be drawn on an open image in the image view. Drag to draw a
  box and type its label, or pick one already used from the list under the input; select a box to delete it,
  or select its label to change it. A box inside a larger one stays on top, so it can
  still be selected. A label no box uses any more is dropped from the list. Boxes are saved to `annotations.json`, or the file
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

### Changed

- **UI**: the Activity and Chat buttons moved from the top-right corner of the map into
  the header bar, as icon buttons next to the theme toggle. They no longer cover a
  view's own controls, such as the table view's timeline dropdown and replay controls,
  and the button of the open drawer stays highlighted.

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
