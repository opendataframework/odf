# Examples

Small, focused `odf` projects demonstrating the CLI/MCP/UI-server surface
that sits on top of `opendataframework`. These depend on `opendataframework`
as a real package dependency, so this directory doubles as an integration
check that the split works for external consumers.

| # | Example | Concept(s) |
|---|---|---|
| 1 | [`01-table-view/`](01-table-view/) | A repository implementing no `data_view()` at all, so the UI falls back to the implicit default plain table. |
| 2 | [`02-data-analytics/`](02-data-analytics/) | The `data-analytics` template layout: a `SummarizeReadings` `@Analytics @Task` writing a JSON report to `reports/`. |
| 3 | [`03-data-science/`](03-data-science/) | The `data-science` template layout: `data/raw/` ingested via `Project`, then explored from `notebooks/` through a `Repository` built standalone, outside the `Context`. |
| 4 | [`04-data-engineering/`](04-data-engineering/) | The `data-engineering` template layout: `SeedReadings` + `ExportReadingsSummary` `@Task`s composed by a `Pipeline` into a raw-to-processed ETL flow. |
| 5 | [`05-research/`](05-research/) | The `research` template layout: a single `RunExperiment` `@Task` loading `data/` into a repository and writing `results/summary.json`, alongside a `doc/notes.md` lab-notebook stub. |
| 6 | [`06-location-view/`](06-location-view/) | A repository implementing `data_view() -> LocationView` so the UI renders a map instead of a table. Run with `odf run` and click "View Map" on `Stores`. |
| 7 | [`07-streaming-video-view/`](07-streaming-video-view/) | A stream-only `Webcam` repository (`data_view() -> StreamingVideoView`) rendered as a live video player with a Start/Stop toggle. |
| 8 | [`08-video-view/`](08-video-view/) | A `SecurityClips` repository (`data_view() -> VideoView`) rendered as a list of seekable video clips, one per record. |
| 9 | [`09-streaming-audio-view/`](09-streaming-audio-view/) | A stream-only `DispatchRadio` repository (`data_view() -> StreamingAudioView`) rendered as a live audio player. |
| 10 | [`10-audio-view/`](10-audio-view/) | A `VoiceMemos` repository (`data_view() -> AudioView`) rendered as a list of seekable audio clips. |
| 11 | [`11-image-view/`](11-image-view/) | A `DeliveryPhotos` repository (`data_view() -> ImageView`) rendered as a grid of thumbnails. |
| 12 | [`12-document-view/`](12-document-view/) | An `OrderReceipts` repository (`data_view() -> DocumentView`) rendered as a collapsible, Postman-style JSON tree per record. |
| 13 | [`13-timeseries-view/`](13-timeseries-view/) | An `Orders` repository (`data_view() -> TimeseriesView`) rendered as a line chart, one point per record. |
| 14 | [`14-chart/`](14-chart/) | A `SalesByStore` component implementing `chart() -> str`, a matplotlib-backed self-contained HTML chart the dev UI renders behind a **View Chart** button. |
| 15 | [`15-chart-plotly/`](15-chart-plotly/) | The same `ChartProtocol` contract as `14-chart`, backed by Plotly instead of matplotlib for real hover tooltips. |
| 16 | [`16-mcp-chat/`](16-mcp-chat/) | `odf.server.Server.start(ui=True, mcp=True, chat=True)` — the same resolved `Context` exposed as MCP tools and driven by a local Ollama chat window. |
| 17 | [`17-custom-icon/`](17-custom-icon/) | A `config.toml`-registered `.js` file (`[ui] icon-scripts`) adding a custom "Lighthouse" swatch to the topology UI's icon picker, assignable to any node. |
