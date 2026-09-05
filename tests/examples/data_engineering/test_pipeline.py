import csv
from pathlib import Path

import pytest
from app.entities import Reading
from app.pipelines import SetupPipeline
from app.repositories import Readings
from app.storages import SQLite
from app.tasks import ExportReadingsSummary, SeedReadings
from opendataframework.config import Config
from opendataframework.logger import LogManager

# Deliberately builds Readings/SQLite/Tasks/Pipeline directly rather than
# going through Project/Context — same reason as the other examples' tests
# (see tests/examples/entity_repository/test_books.py): registration is
# global for the whole pytest process. SeedReadings/ExportReadingsSummary
# read/write paths relative to the cwd (data/raw/, data/processed/), so
# each test chdirs into tmp_path first.


def _write_raw_csv(base: Path) -> None:
    raw_dir = base / "data" / "raw"
    raw_dir.mkdir(parents=True)
    with open(raw_dir / "readings.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sensor", "celsius"])
        writer.writerow(["kitchen", "21.0"])
        writer.writerow(["kitchen", "23.0"])
        writer.writerow(["garage", "17.0"])


@pytest.fixture
def readings(tmp_path) -> Readings:
    config = Config({"sqlite": {"path": str(tmp_path / "test.db")}})
    return Readings(SQLite(config))


def test_seed_readings_ingests_raw_csv(tmp_path, monkeypatch, readings):
    _write_raw_csv(tmp_path)
    monkeypatch.chdir(tmp_path)
    logger = LogManager().logger_for("SeedReadings")

    count = SeedReadings(readings, logger).execute()

    assert count == 3
    assert len(readings.all()) == 3


def test_seed_readings_skips_if_already_seeded(tmp_path, monkeypatch, readings):
    _write_raw_csv(tmp_path)
    monkeypatch.chdir(tmp_path)
    readings.save(Reading(id=None, sensor="kitchen", celsius=20.0))
    logger = LogManager().logger_for("SeedReadings")

    count = SeedReadings(readings, logger).execute()

    assert count == 0
    assert len(readings.all()) == 1


def test_export_readings_summary_writes_processed_json(tmp_path, monkeypatch, readings):
    monkeypatch.chdir(tmp_path)
    readings.save(Reading(id=None, sensor="kitchen", celsius=21.0))
    readings.save(Reading(id=None, sensor="kitchen", celsius=23.0))
    logger = LogManager().logger_for("ExportReadingsSummary")

    path = ExportReadingsSummary(readings, logger).execute()

    expected = tmp_path / "data" / "processed" / "readings_summary.json"
    assert Path(path).resolve() == expected
    assert expected.exists()


def test_setup_pipeline_seeds_then_exports(tmp_path, monkeypatch, readings):
    _write_raw_csv(tmp_path)
    monkeypatch.chdir(tmp_path)
    logger = LogManager().logger_for("SetupPipeline")

    pipeline = SetupPipeline(
        SeedReadings(readings, logger), ExportReadingsSummary(readings, logger)
    )
    pipeline.execute()

    assert len(readings.all()) == 3
    assert (tmp_path / "data" / "processed" / "readings_summary.json").exists()
