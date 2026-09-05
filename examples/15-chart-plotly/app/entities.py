"""Entities for the chart-plotly example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Sale:
    """A single sale, aggregated by ``SalesByStore.chart()``.

    Attributes:
        id: Primary key, ``None`` until ``Sales.save()`` assigns one.
        store: Name of the store the sale was made at.
        amount: The sale amount.
    """

    id: int | None
    store: str
    amount: float
