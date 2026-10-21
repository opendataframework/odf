"""Training, recorded as a run: the ``train`` function.

This is the one place the example differs from ``odf init --template ml``:
the template simulates a training step with the standard library, and this
trains a real scikit-learn classifier. Recording the run is the same code in
both, so swapping the training step is all a real project changes.
"""

import pickle  # nosec B403 — the model is pickled by its own project, see train()
import time

import numpy as np
from opendataframework import Function
from sklearn.datasets import load_digits
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.entities import Artifact, Metric, Param, Run
from app.repositories import Artifacts, Metrics, Params, Runs


def load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(X_train, X_test, y_train, y_test)`` from scikit-learn's
    bundled handwritten digits (8x8 images, flattened), split the same way
    every time."""
    X, y = load_digits(return_X_y=True)
    return train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)


@Function
def train(
    learning_rate: float,
    epochs: int,
    runs: Runs,
    params: Params,
    metrics: Metrics,
    artifacts: Artifacts,
) -> dict:
    """Train a digits classifier once and record it as a run: its params, a
    metric row per epoch, a summary, and the trained model. Returns the summary.

    Each epoch is one ``partial_fit`` pass of a logistic-regression
    ``SGDClassifier`` at a constant ``learning_rate``, measured on held-out
    digits. Training is seeded, so a run with the same params gives the same
    metrics.

    Called through the ``Context`` (the UI's **Call** form, the
    ``function.train.call`` MCP tool, or ``Sweep``), the repositories are
    injected, so the caller passes only the learning rate and epochs.

    Args:
        learning_rate: The learning rate to train with.
        epochs: How many passes over the training digits, one metric row each.
        runs: Where the run is recorded, injected by the ``Context``.
        params: Where its parameters go, injected by the ``Context``.
        metrics: Where its per-step metrics go, injected by the ``Context``.
        artifacts: Where its summary and model go, injected by the ``Context``.
    """
    run = Run(id=None, name=f"lr={learning_rate}", status="running", started_at=time.time())
    runs.save(run)
    for key, value in {"learning_rate": learning_rate, "epochs": epochs}.items():
        params.save(Param(id=None, run_id=run.id, key=key, value=str(value)))

    X_train, X_test, y_train, y_test = load_data()
    scaler = StandardScaler().fit(X_train)
    X_train, X_test = scaler.transform(X_train), scaler.transform(X_test)
    classes = np.unique(y_train)
    model = SGDClassifier(
        loss="log_loss", learning_rate="constant", eta0=learning_rate, random_state=0
    )
    steps = []
    for step in range(1, epochs + 1):
        model.partial_fit(X_train, y_train, classes=classes)
        loss = round(float(log_loss(y_test, model.predict_proba(X_test), labels=classes)), 4)
        accuracy = round(float(accuracy_score(y_test, model.predict(X_test))), 4)
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
    # The scaler and the classifier together, so the exported model takes raw
    # 8x8 digits. Pickled: load it only from a project you trust, since
    # unpickling runs code.
    pipeline = make_pipeline(scaler, model)
    artifacts.save(
        Artifact(id=None, run_id=run.id, name="model.pkl", content=pickle.dumps(pipeline))
    )

    run.status = "finished"
    run.finished_at = time.time()
    runs.save(run)
    return summary
