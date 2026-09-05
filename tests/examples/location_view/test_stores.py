from app.entities import Store
from app.repositories import Stores
from opendataframework import LocationView

# Deliberately builds Stores directly rather than going through Project/
# Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_stores_save_assigns_incrementing_ids():
    stores = Stores()
    seeded = len(stores.all())

    stores.save(Store(id=None, name="Downtown", lat=40.7128, lon=-74.0060))
    stores.save(Store(id=None, name="Uptown", lat=40.8116, lon=-73.9465))

    assert [s.id for s in stores.all()][seeded:] == [seeded + 1, seeded + 2]


def test_stores_save_updates_existing_record():
    stores = Stores()
    before = len(stores.all())
    stores.save(Store(id=None, name="Downtown", lat=40.7128, lon=-74.0060))
    saved = stores.all()[-1]

    saved.name = "Downtown (renamed)"
    stores.save(saved)

    assert len(stores.all()) == before + 1
    assert stores.all()[-1].name == "Downtown (renamed)"


def test_stores_delete_removes_record():
    stores = Stores()
    before = len(stores.all())
    stores.save(Store(id=None, name="Downtown", lat=40.7128, lon=-74.0060))
    new_id = stores.all()[-1].id

    stores.delete(new_id)

    assert len(stores.all()) == before


def test_stores_data_view_is_location():
    stores = Stores()

    assert stores.data_view() == LocationView(fields=("lat", "lon"))
