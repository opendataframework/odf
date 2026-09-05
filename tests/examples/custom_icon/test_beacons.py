from app.entities import Beacon
from app.repositories import Beacons
from opendataframework.view import DataViewProtocol

# Deliberately builds Beacons directly rather than going through Project/
# Context — same reason as the other examples' tests, see
# tests/examples/table_view/test_books.py.


def test_beacons_starts_pre_seeded():
    beacons = Beacons()

    assert [b.name for b in beacons.all()] == ["Point Reyes", "Cape Hatteras"]


def test_beacons_save_assigns_incrementing_ids_after_seed():
    beacons = Beacons()

    beacons.save(Beacon(id=None, name="Montauk Point", active=True))
    beacons.save(Beacon(id=None, name="Cape Cod", active=True))

    assert [b.id for b in beacons.all()] == [1, 2, 3, 4]


def test_beacons_save_updates_existing_record():
    beacons = Beacons()
    saved = beacons.all()[0]

    saved.active = False
    beacons.save(saved)

    assert len(beacons.all()) == 2
    assert beacons.all()[0].active is False


def test_beacons_delete_removes_record():
    beacons = Beacons()

    beacons.delete(1)

    assert [b.name for b in beacons.all()] == ["Cape Hatteras"]


def test_beacons_implements_no_data_view():
    beacons = Beacons()

    assert not isinstance(beacons, DataViewProtocol)
