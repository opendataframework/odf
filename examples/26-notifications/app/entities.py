"""Entities for the notifications example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Order:
    """An order taken at the café's counter.

    Attributes:
        id: Primary key, ``None`` until ``Orders.save()`` assigns one.
        table: The table it's for.
        item: What was ordered, a key of ``MENU``.
    """

    id: int | None
    table: int
    item: str


@Entity
@dataclass
class Supply:
    """One ingredient in the pantry.

    Attributes:
        id: Primary key.
        name: The ingredient's name.
        stock: Portions left.
    """

    id: int
    name: str
    stock: int
