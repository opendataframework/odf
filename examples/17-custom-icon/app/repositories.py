"""In-memory repository backing the custom-icon example."""

from opendataframework import Repository, Storage

from app.entities import Beacon

# (name, active) — a couple of real beacons to look at without hand-typing
# records through the UI first.
_SEED_BEACONS: tuple[tuple[str, bool], ...] = (
    ("Point Reyes", True),
    ("Cape Hatteras", False),
)


@Storage
@Repository(Beacon)
class Beacons:
    """In-memory ``Beacon`` repository, pre-seeded with ``_SEED_BEACONS``.

    Implements no ``data_view()`` — the concept this example isolates is a
    custom node icon (see ``../icons/lighthouse.js`` and this project's
    ``config.toml``), not the data view, so it renders as the same plain
    default table as ../01-table-view.
    """

    def __init__(self) -> None:
        """Seed the in-memory beacon list from ``_SEED_BEACONS``."""
        self._beacons: list[Beacon] = [
            Beacon(id=beacon_id, name=name, active=active)
            for beacon_id, (name, active) in enumerate(_SEED_BEACONS, start=1)
        ]
        self._next_id = len(self._beacons) + 1

    def all(self) -> list[Beacon]:
        """Return every beacon."""
        return list(self._beacons)

    def save(self, beacon: Beacon) -> None:
        """Create or update a beacon.

        Args:
            beacon: The beacon to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if beacon.id is None:
            beacon.id = self._next_id
            self._next_id += 1
            self._beacons.append(beacon)
            return
        for i, existing in enumerate(self._beacons):
            if existing.id == beacon.id:
                self._beacons[i] = beacon
                return

    def delete(self, beacon_id: int) -> None:
        """Delete the beacon matching ``beacon_id``, if one exists.

        Args:
            beacon_id: The ``id`` of the beacon to remove.
        """
        self._beacons = [b for b in self._beacons if b.id != beacon_id]
