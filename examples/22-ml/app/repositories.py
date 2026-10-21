"""SQLite-backed repositories for the ml example, one per entity."""

import json

from opendataframework import DocumentView, Repository, Storage, TimeseriesView

from app.entities import Artifact, Metric, Param, Run
from app.storages import SQLite


@Storage
@Repository(Run)
class Runs:
    """Every run, shown as the implicit table: the list of runs."""

    def __init__(self, sqlite: SQLite) -> None:
        """Store the shared ``SQLite`` component to persist through.

        Args:
            sqlite: The shared connection component.
        """
        self.db = sqlite

    def all(self) -> list[Run]:
        """Return every run, oldest first."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, name, status, started_at, finished_at FROM runs ORDER BY id"
            ).fetchall()
        return [Run(*row) for row in rows]

    def get(self, run_id: int) -> Run | None:
        """Return the run matching ``run_id``, or ``None``.

        Args:
            run_id: The ``id`` of the run.
        """
        with self.db.lock:
            row = self.db.conn.execute(
                "SELECT id, name, status, started_at, finished_at FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return Run(*row) if row else None

    def save(self, run: Run) -> None:
        """Create or update a run.

        Args:
            run: The run to persist. An unset ``id`` creates a new record and
                has one assigned; a set ``id`` updates the matching record.
        """
        with self.db.lock:
            if run.id is None:
                cursor = self.db.conn.execute(
                    "INSERT INTO runs (name, status, started_at, finished_at) VALUES (?, ?, ?, ?)",
                    (run.name, run.status, run.started_at, run.finished_at),
                )
                run.id = cursor.lastrowid
            else:
                self.db.conn.execute(
                    "UPDATE runs SET name = ?, status = ?, started_at = ?, finished_at = ? "
                    "WHERE id = ?",
                    (run.name, run.status, run.started_at, run.finished_at, run.id),
                )
            self.db.conn.commit()

    def delete(self, run_id: int) -> None:
        """Delete a run together with its params, metrics and artifacts.

        Args:
            run_id: The ``id`` of the run to remove.
        """
        with self.db.lock:
            for table in ("params", "metrics", "artifacts"):
                self.db.conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))  # nosec B608
            self.db.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            self.db.conn.commit()


@Storage
@Repository(Param)
class Params:
    """Every run's parameters, one row per parameter, shown as a table."""

    def __init__(self, sqlite: SQLite) -> None:
        """Store the shared ``SQLite`` component to persist through.

        Args:
            sqlite: The shared connection component.
        """
        self.db = sqlite

    def all(self) -> list[Param]:
        """Return every parameter, grouped by run."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, run_id, key, value FROM params ORDER BY run_id, id"
            ).fetchall()
        return [Param(*row) for row in rows]

    def for_run(self, run_id: int) -> dict[str, str]:
        """Return one run's parameters, by name.

        Args:
            run_id: The ``id`` of the run.
        """
        return {p.key: p.value for p in self.all() if p.run_id == run_id}

    def save(self, param: Param) -> None:
        """Insert a parameter.

        Args:
            param: The parameter to persist; its ``id`` is assigned.
        """
        with self.db.lock:
            cursor = self.db.conn.execute(
                "INSERT INTO params (run_id, key, value) VALUES (?, ?, ?)",
                (param.run_id, param.key, param.value),
            )
            param.id = cursor.lastrowid
            self.db.conn.commit()


@Storage
@Repository(Metric)
class Metrics:
    """Every run's per-step metrics, shown as a chart with one line per run."""

    def __init__(self, sqlite: SQLite) -> None:
        """Store the shared ``SQLite`` component to persist through.

        Args:
            sqlite: The shared connection component.
        """
        self.db = sqlite

    def all(self) -> list[Metric]:
        """Return every metric row, sorted by run, then step.

        So a page of records holds whole runs where it can, rather than a
        few steps of each.
        """
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, run_id, step, loss, accuracy FROM metrics ORDER BY run_id, step"
            ).fetchall()
        return [Metric(*row) for row in rows]

    def for_run(self, run_id: int) -> list[Metric]:
        """Return one run's metric rows, in step order.

        Args:
            run_id: The ``id`` of the run.
        """
        return [m for m in self.all() if m.run_id == run_id]

    def save(self, metric: Metric) -> None:
        """Insert a metric row.

        Args:
            metric: The row to persist; its ``id`` is assigned.
        """
        with self.db.lock:
            cursor = self.db.conn.execute(
                "INSERT INTO metrics (run_id, step, loss, accuracy) VALUES (?, ?, ?, ?)",
                (metric.run_id, metric.step, metric.loss, metric.accuracy),
            )
            metric.id = cursor.lastrowid
            self.db.conn.commit()

    def data_view(self) -> TimeseriesView:
        """Chart ``loss`` and ``accuracy`` against ``step``, one line per run.

        Returns:
            A ``TimeseriesView`` ordered by ``step`` and grouped by ``run_id``.
        """
        return TimeseriesView(field="step", fields=("loss", "accuracy"), group="run_id")


@Storage
@Repository(Artifact)
class Artifacts:
    """Every run's artifacts, each opened as a document."""

    def __init__(self, sqlite: SQLite) -> None:
        """Store the shared ``SQLite`` component to persist through.

        Args:
            sqlite: The shared connection component.
        """
        self.db = sqlite

    def all(self) -> list[Artifact]:
        """Return every artifact, grouped by run."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, run_id, name, content FROM artifacts ORDER BY run_id, id"
            ).fetchall()
        return [Artifact(id=r[0], run_id=r[1], name=r[2], content=json.loads(r[3])) for r in rows]

    def save(self, artifact: Artifact) -> None:
        """Insert an artifact, storing its content as JSON.

        Args:
            artifact: The artifact to persist; its ``id`` is assigned.
        """
        with self.db.lock:
            cursor = self.db.conn.execute(
                "INSERT INTO artifacts (run_id, name, content) VALUES (?, ?, ?)",
                (artifact.run_id, artifact.name, json.dumps(artifact.content)),
            )
            artifact.id = cursor.lastrowid
            self.db.conn.commit()

    def data_view(self) -> DocumentView:
        """Open each artifact's ``content`` as a document.

        Returns:
            A ``DocumentView`` keyed on the ``content`` field.
        """
        return DocumentView(field="content")
