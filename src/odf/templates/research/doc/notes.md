# Research Notes

## Hypothesis

_What are you trying to find out?_

## Method

`RunExperiment` (`app/experiments.py`) loads `data/items.csv` — the raw,
read-only source data — into the `Items` repository, computes summary
statistics, and writes them to `results/summary.json`. Run it from the
UI's Execute action, or call `RunExperiment.execute()` directly.

## Results

See `results/summary.json` after running the experiment.

## Notes

_Anything else worth recording as you go._
