from app.entities import OrderReceipt
from app.repositories import OrderReceipts
from opendataframework import DocumentView

# Deliberately builds OrderReceipts directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_order_receipts_save_assigns_incrementing_ids():
    receipts = OrderReceipts()
    seeded = len(receipts.all())

    receipts.save(OrderReceipt(id=None, order_id=101, document={}, issued_at=1.0))
    receipts.save(OrderReceipt(id=None, order_id=102, document={}, issued_at=2.0))

    assert [r.id for r in receipts.all()][seeded:] == [seeded + 1, seeded + 2]


def test_order_receipts_save_updates_existing_record():
    receipts = OrderReceipts()
    before = len(receipts.all())
    receipts.save(OrderReceipt(id=None, order_id=101, document={"total": 1}, issued_at=1.0))
    saved = receipts.all()[-1]

    saved.document = {"total": 2}
    receipts.save(saved)

    assert len(receipts.all()) == before + 1
    assert receipts.all()[-1].document == {"total": 2}


def test_order_receipts_delete_removes_record():
    receipts = OrderReceipts()
    before = len(receipts.all())
    receipts.save(OrderReceipt(id=None, order_id=101, document={}, issued_at=1.0))
    new_id = receipts.all()[-1].id

    receipts.delete(new_id)

    assert len(receipts.all()) == before


def test_order_receipts_data_view_is_document():
    receipts = OrderReceipts()

    assert receipts.data_view() == DocumentView(field="document")
