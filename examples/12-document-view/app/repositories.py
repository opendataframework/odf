"""In-memory repository backing the document-view example."""

import mimetypes
import time
from pathlib import Path

from opendataframework import ContentMetadata, DocumentView, Repository, Storage

from app.entities import OrderReceipt

_RECEIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "receipts"

# (order_id, receipt document or file) — one receipt per kind of document the
# view shows (JSON, a text file, a PDF, Markdown, a JSON file), so there are
# real receipts to look at without hand-triggering a save() first.
_SEED_RECEIPTS: tuple[tuple[int, dict | str | Path], ...] = (
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
    (103, _RECEIPTS_DIR / "order-103.txt"),
    (104, _RECEIPTS_DIR / "order-104.pdf"),
    (105, _RECEIPTS_DIR / "order-105.md"),
    (106, _RECEIPTS_DIR / "order-106.json"),
)


@Storage
@Repository(OrderReceipt)
class OrderReceipts:
    """In-memory ``OrderReceipts`` repository, pre-seeded with ``_SEED_RECEIPTS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a document view is a lot more useful to
    look at with a few real receipts already in it than an empty one. The
    receipt files are only read once, when it is created; ``document``
    holds their bytes, and the file names are kept beside the receipts for
    ``content_metadata()``.
    """

    def __init__(self) -> None:
        """Seed the in-memory receipt list from ``_SEED_RECEIPTS``."""
        now = time.time()
        self._receipts: list[OrderReceipt] = []
        self._filenames: dict[int, str] = {}
        for receipt_id, (order_id, document) in enumerate(_SEED_RECEIPTS, start=1):
            if isinstance(document, Path):
                self._filenames[receipt_id] = document.name
                document = document.read_bytes()
            self._receipts.append(
                OrderReceipt(id=receipt_id, order_id=order_id, document=document, issued_at=now)
            )
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

    def content_metadata(self, receipt: OrderReceipt) -> ContentMetadata:
        """Name a receipt read from a file, and give its type.

        The file name isn't an ``OrderReceipt`` field: the repository keeps
        it, and the type follows from its extension. A receipt held in the
        record itself, or saved without a file, declares nothing.

        Args:
            receipt: The receipt whose document to describe.

        Returns:
            The receipt's file name and type, or an empty ``ContentMetadata``.
        """
        filename = self._filenames.get(receipt.id)
        if filename is None:
            return ContentMetadata()
        return ContentMetadata(filename=filename, content_type=mimetypes.guess_type(filename)[0])
