from app.entities import Order
from app.repositories import Orders
from opendataframework import TimeseriesView

# Deliberately builds Orders directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_orders_save_assigns_incrementing_ids():
    orders = Orders()
    seeded = len(orders.all())

    orders.save(Order(id=None, amount=129.99, created_at=1.0))
    orders.save(Order(id=None, amount=18.30, created_at=2.0))

    assert [o.id for o in orders.all()][seeded:] == [seeded + 1, seeded + 2]


def test_orders_save_updates_existing_record():
    orders = Orders()
    before = len(orders.all())
    orders.save(Order(id=None, amount=129.99, created_at=1.0))
    saved = orders.all()[-1]

    saved.amount = 200.00
    orders.save(saved)

    assert len(orders.all()) == before + 1
    assert orders.all()[-1].amount == 200.00


def test_orders_delete_removes_record():
    orders = Orders()
    before = len(orders.all())
    orders.save(Order(id=None, amount=129.99, created_at=1.0))
    new_id = orders.all()[-1].id

    orders.delete(new_id)

    assert len(orders.all()) == before


def test_orders_data_view_is_timeseries():
    orders = Orders()

    assert orders.data_view() == TimeseriesView(field="created_at")
