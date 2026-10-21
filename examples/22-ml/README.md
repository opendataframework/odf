# 22 — ML

The project shape `odf init --template ml` scaffolds: training runs and what
each one records, kept in four repositories with a fixed structure. Since
they are ordinary repositories, the UI shows them, the MCP tools query them
and chat answers questions about them, with no extra code.

- **`Runs`**: one record per run (name, status, start and finish time),
  shown as the implicit table, the list of runs.
- **`Params`**: the parameters each run was trained with, one row per
  parameter.
- **`Metrics`**: one row per training step, with each metric as a column.
  `data_view()` returns
  `TimeseriesView(field="step", fields=("loss", "accuracy"), group="run_id")`,
  so the chart plots loss and accuracy by step with one line per run. Every
  run shares each metric's y axis, so the runs compare on one chart.
- **`Artifacts`**: what each run produced, here a JSON summary of its
  params and final and best metrics, opened as a document through
  `DocumentView`.

The work itself:

- **`train`** (`app/training.py`) is a `@Function` taking
  `learning_rate` and `epochs`. It records one run with its params, a metric
  row per epoch and a summary artifact. The repositories are injected, so the
  UI's **Call** form and the `function.train.call` MCP tool ask only for the
  learning rate and epochs (see [`20-function`](../20-function)). Its training
  step is simulated, deterministic, and settles lowest near a learning rate
  of `0.1`. A real project replaces `simulate_step()` with its model.
- **`Sweep`** (`app/tasks.py`) is a `@Task` training once per learning rate
  in `[task.sweep]`. It asks for `train` through `Annotated`, already bound
  to its repositories. A task takes no arguments when it runs, so the grid
  lives in `config.toml`.
- **`RunComparison`** (`app/charts.py`) is a `ChartProtocol` component
  plotting each run's final loss against its learning rate, one point per
  run, with the best one highlighted. That is a chart derived from several
  repositories, rather than a view of one, so it is a component (see
  [`14-chart`](../14-chart)). It draws plain SVG and needs no charting
  library.

## Structure

```
22-ml/
├── config.toml          # SQLite path, and the sweep's learning rates and epochs
├── main.py              # entry point: records a sweep, trains once over MCP, finds the best run
└── app/
    ├── __init__.py      # imports all modules so decorators register at startup
    ├── entities.py      # Run, Param, Metric, Artifact — @Entity
    ├── storages.py      # SQLite — @Storage @Component, one table per entity
    ├── repositories.py  # Runs, Params, Metrics (grouped timeseries), Artifacts (documents)
    ├── training.py      # train — @Function, records one run
    ├── tasks.py         # Sweep — @Task, one run per learning rate
    └── charts.py        # RunComparison — @Analytics @Component, final loss by learning rate
```

## Dependencies

Needs the `mcp` extra (`pip install "odf[mcp]"`) for the MCP server and its
client, and `ui` for the UI. Both are in the repo's `dev` dependency group, so
a plain `poetry install` covers them. The template itself needs only the
standard library.

## Run it

```bash
cd examples/22-ml
python main.py
```

Expected output, on a fresh `app.db`:

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp

context.execute("task.sweep") recorded lr=0.01: {'loss': 0.8473, 'accuracy': 0.1527}
context.execute("task.sweep") recorded lr=0.1: {'loss': 0.2237, 'accuracy': 0.7763}
context.execute("task.sweep") recorded lr=0.5: {'loss': 0.3855, 'accuracy': 0.6145}

Driving the project over MCP, the same way an MCP client would:
function.train.call recorded lr=0.05: {'loss': 0.4419, 'accuracy': 0.5581}

Best run, by final loss: lr=0.1 {'loss': 0.2237, 'accuracy': 0.7763}
```

Runs persist in `app.db`, so a second run skips the sweep and only finds the
best run. Delete `app.db` to start over.

## Look at the runs

Start it with the CLI:

```bash
odf run --mcp --chat
```

- **Runs** and **Params** → **View** open as tables.
- **Metrics** → **View** shows loss and accuracy by step, one color per run
  and one dash style per metric. Click a run or a metric in the legend to hide
  or show it.
- **Artifacts** → **View** opens each run's summary as a document.
- **RunComparison** → **View Chart** shows final loss by learning rate.
- **Sweep** → **Execute** records another sweep, and **train** → **Call**
  trains one run with the learning rate and epochs you enter.
- In chat, ask "which run had the lowest loss?". The model answers by
  querying `Artifacts` or `Metrics` with `query_repository`.

The timeseries chart shows one page of records at a time. Rows come sorted by
run, then step, so a page holds whole runs where it can. With many runs or
long runs, raise the page size, or keep fewer runs in `app.db`.
