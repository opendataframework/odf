"""Entities for the custom-theme example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Account:
    """One customer account of a subscription product.

    Attributes:
        id: Primary key, ``None`` until ``Accounts.save()`` assigns one.
        name: The customer's company name.
        plan: The subscription plan: ``"Free"``, ``"Pro"`` or ``"Enterprise"``.
        mrr: Monthly recurring revenue, in whole dollars.
    """

    id: int | None
    name: str
    plan: str
    mrr: int
