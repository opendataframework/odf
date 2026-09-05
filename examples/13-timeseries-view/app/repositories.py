"""In-memory repository backing the timeseries-view example."""

import time

from opendataframework import Repository, Storage, TimeseriesView

from app.entities import Order

_DAY = 86400

# (amount, created_at offset in seconds from construction time) — so
# there's a real line to chart without hand-triggering a save() first.
_SEED_ORDERS: tuple[tuple[float, float], ...] = (
    (129.99, -3 * _DAY),
    (18.30, -2 * _DAY),
    (275.00, -1 * _DAY),
)


@Storage
@Repository(Order)
class Orders:
    """In-memory ``Orders`` repository, pre-seeded with ``_SEED_ORDERS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a timeseries chart is a lot more useful
    to look at with a few real points already in it than an empty one.
    """

    def __init__(self) -> None:
        """Seed the in-memory order list from ``_SEED_ORDERS``."""
        now = time.time()
        self._orders: list[Order] = [
            Order(id=order_id, amount=amount, created_at=now + offset)
            for order_id, (amount, offset) in enumerate(_SEED_ORDERS, start=1)
        ]
        self._next_id = len(self._orders) + 1

    def all(self) -> list[Order]:
        """Return every order."""
        return list(self._orders)

    def save(self, order: Order) -> None:
        """Create or update an order.

        Args:
            order: The order to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if order.id is None:
            order.id = self._next_id
            self._next_id += 1
            self._orders.append(order)
            return
        for i, existing in enumerate(self._orders):
            if existing.id == order.id:
                self._orders[i] = order
                return

    def delete(self, order_id: int) -> None:
        """Delete the order matching ``order_id``, if one exists.

        Args:
            order_id: The ``id`` of the order to remove.
        """
        self._orders = [o for o in self._orders if o.id != order_id]

    def data_view(self) -> TimeseriesView:
        """Tell the UI to render these records as a timeseries, not a table.

        Returns:
            A ``TimeseriesView`` keyed on the ``created_at`` field.
        """
        return TimeseriesView(field="created_at")
