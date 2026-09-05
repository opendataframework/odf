"""Entities for the location-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Store:
    """A store location shown on the map via ``Stores.data_view()``.

    Attributes:
        id: Primary key, ``None`` until ``Stores.save()`` assigns one.
        name: The store's display name.
        lat: Latitude, in decimal degrees.
        lon: Longitude, in decimal degrees.
    """

    id: int | None
    name: str
    lat: float
    lon: float
