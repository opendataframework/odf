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
    and ``bytes`` (such as a trained model) as ``<name>``.
    """
    run = runs.get(run_id)
    if run is None:
        raise ValueError(f"no run with id {run_id}")
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
