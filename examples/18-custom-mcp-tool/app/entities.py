"""Entities for the custom-mcp-tool example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Item:
    """A stock-room item tracked for reorder alerts.

    Attributes:
        id: Primary key, ``None`` until ``Items.save()`` assigns one.
        name: The item's name.
        quantity: Units currently in stock.
        reorder_level: Quantity at or below which the item needs restocking.
    """

    id: int | None
    name: str
    quantity: int
    reorder_level: int
