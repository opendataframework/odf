from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Run:
    id: int | None
    name: str
    status: str
    started_at: float
    finished_at: float | None = None


@Entity
@dataclass
class Param:
    id: int | None
    run_id: int
    key: str
    value: str


@Entity
@dataclass
class Metric:
    """One training step of a run. Each metric is a column, so add or rename
    columns here (and in ``storages.py``) to track other metrics."""

    id: int | None
    run_id: int
    step: int
    loss: float
    accuracy: float


@Entity
@dataclass
class Artifact:
    """Something a run produced: a JSON-shaped ``dict`` (a summary, a report)
    or a file's ``bytes`` (a trained model), named by ``name``."""

    id: int | None
    run_id: int
    name: str
    content: dict | bytes
