# `ml` template

```bash
odf init my-project --template ml
```

[`default`](default.md)'s `SQLite` storage, with `Item`/`Items` replaced by
four entities that structure training: a `Run`, the `Param`s it was trained
with, a `Metric` row per training step, and the `Artifact`s it produced. A
`train` function records one run, a `Sweep` task records one run per
learning rate, and a `RunComparison` chart compares them. Since runs and
what they record are ordinary repositories, the UI shows them, the MCP
tools query them and chat answers questions about them, with no extra code.

## Choosing between `data-science` and `ml`

Both are for data work. They differ in what the project is about:

- **[`data-science`](data-science.md)** is for exploring data: source data
  in `data/raw/`, derived data in `data/processed/`, and a notebook to work
  through it. The records are the data itself, and the question is "what's
  in this data?".
- **`ml`** is for training and comparing models: runs, their parameters,
  per-step metrics and per-run artifacts, a sweep and a comparison chart.
  The records are runs and what they measured, and the question is "which
  run did best, and why?".

Pick `ml` when you'll train something more than once and compare the
results, and `data-science` when you're still finding out what the data
holds. An `ml` project can still add `data/` folders and notebooks.

## Layout

```text
my-project/
├── config.toml           # SQLite path, plus [task.sweep] learning-rates and epochs
└── app/
    ├── __init__.py
    ├── entities.py       # Run, Param, Metric, Artifact
    ├── storages.py       # SQLite, one table per entity
    ├── repositories.py   # Runs, Params, Metrics, Artifacts
    ├── training.py       # train (@Function)
    ├── tasks.py          # Sweep (@Task)
    └── charts.py         # RunComparison (@Analytics @Component)
```

## What's added

| Name | What it is | In the UI |
|---|---|---|
| `Runs` | One record per run: name, status, start and finish time | A table, the list of runs |
| `Params` | One row per parameter of a run, its value stored as text | A table |
| `Metrics` | One row per training step, with each metric (`loss`, `accuracy`) as a column | A chart of each metric by step, one line per run |
| `Artifacts` | What a run produced, here a JSON summary of its params and results | A document per artifact |
| `train` | A `@Function` taking `learning_rate` and `epochs`, recording one run | A **Call** form, and the `function.train.call` MCP tool |
| `Sweep` | A `@Task` training once per learning rate in `[task.sweep]` | **Execute** |
| `RunComparison` | A chart of each run's final loss against its learning rate | **View Chart** |

`Metrics` charts its rows with a grouped timeseries view:

```python
def data_view(self) -> TimeseriesView:
    return TimeseriesView(field="step", fields=("loss", "accuracy"), group="run_id")
```

Each run gets its own line, and every run shares each metric's y axis, so
the runs compare on one chart (see [UI](../ui.md#grouped-timeseries)). A
metric is a column, so tracking another one, such as a validation loss, is
a new field on `Metric` and a new column in `storages.py`.

The training step in `training.py` is simulated: deterministic, and best
near a learning rate of `0.1`. Replace `simulate_step()` with your model's
training step. The rest of `train`, recording the run, stays as it is.

`Sweep` takes no arguments when it runs, like every task, so the grid is
in `config.toml`:

```toml
[task.sweep]
learning-rates = [0.01, 0.1, 0.5]
epochs = 6
```

A one-off run with other values is a call to `train`, from its **Call**
form, over MCP or from chat.

The template needs only the standard library: `RunComparison` draws plain
SVG.

## Run it

<!-- termynal -->

```
$ odf run --mcp
```

Execute `Sweep`, then open `Metrics` and `RunComparison` to compare the runs.
In chat (`odf run --mcp --chat`), "which run had the lowest loss?" is
answered from the repositories. The
[`22-ml`](https://github.com/opendataframework/odf/tree/main/examples/22-ml)
example is this layout, with a `main.py` that records a sweep and trains
once over MCP.
