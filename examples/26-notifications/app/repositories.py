"""In-memory repositories backing the notifications example."""

from opendataframework import Repository, Storage

from app.entities import Order, Supply

# (name, stock): portions the pantry starts the day with. Oat milk is short on
# purpose, so a low-stock warning and an out-of-stock error come up soon.
STARTING_STOCK: tuple[tuple[str, int], ...] = (
    ("milk", 6),
    ("oat milk", 2),
    ("croissants", 4),
)


@Storage
@Repository(Order)
class Orders:
    """Every order taken today, in-memory, starting empty."""

    def __init__(self) -> None:
        """Start with no orders."""
        self._orders: list[Order] = []

    def all(self) -> list[Order]:
        """Return every order, oldest first."""
        return list(self._orders)

    def save(self, order: Order) -> None:
        """Create or update an order.

        Args:
            order: The order to persist. An unset ``id`` creates a new record
                and has one assigned; a set ``id`` updates the matching
                record in place.
        """
        if order.id is None:
            order.id = len(self._orders) + 1
            self._orders.append(order)
            return
        for i, existing in enumerate(self._orders):
            if existing.id == order.id:
                self._orders[i] = order
                return


@Storage
@Repository(Supply)
class Pantry:
    """The pantry's ingredients, in-memory, seeded from ``STARTING_STOCK``."""

    def __init__(self) -> None:
        """Seed the pantry."""
        self._supplies: list[Supply] = []
        self.restock()

    def all(self) -> list[Supply]:
        """Return every ingredient."""
        return list(self._supplies)

    def get(self, name: str) -> Supply:
        """Return the ingredient called ``name``.

        Raises:
            KeyError: If the pantry has no such ingredient.
        """
        for supply in self._supplies:
            if supply.name == name:
                return supply
        raise KeyError(name)

    def save(self, supply: Supply) -> None:
        """Update an ingredient's stock.

        Args:
            supply: The ingredient, matched by ``id``.
        """
        for i, existing in enumerate(self._supplies):
            if existing.id == supply.id:
                self._supplies[i] = supply
                return

    def restock(self) -> None:
        """Put every ingredient back to its starting stock."""
        self._supplies = [
            Supply(id=supply_id, name=name, stock=stock)
            for supply_id, (name, stock) in enumerate(STARTING_STOCK, start=1)
        ]
