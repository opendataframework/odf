"""In-memory repository backing the custom-mcp-tool example."""

from opendataframework import Repository, Storage

from app.entities import Item

# (name, quantity, reorder_level) — a couple of items already below their
# reorder level, so low_stock() has something to report without
# hand-seeding through the UI first.
_SEED_ITEMS: tuple[tuple[str, int, int], ...] = (
    ("Packing tape", 4, 10),
    ("Bubble wrap", 25, 15),
    ("Shipping labels", 2, 20),
)


@Storage
@Repository(Item)
class Items:
    """In-memory ``Item`` repository, pre-seeded with ``_SEED_ITEMS``.

    Implements no ``data_view()`` — the concept this example isolates is
    ``StockRoom``'s custom MCP tool, not the data view, so it renders as
    the same plain default table as ../01-table-view.
    """

    def __init__(self) -> None:
        """Seed the in-memory item list from ``_SEED_ITEMS``."""
        self._items: list[Item] = [
            Item(id=item_id, name=name, quantity=quantity, reorder_level=reorder_level)
            for item_id, (name, quantity, reorder_level) in enumerate(_SEED_ITEMS, start=1)
        ]
        self._next_id = len(self._items) + 1

    def all(self) -> list[Item]:
        """Return every item."""
        return list(self._items)

    def save(self, item: Item) -> None:
        """Create or update an item.

        Args:
            item: The item to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if item.id is None:
            item.id = self._next_id
            self._next_id += 1
            self._items.append(item)
            return
        for i, existing in enumerate(self._items):
            if existing.id == item.id:
                self._items[i] = item
                return
