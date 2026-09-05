import csv
from pathlib import Path

import pytest
from app.entities import Reading
from app.experiments import RunExperiment
from app.repositories import Readings
from app.storages import SQLite
from opendataframework.config import Config
from opendataframework.logger import LogManager

# Deliberately builds Readings/SQLite/RunExperiment directly rather than
# going through Project/Context — same reason as the other examples' tests
# (see tests/examples/entity_repository/test_books.py): registration is
# global for the whole pytest process. RunExperiment reads/writes paths
# relative to the cwd (data/, results/), so each test chdirs into tmp_path
# first.


def _write_data_csv(base: Path) -> None:
    data_dir = base / "data"
    data_dir.mkdir(parents=True)
    with open(data_dir / "readings.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sensor", "celsius"])
        writer.writerow(["kitchen", "21.0"])
        writer.writerow(["kitchen", "23.0"])
        writer.writerow(["garage", "17.0"])


@pytest.fixture
def readings(tmp_path) -> Readings:
    config = Config({"sqlite": {"path": str(tmp_path / "test.db")}})
    return Readings(SQLite(config))


def test_run_experiment_loads_data_and_writes_results(tmp_path, monkeypatch, readings):
    _write_data_csv(tmp_path)
    monkeypatch.chdir(tmp_path)
    logger = LogManager().logger_for("RunExperiment")

    summary = RunExperiment(readings, logger).execute()

    assert summary == {
        "reading_count": 3,
        "average_celsius_by_sensor": {"kitchen": 22.0, "garage": 17.0},
    }
    assert (tmp_path / "results" / "summary.json").exists()


def test_run_experiment_skips_reload_but_recomputes(tmp_path, monkeypatch, readings):
    _write_data_csv(tmp_path)
    monkeypatch.chdir(tmp_path)
    readings.save(Reading(id=None, sensor="attic", celsius=30.0))
    logger = LogManager().logger_for("RunExperiment")

    summary = RunExperiment(readings, logger).execute()

    assert summary["reading_count"] == 1
    assert summary["average_celsius_by_sensor"] == {"attic": 30.0}
