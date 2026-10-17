"""In-memory repository backing the function example."""

from opendataframework import Repository, Storage

from app.entities import Order

# (store, amount, currency)
_SEED_ORDERS: tuple[tuple[str, float, str], ...] = (
    ("Berlin", 120.0, "EUR"),
    ("Berlin", 80.0, "USD"),
    ("London", 50.0, "GBP"),
    ("London", 200.0, "USD"),
    ("Lisbon", 40.0, "EUR"),
)


@Storage
@Repository(Order)
class Orders:
    """In-memory ``Order`` repository, pre-seeded with ``_SEED_ORDERS``."""

    def __init__(self) -> None:
        """Seed the orders from ``_SEED_ORDERS``."""
        self._orders = [
            Order(id=order_id, store=store, amount=amount, currency=currency)
            for order_id, (store, amount, currency) in enumerate(_SEED_ORDERS, start=1)
        ]

    def all(self) -> list[Order]:
        """Return every order."""
        return list(self._orders)
