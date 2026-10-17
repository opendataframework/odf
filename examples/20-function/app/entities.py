"""Entities for the function example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Order:
    """One order taken by a store, in the currency it was paid in.

    Attributes:
        id: Primary key.
        store: The store that took the order.
        amount: The amount paid.
        currency: The ISO code of the currency it was paid in.
    """

    id: int
    store: str
    amount: float
    currency: str
