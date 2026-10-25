"""Entities for the flat-grid example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Parcel:
    """A parcel waiting at the depot.

    Attributes:
        id: Primary key, ``None`` until ``Parcels.save()`` assigns one.
        destination: The city the parcel ships to.
        weight_kg: The parcel's weight, in kilograms.
        sorted: Whether ``SortParcels`` has sorted it onto a route yet.
    """

    id: int | None
    destination: str
    weight_kg: float
    sorted: bool


@Entity
@dataclass
class Courier:
    """A courier delivering the depot's parcels.

    Attributes:
        id: Primary key, ``None`` until ``Couriers.save()`` assigns one.
        name: The courier's name.
    """

    id: int | None
    name: str
