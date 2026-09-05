from app.analytics import SummarizeReadings
from app.entities import Reading
from app.repositories import Readings
from app.storages import SQLite
from opendataframework.config import Config
from opendataframework.logger import LogManager

# Deliberately builds Readings/SQLite/SummarizeReadings directly rather than
# going through Project/Context — same reason as the other examples' tests
# (see tests/examples/entity_repository/test_books.py): registration is
# global for the whole pytest process.


def _readings(tmp_path) -> Readings:
    config = Config({"sqlite": {"path": str(tmp_path / "test.db")}})
    return Readings(SQLite(config))


def test_summarize_readings_writes_report(tmp_path):
    readings = _readings(tmp_path)
    readings.save(Reading(id=None, sensor="kitchen", celsius=21.0))
    readings.save(Reading(id=None, sensor="kitchen", celsius=23.0))
    readings.save(Reading(id=None, sensor="garage", celsius=17.0))

    report_path = tmp_path / "reports" / "summary.json"
    config = Config({"summarize-readings": {"report-path": str(report_path)}})
    logger = LogManager().logger_for("SummarizeReadings")

    summary = SummarizeReadings(readings, config, logger).execute()

    assert summary == {
        "reading_count": 3,
        "average_celsius_by_sensor": {"kitchen": 22.0, "garage": 17.0},
    }
    assert report_path.exists()


def test_summarize_readings_handles_no_data(tmp_path):
    readings = _readings(tmp_path)
    report_path = tmp_path / "reports" / "summary.json"
    config = Config({"summarize-readings": {"report-path": str(report_path)}})
    logger = LogManager().logger_for("SummarizeReadings")

    summary = SummarizeReadings(readings, config, logger).execute()

    assert summary == {"reading_count": 0, "average_celsius_by_sensor": {}}
