"""In-memory repository backing the document-view example."""

import time
from pathlib import Path

from opendataframework import DocumentView, Repository, Storage

from app.entities import OrderReceipt

_RECEIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "receipts"

# (order_id, receipt document) — one receipt per kind of document the view
# shows (JSON, a text file, a PDF, Markdown), so there are real receipts to look at
# without hand-triggering a save() first.
_SEED_RECEIPTS: tuple[tuple[int, dict | str | bytes], ...] = (
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
    (
        102,
        {
            "order_id": 102,
            "line_items": [
                {"sku": "SKU-0102", "quantity": 2, "price": 12.50},
                {"sku": "SKU-0318", "quantity": 1, "price": 25.00},
            ],
            "subtotal": 50.00,
            "tax": 4.00,
            "total": 54.00,
        },
    ),
    (103, (_RECEIPTS_DIR / "order-103.txt").read_bytes()),
    (104, (_RECEIPTS_DIR / "order-104.pdf").read_bytes()),
    (105, (_RECEIPTS_DIR / "order-105.md").read_bytes()),
)


@Storage
@Repository(OrderReceipt)
class OrderReceipts:
    """In-memory ``OrderReceipts`` repository, pre-seeded with ``_SEED_RECEIPTS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a document view is a lot more useful to
    look at with a few real receipts already in it than an empty one. The
    receipt files are only read once, at import; ``document`` holds their
    bytes.
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
