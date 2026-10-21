import json

from opendataframework import DocumentView, Repository, Storage, TimeseriesView

from app.entities import Artifact, Metric, Param, Run
from app.storages import SQLite


@Storage
@Repository(Run)
class Runs:
    def __init__(self, sqlite: SQLite) -> None:
        self.db = sqlite

    def all(self) -> list[Run]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, name, status, started_at, finished_at FROM runs ORDER BY id"
            ).fetchall()
        return [Run(*row) for row in rows]

    def get(self, run_id: int) -> Run | None:
        with self.db.lock:
            row = self.db.conn.execute(
                "SELECT id, name, status, started_at, finished_at FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return Run(*row) if row else None

    def save(self, run: Run) -> None:
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
        """Delete a run together with its params, metrics and artifacts."""
        with self.db.lock:
            for table in ("params", "metrics", "artifacts"):
                self.db.conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))  # nosec B608
            self.db.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            self.db.conn.commit()


@Storage
@Repository(Param)
class Params:
    def __init__(self, sqlite: SQLite) -> None:
        self.db = sqlite

    def all(self) -> list[Param]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, run_id, key, value FROM params ORDER BY run_id, id"
            ).fetchall()
        return [Param(*row) for row in rows]

    def for_run(self, run_id: int) -> dict[str, str]:
        return {p.key: p.value for p in self.all() if p.run_id == run_id}

    def save(self, param: Param) -> None:
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
    def __init__(self, sqlite: SQLite) -> None:
        self.db = sqlite

    def all(self) -> list[Metric]:
        # Sorted by run, then step, so a page of records holds whole runs
        # where it can, rather than a few steps of each.
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, run_id, step, loss, accuracy FROM metrics ORDER BY run_id, step"
            ).fetchall()
        return [Metric(*row) for row in rows]

    def for_run(self, run_id: int) -> list[Metric]:
        return [m for m in self.all() if m.run_id == run_id]

    def save(self, metric: Metric) -> None:
        with self.db.lock:
            cursor = self.db.conn.execute(
                "INSERT INTO metrics (run_id, step, loss, accuracy) VALUES (?, ?, ?, ?)",
                (metric.run_id, metric.step, metric.loss, metric.accuracy),
            )
            metric.id = cursor.lastrowid
            self.db.conn.commit()

    def data_view(self) -> TimeseriesView:
        return TimeseriesView(field="step", fields=("loss", "accuracy"), group="run_id")


@Storage
@Repository(Artifact)
class Artifacts:
    def __init__(self, sqlite: SQLite) -> None:
        self.db = sqlite

    def all(self) -> list[Artifact]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, run_id, name, content FROM artifacts ORDER BY run_id, id"
            ).fetchall()
        return [Artifact(id=r[0], run_id=r[1], name=r[2], content=json.loads(r[3])) for r in rows]

    def save(self, artifact: Artifact) -> None:
        with self.db.lock:
            cursor = self.db.conn.execute(
                "INSERT INTO artifacts (run_id, name, content) VALUES (?, ?, ?)",
                (artifact.run_id, artifact.name, json.dumps(artifact.content)),
            )
            artifact.id = cursor.lastrowid
            self.db.conn.commit()

    def data_view(self) -> DocumentView:
        return DocumentView(field="content")
