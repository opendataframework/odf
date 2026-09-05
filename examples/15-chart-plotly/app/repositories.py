"""In-memory repository backing the chart-plotly example."""

from opendataframework import Repository, Storage

from app.entities import Sale

# (store, amount) — so there are real sales for SalesByStore.chart() to
# aggregate without hand-triggering a save() first.
_SEED_SALES: tuple[tuple[str, float], ...] = (
    ("Downtown", 120.0),
    ("Downtown", 80.0),
    ("Uptown", 45.0),
)


@Storage
@Repository(Sale)
class Sales:
    """In-memory ``Sales`` repository, pre-seeded with ``_SEED_SALES``.

    Kept in-memory on purpose — the concept here is ``ChartProtocol``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a bar chart is a lot more useful to look
    at with a couple of real sales already in it than an empty one.
    """

    def __init__(self) -> None:
        """Seed the in-memory sale list from ``_SEED_SALES``."""
        self._sales: list[Sale] = [
            Sale(id=sale_id, store=store, amount=amount)
            for sale_id, (store, amount) in enumerate(_SEED_SALES, start=1)
        ]
        self._next_id = len(self._sales) + 1

    def all(self) -> list[Sale]:
        """Return every sale."""
        return list(self._sales)

    def save(self, sale: Sale) -> None:
        """Create or update a sale.

        Args:
            sale: The sale to persist. An unset ``id`` creates a new record
                and has one assigned; a set ``id`` updates the matching
                record in place.
        """
        if sale.id is None:
            sale.id = self._next_id
            self._next_id += 1
            self._sales.append(sale)
            return
        for i, existing in enumerate(self._sales):
            if existing.id == sale.id:
                self._sales[i] = sale
                return

    def delete(self, sale_id: int) -> None:
        """Delete the sale matching ``sale_id``, if one exists.

        Args:
            sale_id: The ``id`` of the sale to remove.
        """
        self._sales = [s for s in self._sales if s.id != sale_id]
