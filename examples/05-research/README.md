# 05 — Research

The project shape `odf init --template research` scaffolds: `data/` holds
raw, read-only source data, `results/` holds everything an experiment
generates, and `doc/notes.md` is a lab-notebook stub (hypothesis, method,
results, notes) — the `data`/`results` split from ["Good Enough Practices in
Scientific Computing"](https://doi.org/10.1371/journal.pcbi.1005510)
(Wilson et al., 2017): raw input and generated output never share a
directory.

`RunExperiment` (`app/experiments.py`) is a single `@Task` that both loads
`data/readings.csv` into the `Readings` repository (idempotently — skipped
if already loaded) and computes summary statistics from it, writing
`results/summary.json`. That's the one deliberate difference from
[`04-data-engineering`](../04-data-engineering/), which splits the same two
steps into `SeedItems`/`ExportItemsSummary` plus a `Pipeline`: a real
experiment script is usually rerun as a single step while its method is
still being iterated on, not staged across a multi-task pipeline.

## Structure

```
05-research/
├── config.toml            # SQLite path
├── main.py                 # entry point — runs RunExperiment
├── app/
│   ├── __init__.py         # imports all modules so decorators register at startup
│   ├── entities.py         # Reading — @Entity @dataclass
│   ├── storages.py          # SQLite — @Storage @Component
│   ├── repositories.py     # Readings — @Storage @Repository(Reading)
│   └── experiments.py      # RunExperiment — @Task, load + compute in one step
├── data/
│   └── readings.csv        # source data, never edited in place
├── results/                # written by RunExperiment, not checked in
└── doc/
    └── notes.md            # hypothesis / method / results / notes stub
```

## Run it

```bash
cd examples/05-research
python main.py
```

```
Experiment result: {'reading_count': 5, 'average_celsius_by_sensor': {'kitchen': 21.5, 'garage': 16.88}}
```

Run it again and `RunExperiment` skips re-loading `data/readings.csv` —
`app.db` already has the rows — but still recomputes and rewrites
`results/summary.json` from whatever `Readings` currently holds.

Or start the dev UI and run `RunExperiment` from there (or via the MCP
`execute_task` tool with `--mcp`):

```bash
odf run
```
