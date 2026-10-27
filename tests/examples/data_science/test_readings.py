import pytest
from app.entities import Reading
from app.repositories import Readings
from app.storages import SQLite
from opendataframework.config import Config

# Deliberately builds SQLite/Readings directly rather than going through
# Project/Context — same reason as the other examples' tests (see
# tests/examples/entity_repository/test_books.py): registration is global
# for the whole pytest process. It also mirrors how notebooks/explore.ipynb
# builds Readings standalone, outside a running Project.


@pytest.fixture
def readings(tmp_path) -> Readings:
    config = Config({"component": {"sqlite": {"path": str(tmp_path / "test.db")}}})
    sqlite = SQLite(config)
    yield Readings(sqlite)
    sqlite.on_stop()


def test_readings_repository_save_and_all(readings):
    assert readings.all() == []

    readings.save(Reading(id=None, sensor="kitchen", celsius=21.5))
    readings.save(Reading(id=None, sensor="garage", celsius=17.0))

    saved = readings.all()
    assert len(saved) == 2
    assert {r.sensor for r in saved} == {"kitchen", "garage"}


def test_readings_are_persisted_across_repository_instances(tmp_path):
    config = Config({"component": {"sqlite": {"path": str(tmp_path / "test.db")}}})
    first = SQLite(config)
    Readings(first).save(Reading(id=None, sensor="kitchen", celsius=21.5))
    first.on_stop()

    second = SQLite(config)
    reopened = Readings(second)
    assert len(reopened.all()) == 1
    second.on_stop()
