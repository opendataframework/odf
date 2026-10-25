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
| 4 | [`04-data-engineering`](https://github.com/opendataframework/odf/tree/main/examples/04-data-engineering) | The `data-engineering` template layout: `SeedReadings` + `ExportReadingsSummary` `@Task`s composed by a `Pipeline` into a raw-to-processed ETL flow. Its `[ui.topology]` config hides the `Config` and `SQLite` nodes. | Task, Pipeline, [Topology view config](ui.md#choosing-what-the-topology-shows) |
| 5 | [`05-research`](https://github.com/opendataframework/odf/tree/main/examples/05-research) | The `research` template layout: a single `RunExperiment` `@Task` loading `data/` into a repository and writing `results/summary.json`, alongside a `doc/notes.md` lab-notebook stub. | Task |
| 6 | [`06-location-view`](https://github.com/opendataframework/odf/tree/main/examples/06-location-view) | A repository implementing `data_view() -> LocationView` so the UI renders a map instead of a table. | View |
| 7 | [`07-streaming-video-view`](https://github.com/opendataframework/odf/tree/main/examples/07-streaming-video-view) | A stream-only `Webcam` repository (`data_view() -> StreamingVideoView`) rendered as a live video player with a Start/Stop toggle. | View |
| 8 | [`08-video-view`](https://github.com/opendataframework/odf/tree/main/examples/08-video-view) | A `SecurityClips` repository (`data_view() -> VideoView`) rendered as a grid of video cards, each previewing a frame of its clip and opening it in a player. | View |
| 9 | [`09-streaming-audio-view`](https://github.com/opendataframework/odf/tree/main/examples/09-streaming-audio-view) | A stream-only `DispatchRadio` repository (`data_view() -> StreamingAudioView`) rendered as a live audio player. | View |
| 10 | [`10-audio-view`](https://github.com/opendataframework/odf/tree/main/examples/10-audio-view) | A `VoiceMemos` repository (`data_view() -> AudioView`) rendered as a grid of audio cards, each showing its clip's waveform and opening it in a player. | View |
| 11 | [`11-image-view`](https://github.com/opendataframework/odf/tree/main/examples/11-image-view) | A `DeliveryPhotos` repository (`data_view() -> ImageView`) rendered as a grid of thumbnails that open full size, where labelled boxes can be drawn on them. | View |
| 12 | [`12-document-view`](https://github.com/opendataframework/odf/tree/main/examples/12-document-view) | An `OrderReceipts` repository (`data_view() -> DocumentView`) rendered as cards that open each record's document: a JSON tree, text, or a PDF. File receipts are named and typed by `content_metadata()`. | View |
| 13 | [`13-timeseries-view`](https://github.com/opendataframework/odf/tree/main/examples/13-timeseries-view) | An `Orders` repository (`data_view() -> TimeseriesView`) rendered as a line chart, one point per record, where time ranges and points can be labelled. | View |
| 14 | [`14-chart`](https://github.com/opendataframework/odf/tree/main/examples/14-chart) | A `SalesByStore` component implementing `chart() -> str`, a matplotlib-backed self-contained HTML chart the UI renders behind a **View Chart** button. | Component |
| 15 | [`15-chart-plotly`](https://github.com/opendataframework/odf/tree/main/examples/15-chart-plotly) | The same `ChartProtocol` contract as `14-chart`, backed by Plotly instead of matplotlib for real hover tooltips. | Component |
| 16 | [`16-mcp-chat`](https://github.com/opendataframework/odf/tree/main/examples/16-mcp-chat) | `odf.server.Server.start(ui=True, mcp=True, chat=True)` — the same resolved `Context` exposed as MCP tools and driven by a local Ollama chat window. | [Chat](chat.md) |
| 17 | [`17-custom-icon`](https://github.com/opendataframework/odf/tree/main/examples/17-custom-icon) | A `config.toml`-registered `.js` file (`[ui] icon-scripts`) and `[ui.colors]` entries adding a "Lighthouse" icon and named color swatches to the topology UI's pickers — pre-applied to the `Beacons` node via a committed `layout.json` — plus a custom favicon, header logo, and brand name (`[ui] favicon` / `[ui] logo` / `[ui] brand`). | [UI](ui.md#themes-icons-and-branding) |
| 18 | [`18-custom-mcp-tool`](https://github.com/opendataframework/odf/tree/main/examples/18-custom-mcp-tool) | A `StockRoom` component whose `mcp_tools()` adds a typed `stock-room.low_stock` tool next to the fixed MCP tools. | [MCP Server](mcp.md) |
| 19 | [`19-agent`](https://github.com/opendataframework/odf/tree/main/examples/19-agent) | A `Librarian` `@Agent` whose `invoke(question, limit=3)` takes arguments: called through `context.call()`, invoked from a form in the UI, and exposed as its own typed `agent.librarian.invoke` MCP tool. | [MCP Server](mcp.md), [Chat](chat.md) |
| 20 | [`20-function`](https://github.com/opendataframework/odf/tree/main/examples/20-function) | Adopting plain functions with `@Function`: `to_eur` and `store_total` keep their signatures and still work when called directly, while `context.call()` injects their `Rates`/`Orders` dependencies and another function through `Annotated`. Each one gets a **Call** action in the UI and its own typed `<key>.call` MCP tool. | [MCP Server](mcp.md), [Chat](chat.md) |
| 21 | [`21-notebook-view`](https://github.com/opendataframework/odf/tree/main/examples/21-notebook-view) | A `Notebooks` repository over the `.ipynb` files in `notebooks/`, with a `DocumentView`: each notebook opens as its cells and outputs, and **Edit in Jupyter** edits it in place, saving through `save()` back to its file. | [UI](ui.md#notebooks) |
| 22 | [`22-ml`](https://github.com/opendataframework/odf/tree/main/examples/22-ml) | The `ml` template layout, training a real scikit-learn classifier: `Runs`, `Params`, `Metrics` and `Artifacts` repositories, recorded by a `train` `@Function` and a `Sweep` `@Task`. `Metrics` uses a grouped `TimeseriesView`, one line per run, `export_run` writes a run with its `model.pkl` to `exports/`, and a Plotly `RunComparison` page compares the runs. | [UI](ui.md#grouped-timeseries), [`ml` template](init-templates/ml.md) |
| 23 | [`23-reverse-proxy`](https://github.com/opendataframework/odf/tree/main/examples/23-reverse-proxy) | Deploying behind a reverse proxy with `docker compose up`: `odf run` in a container reachable only from Traefik, which adds HTTPS, a Basic auth login (or an identity provider through oauth2-proxy) and the MCP server at `/mcp`. **Edit in Jupyter** works through it unchanged. | [UI](ui.md#deploying) |
| 24 | [`24-custom-theme`](https://github.com/opendataframework/odf/tree/main/examples/24-custom-theme) | A project serving its own UI theme from `./pixel-theme/` (`[ui] theme` as a path): a pixel-art theme with PICO-8 and Game Boy palettes and pixel fonts, whose `theme.js` sets `pixelSize: 2` so the topology canvas is drawn in hard pixels, plus two more selected with `--theme`: a late-90s theme-park theme in `./park-theme/` (beveled windows, grass tiles) and a 1980s neon-coast theme in `./neon-theme/` (pink and cyan neon, a sunset stripe), which keeps the canvas at full resolution so its icons glow, and seven more: `./terminal-theme/`, `./y2k-theme/`, `./meadow-theme/`, `./beacon-theme/`, `./ledger-theme/`, `./clay-theme/` and `./workbench-theme/`. | [UI](ui.md#custom-themes) |

Examples 2–5 and 22 mirror `odf init --template <name>`'s scaffolded layouts —
each is runnable both as a plain script (`python main.py`) and via
`odf run` (see each example's own `README.md` for specifics). Most "Docs"
entries above refer to concept pages on the
[`opendataframework` docs site](https://opendataframework.github.io/opendataframework/) —
`Entity`, `Repository`, `Task`, `Pipeline`, `Layer`, `View`, and
`Component` are all core abstractions documented there, not here. The UI,
MCP server and chat each have their own page here: [UI](ui.md),
[MCP Server](mcp.md), [Chat](chat.md).

## Running an example

Clone the repository, install `odf` with the UI (`pip install "odf[ui]"`; some
examples need more, such as `opencv-python` or `matplotlib`, listed in their own
`README.md`), then run from inside the example's own directory:

<!-- termynal -->

```
$ cd examples/01-table-view
$ odf run
UI running at http://127.0.0.1:4747
```

Open the UI and look at `Books` — it renders as a plain table with no
extra step needed. Examples 2–5 and 22 can also run as a plain script instead of
the UI (`python main.py`) — see each example's own `README.md` for
specifics.
