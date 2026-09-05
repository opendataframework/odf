"""Entities for the custom-icon example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Beacon:
    """A coastal beacon tracked in the harbor authority's registry.

    Attributes:
        id: Primary key, ``None`` until ``Beacons.save()`` assigns one.
        name: The beacon's name.
        active: Whether the beacon's light is currently lit.
    """

    id: int | None
    name: str
    active: bool
