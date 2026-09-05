"""Entities for the document-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class OrderReceipt:
    """An order receipt shown via ``OrderReceipts.data_view()``.

    Attributes:
        id: Primary key, ``None`` until ``OrderReceipts.save()`` assigns one.
        order_id: The order this receipt was issued for.
        document: The receipt content, as a JSON-serializable dict.
        issued_at: ``time.time()`` when the receipt was issued.
    """

    id: int | None
    order_id: int
    document: dict
    issued_at: float
