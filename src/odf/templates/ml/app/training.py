import math
import time

from opendataframework import Function

from app.entities import Artifact, Metric, Param, Run
from app.repositories import Artifacts, Metrics, Params, Runs


def simulate_step(learning_rate: float, step: int) -> tuple[float, float]:
    """Return a ``(loss, accuracy)`` pair for one training step.

    A stand-in for real training, deterministic so runs are reproducible: the
    loss falls faster with a higher learning rate but settles lowest near
    ``0.1``. Replace it with your model's training step.
    """
    floor = 0.05 + 2 * (learning_rate - 0.1) ** 2
    wobble = 0.01 * (1 + math.sin(step * 1.7 + learning_rate * 31))
    loss = floor + (1 - floor) * math.exp(-3 * learning_rate * step) + wobble
    return round(loss, 4), round(max(0.0, 1 - loss), 4)


@Function
def train(
    learning_rate: float,
    epochs: int,
    runs: Runs,
    params: Params,
    metrics: Metrics,
    artifacts: Artifacts,
) -> dict:
    """Train once and record it as a run: its params, a metric row per
    epoch, and a summary artifact. Returns the summary."""
    run = Run(id=None, name=f"lr={learning_rate}", status="running", started_at=time.time())
    runs.save(run)
    for key, value in {"learning_rate": learning_rate, "epochs": epochs}.items():
        params.save(Param(id=None, run_id=run.id, key=key, value=str(value)))

    steps = []
    for step in range(1, epochs + 1):
        loss, accuracy = simulate_step(learning_rate, step)
        metric = Metric(id=None, run_id=run.id, step=step, loss=loss, accuracy=accuracy)
        metrics.save(metric)
        steps.append(metric)

    best = min(steps, key=lambda m: m.loss)
    summary = {
        "run_id": run.id,
        "run": run.name,
        "params": {"learning_rate": learning_rate, "epochs": epochs},
        "final": {"loss": steps[-1].loss, "accuracy": steps[-1].accuracy},
        "best": {"step": best.step, "loss": best.loss},
    }
    artifacts.save(Artifact(id=None, run_id=run.id, name="summary", content=summary))

    run.status = "finished"
    run.finished_at = time.time()
    runs.save(run)
    return summary
