"""Exporting a run: the ``export_run`` function."""

import csv
import json
import re
from pathlib import Path

from opendataframework import Function

from app.repositories import Artifacts, Metrics, Params, Runs


@Function
def export_run(
    run_id: int,
    runs: Runs,
    params: Params,
    metrics: Metrics,
    artifacts: Artifacts,
) -> str:
    """Write one run's params, metrics and artifacts to ``exports/``, to
    reproduce or deploy it elsewhere. Returns the folder written.

    Every artifact the run saved is written: a ``dict`` as ``<name>.json``
    and ``bytes`` as ``<name>``, so ``model.pkl`` lands next to the run's
    params. It doesn't know about models: whatever ``train`` saves as an
    artifact is exported.

    Args:
        run_id: The ``id`` of the run to export.
        runs: Where the run is read from, injected by the ``Context``.
        params: Where its parameters are read from, injected by the ``Context``.
        metrics: Where its per-step metrics are read from, injected by the ``Context``.
        artifacts: Where its artifacts are read from, injected by the ``Context``.

    Raises:
        ValueError: If no run has ``run_id``.
    """
    run = runs.get(run_id)
    if run is None:
        raise ValueError(f"no run with id {run_id}")
    # The run's id keeps folders apart; its name, made safe for any file
    # system, says what's inside.
    folder = Path("exports") / f"{run.id}-{re.sub(r'[^A-Za-z0-9.]+', '-', run.name).strip('-')}"
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "params.json").write_text(json.dumps(params.for_run(run_id), indent=2))
    with open(folder / "metrics.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["step", "loss", "accuracy"])
        for metric in metrics.for_run(run_id):
            writer.writerow([metric.step, metric.loss, metric.accuracy])

    for artifact in artifacts.for_run(run_id):
        if isinstance(artifact.content, bytes):
            (folder / artifact.name).write_bytes(artifact.content)
        else:
            (folder / f"{artifact.name}.json").write_text(json.dumps(artifact.content, indent=2))
    return str(folder)
