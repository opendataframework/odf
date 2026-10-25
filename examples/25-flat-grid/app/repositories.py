"""In-memory repositories backing the flat-grid example."""

from opendataframework import Repository, Storage

from app.entities import Courier, Parcel


@Storage
@Repository(Parcel)
class Parcels:
    """In-memory ``Parcel`` repository, seeded with a few unsorted parcels."""

    def __init__(self) -> None:
        """Start with three unsorted parcels."""
        self._parcels = [
            Parcel(id=1, destination="Lyon", weight_kg=2.5, sorted=False),
            Parcel(id=2, destination="Porto", weight_kg=0.8, sorted=False),
            Parcel(id=3, destination="Gdansk", weight_kg=6.0, sorted=False),
        ]
        self._next_id = 4

    def all(self) -> list[Parcel]:
        """Return every parcel."""
        return list(self._parcels)

    def save(self, parcel: Parcel) -> None:
        """Create or update a parcel.

        Args:
            parcel: The parcel to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if parcel.id is None:
            parcel.id = self._next_id
            self._next_id += 1
            self._parcels.append(parcel)
            return
        for i, existing in enumerate(self._parcels):
            if existing.id == parcel.id:
                self._parcels[i] = parcel
                return

    def delete(self, parcel_id: int) -> None:
        """Delete the parcel matching ``parcel_id``, if one exists.

        Args:
            parcel_id: The ``id`` of the parcel to remove.
        """
        self._parcels = [p for p in self._parcels if p.id != parcel_id]


@Storage
@Repository(Courier)
class Couriers:
    """In-memory ``Courier`` repository, seeded with two couriers.

    Its node is the one ``layout.json`` customizes on the flat grid.
    """

    def __init__(self) -> None:
        """Start with two couriers."""
        self._couriers = [Courier(id=1, name="Ines"), Courier(id=2, name="Tomasz")]
        self._next_id = 3

    def all(self) -> list[Courier]:
        """Return every courier."""
        return list(self._couriers)

    def save(self, courier: Courier) -> None:
        """Create or update a courier.

        Args:
            courier: The courier to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if courier.id is None:
            courier.id = self._next_id
            self._next_id += 1
            self._couriers.append(courier)
            return
        for i, existing in enumerate(self._couriers):
            if existing.id == courier.id:
                self._couriers[i] = courier
                return

    def delete(self, courier_id: int) -> None:
        """Delete the courier matching ``courier_id``, if one exists.

        Args:
            courier_id: The ``id`` of the courier to remove.
        """
        self._couriers = [c for c in self._couriers if c.id != courier_id]
