# 22 — ML

The project shape `odf init --template ml` scaffolds: training runs and what
each one records, kept in four repositories with a fixed structure. Since
they are ordinary repositories, the UI shows them, the MCP tools query them
and chat answers questions about them, with no extra code. Each run here
trains a real scikit-learn classifier on handwritten digits.

- **`Runs`**: one record per run (name, status, start and finish time),
  shown as the implicit table, the list of runs.
- **`Params`**: the parameters each run was trained with, one row per
  parameter.
- **`Metrics`**: one row per training step, with each metric as a column.
  `data_view()` returns
  `TimeseriesView(field="step", fields=("loss", "accuracy"), group="run_id")`,
  so the chart plots loss and accuracy by step with one line per run. Every
  run shares each metric's y axis, so the runs compare on one chart.
- **`Artifacts`**: what each run produced, through `DocumentView`:
  - a JSON summary of its params and final and best metrics, opened as a
    tree;
  - the trained model, `model.pkl`, which `content_metadata()` names so the
    view's **Download** saves it under that name.

The work itself:

- **`train`** (`app/training.py`) is a `@Function` taking
  `learning_rate` and `epochs`. It trains a logistic-regression
  `SGDClassifier` on scikit-learn's bundled digits, one `partial_fit` pass per
  epoch, and measures loss and accuracy on held-out digits after each. It
  records the run with its params, a metric row per epoch, the summary, and
  the scaler and classifier together as `model.pkl`, which takes raw 8×8
  digits. Training is seeded, so the same params give the same metrics.
  The repositories are injected, so the UI's **Call** form and the
  `function.train.call` MCP tool ask only for the learning rate and epochs
  (see [`20-function`](../20-function)).
- **`Sweep`** (`app/tasks.py`) is a `@Task` training once per learning rate
  in `[task.sweep]`. It asks for `train` through `Annotated`, already bound
  to its repositories. A task takes no arguments when it runs, so the grid
  lives in `config.toml`.
- **`export_run`** (`app/exports.py`) is a `@Function` taking a `run_id`. It
  writes the run to `exports/<id>-<name>/`:
  - `params.json`;
  - `metrics.csv`;
  - every artifact the run saved: `summary.json`, and `model.pkl`.

  It doesn't know about models: whatever `train` saves as an artifact is
  exported, so the folder holds what's needed to reproduce or deploy the
  run elsewhere.
- **`RunComparison`** (`app/charts.py`) is a `ChartProtocol` component
  built with Plotly. One page holds:
  - final loss and final accuracy against learning rate (log scale);
  - every run's loss curve by step, with the best run drawn thicker;
  - a table of the runs ranked by final loss, with their params, best step
    and duration.

  Hovering shows a run's params and values, and clicking a run in the legend
  hides it in every panel. Each run keeps the color the `Metrics` chart
  gives it, and the page follows the UI's theme, light or dark. It's a chart
  derived from several repositories, rather than a view of one, so it is a
  component (see [`14-chart`](../14-chart) and
  [`15-chart-plotly`](../15-chart-plotly)).

The example differs from its template in two places:

- **The training step.** The template simulates one with the standard
  library. Swapping it for a real model is all a real project changes:
  recording the run, the views and the export stay the same.
- **`RunComparison`.** The template's is a plain SVG scatter; this one is the
  fuller version.

With the template, an export has everything except `model.pkl`, until
`train` saves a model as an artifact.

## Structure

```
22-ml/
├── config.toml          # SQLite path, and the sweep's learning rates and epochs
├── main.py              # entry point: records a sweep, trains once over MCP, exports the best run
└── app/
    ├── __init__.py      # imports all modules so decorators register at startup
    ├── entities.py      # Run, Param, Metric, Artifact — @Entity
    ├── storages.py      # SQLite — @Storage @Component, one table per entity
    ├── repositories.py  # Runs, Params, Metrics (grouped timeseries), Artifacts (documents, downloads)
    ├── training.py      # train — @Function, trains a digits classifier and records the run
    ├── tasks.py         # Sweep — @Task, one run per learning rate
    ├── exports.py       # export_run — @Function, writes a run to exports/
    └── charts.py        # RunComparison — @Analytics @Component, Plotly comparison page
```

## Dependencies

- **`scikit-learn` and `plotly`:** from the `examples` extra
  (`pip install "odf[examples]"`).
- **`mcp`:** the `mcp` extra (`pip install "odf[mcp]"`), for the MCP server
  and its client.
- **`ui`:** the `ui` extra, for the UI.

All of them are in the repo's `dev` dependency group, so a plain
`poetry install` covers them. The template itself needs only the standard
library.

## Run it

```bash
cd examples/22-ml
python main.py
```

Expected output, on a fresh `app.db`:

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp

context.execute("task.sweep") recorded lr=0.001: {'loss': 1.1331, 'accuracy': 0.9356}
context.execute("task.sweep") recorded lr=0.01: {'loss': 0.383, 'accuracy': 0.9489}
context.execute("task.sweep") recorded lr=0.1: {'loss': 0.2918, 'accuracy': 0.9467}
context.execute("task.sweep") recorded lr=1.0: {'loss': 1.1317, 'accuracy': 0.92}

Driving the project over MCP, the same way an MCP client would:
function.train.call recorded lr=0.05: {'loss': 0.2892, 'accuracy': 0.9578}

Best run, by final loss: lr=0.05 {'loss': 0.2892, 'accuracy': 0.9578}
function.export-run.call exported it to exports/5-lr-0.05
```

The sweep's U shape is real: too low a learning rate hasn't converged in five
epochs, and too high a one overshoots. The run tried over MCP, between the
sweep's two best, beats them all.

Runs persist in `app.db`, so a second run skips the training, then finds and
exports the best run again. Delete `app.db` to start over.

The exported model loads anywhere scikit-learn is installed:

```python
import pickle

from sklearn.datasets import load_digits

with open("exports/5-lr-0.05/model.pkl", "rb") as f:
    model = pickle.load(f)
print(model.predict(load_digits().data[:5]))  # [0 1 2 3 4]
```

`model.pkl` is a pickle, and loading a pickle runs code from it. Load only
models your own project saved, never one you were sent.

## Look at the runs

Start it with the CLI:

```bash
odf run --mcp --chat
```

- **Runs** and **Params** → **View** open as tables.
- **Metrics** → **View** shows loss and accuracy by step, one color per run
  and one dash style per metric. Click a run or a metric in the legend to hide
  or show it.
- **Artifacts** → **View** opens each run's summary as a document. Its
  `model.pkl` opens as a file to **Download**.
- **RunComparison** → **View Chart** shows the comparison page.
- **Sweep** → **Execute** records another sweep. **train** → **Call** trains
  one run with the learning rate and epochs you enter. **export_run** →
  **Call** exports the run you name.
- In chat, ask "which run had the lowest loss?". The model answers by
  querying `Artifacts` or `Metrics` with `query_repository`.

The timeseries chart shows one page of records at a time. Rows come sorted by
run, then step, so a page holds whole runs where it can. The sweep and the
run over MCP make 25 rows, the default page. With more runs, raise the page
size, or keep fewer runs in `app.db`.
