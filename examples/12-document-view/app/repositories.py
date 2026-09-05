"""In-memory repository backing the document-view example."""

import time

from opendataframework import DocumentView, Repository, Storage

from app.entities import OrderReceipt

# (order_id, receipt document) — so there's a real receipt to look at
# without hand-triggering a save() first.
_SEED_RECEIPTS: tuple[tuple[int, dict], ...] = (
    (
        101,
        {
            "order_id": 101,
            "line_items": [{"sku": "SKU-0101", "quantity": 1, "price": 92.59}],
            "subtotal": 92.59,
            "tax": 7.41,
            "total": 100.00,
        },
    ),
)


@Storage
@Repository(OrderReceipt)
class OrderReceipts:
    """In-memory ``OrderReceipts`` repository, pre-seeded with ``_SEED_RECEIPTS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a document view is a lot more useful to
    look at with a real receipt already in it than an empty one.
    """

    def __init__(self) -> None:
        """Seed the in-memory receipt list from ``_SEED_RECEIPTS``."""
        now = time.time()
        self._receipts: list[OrderReceipt] = [
            OrderReceipt(id=receipt_id, order_id=order_id, document=document, issued_at=now)
            for receipt_id, (order_id, document) in enumerate(_SEED_RECEIPTS, start=1)
        ]
        self._next_id = len(self._receipts) + 1

    def all(self) -> list[OrderReceipt]:
        """Return every receipt."""
        return list(self._receipts)

    def save(self, receipt: OrderReceipt) -> None:
        """Create or update a receipt.

        Args:
            receipt: The receipt to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if receipt.id is None:
            receipt.id = self._next_id
            self._next_id += 1
            self._receipts.append(receipt)
            return
        for i, existing in enumerate(self._receipts):
            if existing.id == receipt.id:
                self._receipts[i] = receipt
                return

    def delete(self, receipt_id: int) -> None:
        """Delete the receipt matching ``receipt_id``, if one exists.

        Args:
            receipt_id: The ``id`` of the receipt to remove.
        """
        self._receipts = [r for r in self._receipts if r.id != receipt_id]

    def data_view(self) -> DocumentView:
        """Tell the UI to render these records as documents, not a table.

        Returns:
            A ``DocumentView`` keyed on the ``document`` field.
        """
        return DocumentView(field="document")
