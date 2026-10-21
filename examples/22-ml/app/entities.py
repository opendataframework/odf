"""Entities for the ml example: a run and what it records."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Run:
    """One training run.

    Attributes:
        id: Primary key, ``None`` until ``Runs.save()`` assigns one.
        name: A readable name, such as ``"lr=0.1"``.
        status: ``"running"`` while it trains, then ``"finished"``.
        started_at: ``time.time()`` when it started.
        finished_at: ``time.time()`` when it finished, ``None`` until then.
    """

    id: int | None
    name: str
    status: str
    started_at: float
    finished_at: float | None = None


@Entity
@dataclass
class Param:
    """One parameter a run was trained with.

    Attributes:
        id: Primary key, ``None`` until ``Params.save()`` assigns one.
        run_id: The run it belongs to.
        key: The parameter's name, such as ``"learning_rate"``.
        value: Its value, as text, so every parameter fits one column.
    """

    id: int | None
    run_id: int
    key: str
    value: str


@Entity
@dataclass
class Metric:
    """One training step of a run. Each metric is a column, so tracking
    another metric is a new field here and a new column in ``storages.py``.

    Attributes:
        id: Primary key, ``None`` until ``Metrics.save()`` assigns one.
        run_id: The run it belongs to, one line per run in the chart.
        step: The training step, the chart's x axis.
        loss: The loss after this step.
        accuracy: The accuracy after this step.
    """

    id: int | None
    run_id: int
    step: int
    loss: float
    accuracy: float


@Entity
@dataclass
class Artifact:
    """Something a run produced, here a JSON-shaped summary.

    Attributes:
        id: Primary key, ``None`` until ``Artifacts.save()`` assigns one.
        run_id: The run that produced it.
        name: What it is, such as ``"summary"``.
        content: The artifact itself, shown as a document.
    """

    id: int | None
    run_id: int
    name: str
    content: dict
