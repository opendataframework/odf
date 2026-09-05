# Examples

Small, focused `odf` projects demonstrating the CLI/MCP/UI-server surface
that sits on top of
[`opendataframework`](https://opendataframework.github.io/opendataframework/).
These depend on `opendataframework` as a real package dependency, so this
directory doubles as an integration check that the split works for
external consumers.

| # | Example | Concept(s) | Docs |
|---|---|---|---|
| 1 | [`01-table-view`](https://github.com/opendataframework/odf/tree/main/examples/01-table-view) | A repository implementing no `data_view()` at all, so the UI falls back to the implicit default plain table. | View |
| 2 | [`02-data-analytics`](https://github.com/opendataframework/odf/tree/main/examples/02-data-analytics) | The `data-analytics` template layout: a `SummarizeReadings` `@Analytics @Task` writing a JSON report to `reports/`. | Task, Layer |
| 3 | [`03-data-science`](https://github.com/opendataframework/odf/tree/main/examples/03-data-science) | The `data-science` template layout: `data/raw/` ingested via `Project`, then explored from `notebooks/` through a `Repository` built standalone, outside the `Context`. | Repository |
| 4 | [`04-data-engineering`](https://github.com/opendataframework/odf/tree/main/examples/04-data-engineering) | The `data-engineering` template layout: `SeedReadings` + `ExportReadingsSummary` `@Task`s composed by a `Pipeline` into a raw-to-processed ETL flow. | Task, Pipeline |
| 5 | [`05-research`](https://github.com/opendataframework/odf/tree/main/examples/05-research) | The `research` template layout: a single `RunExperiment` `@Task` loading `data/` into a repository and writing `results/summary.json`, alongside a `doc/notes.md` lab-notebook stub. | Task |
| 6 | [`06-location-view`](https://github.com/opendataframework/odf/tree/main/examples/06-location-view) | A repository implementing `data_view() -> LocationView` so the UI renders a map instead of a table. | View |
| 7 | [`07-streaming-video-view`](https://github.com/opendataframework/odf/tree/main/examples/07-streaming-video-view) | A stream-only `Webcam` repository (`data_view() -> StreamingVideoView`) rendered as a live video player with a Start/Stop toggle. | View |
| 8 | [`08-video-view`](https://github.com/opendataframework/odf/tree/main/examples/08-video-view) | A `SecurityClips` repository (`data_view() -> VideoView`) rendered as a list of seekable video clips, one per record. | View |
| 9 | [`09-streaming-audio-view`](https://github.com/opendataframework/odf/tree/main/examples/09-streaming-audio-view) | A stream-only `DispatchRadio` repository (`data_view() -> StreamingAudioView`) rendered as a live audio player. | View |
| 10 | [`10-audio-view`](https://github.com/opendataframework/odf/tree/main/examples/10-audio-view) | A `VoiceMemos` repository (`data_view() -> AudioView`) rendered as a list of seekable audio clips. | View |
| 11 | [`11-image-view`](https://github.com/opendataframework/odf/tree/main/examples/11-image-view) | A `DeliveryPhotos` repository (`data_view() -> ImageView`) rendered as a grid of thumbnails. | View |
| 12 | [`12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view) | An `OrderReceipts` repository (`data_view() -> DocumentView`) rendered as a collapsible, Postman-style JSON tree per record. | View |
| 13 | [`13-timeseries-view`](https://github.com/opendataframework/odf/tree/main/examples/13-timeseries-view) | An `Orders` repository (`data_view() -> TimeseriesView`) rendered as a line chart, one point per record. | View |
| 14 | [`14-chart`](https://github.com/opendataframework/odf/tree/main/examples/14-chart) | A `SalesByStore` component implementing `chart() -> str`, a matplotlib-backed self-contained HTML chart the UI renders behind a **View Chart** button. | Component |
| 15 | [`15-chart-plotly`](https://github.com/opendataframework/odf/tree/main/examples/15-chart-plotly) | The same `ChartProtocol` contract as `14-chart`, backed by Plotly instead of matplotlib for real hover tooltips. | Component |
| 16 | [`16-mcp-chat`](https://github.com/opendataframework/odf/tree/main/examples/16-mcp-chat) | `odf.server.Server.start(ui=True, mcp=True, chat=True)` — the same resolved `Context` exposed as MCP tools and driven by a local Ollama chat window. | [Chat](chat.md) |
| 17 | [`17-custom-icon`](https://github.com/opendataframework/odf/tree/main/examples/17-custom-icon) | A `config.toml`-registered `.js` file (`[ui] icon-scripts`) and `[ui.colors]` entries adding a "Lighthouse" icon and named color swatches to the topology UI's pickers — pre-applied to the `Beacons` node via a committed `layout.json` — plus a custom favicon, header logo, and brand name (`[ui] favicon` / `[ui] logo` / `[ui] brand`). | — |

Examples 2–5 mirror `odf init --template <name>`'s scaffolded layouts —
each is runnable both as a plain script (`python main.py`) and via
`odf run` (see each example's own `README.md` for specifics). Most "Docs"
entries above refer to concept pages on the
[`opendataframework` docs site](https://opendataframework.github.io/opendataframework/) —
`Entity`, `Repository`, `Task`, `Pipeline`, `Layer`, `View`, and
`Component` are all core abstractions documented there, not here; the MCP
server and topology UI don't yet have their own dedicated pages here (see
[`cli.md`](cli.md) for the CLI flags that start them).

## Running an example

Clone the repository, then run from inside the example's own directory:

<!-- termynal -->

```
$ cd examples/01-table-view
$ odf run
UI running at http://127.0.0.1:4747
```

Open the UI and look at `Books` — it renders as a plain table with no
extra step needed. Examples 2–5 can also run as a plain script instead of
the UI (`python main.py`) — see each example's own `README.md` for
specifics.
