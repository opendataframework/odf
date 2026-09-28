# Release Notes

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
