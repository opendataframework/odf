"""In-memory repository backing the location-view example."""

from opendataframework import LocationView, Repository, Storage

from app.entities import Store

# (name, lat, lon) — real coordinates spread across the US, so the map has
# something worth looking at without hand-typing coordinates through the UI.
_SEED_STORES: tuple[tuple[str, float, float], ...] = (
    ("San Francisco Downtown", 37.7749, -122.4194),
    ("Seattle Downtown", 47.6062, -122.3321),
    ("Austin Downtown", 30.2672, -97.7431),
    ("Chicago Loop", 41.8781, -87.6298),
    ("New York Midtown", 40.7549, -73.9840),
    ("Miami Downtown", 25.7617, -80.1918),
)


@Storage
@Repository(Store)
class Stores:
    """In-memory ``Store`` repository, pre-seeded with ``_SEED_STORES``.

    Kept in-memory on purpose — the concept this example isolates is
    ``data_view()``, not persistence (see ../02-data-analytics for a
    SQLite-backed repository). Pre-seeded, also on purpose — a map with a
    single pin or two isn't much of a showcase, and typing coordinates by
    hand isn't a great way to explore one.
    """

    def __init__(self) -> None:
        """Seed the in-memory store list from ``_SEED_STORES``."""
        self._stores: list[Store] = [
            Store(id=store_id, name=name, lat=lat, lon=lon)
            for store_id, (name, lat, lon) in enumerate(_SEED_STORES, start=1)
        ]
        self._next_id = len(self._stores) + 1

    def all(self) -> list[Store]:
        """Return every store."""
        return list(self._stores)

    def save(self, store: Store) -> None:
        """Create or update a store.

        Args:
            store: The store to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if store.id is None:
            store.id = self._next_id
            self._next_id += 1
            self._stores.append(store)
            return
        for i, existing in enumerate(self._stores):
            if existing.id == store.id:
                self._stores[i] = store
                return

    def delete(self, store_id: int) -> None:
        """Delete the store matching ``store_id``, if one exists.

        Args:
            store_id: The ``id`` of the store to remove.
        """
        self._stores = [s for s in self._stores if s.id != store_id]

    def data_view(self) -> LocationView:
        """Tell the UI to render these records as a map, not a table.

        Returns:
            A ``LocationView`` keyed on the ``lat``/``lon`` fields.
        """
        return LocationView(fields=("lat", "lon"))
