"""Entities for the timeseries-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Order:
    """An order shown as a timeseries via ``Orders.data_view()``.

    Attributes:
        id: Primary key, ``None`` until ``Orders.save()`` assigns one.
        amount: The order total.
        created_at: ``time.time()`` when the order was placed.
    """

    id: int | None
    amount: float
    created_at: float
