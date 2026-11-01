"""SQLite-backed repositories, one per entity, all through the shared ``SQLite`` component."""

import dataclasses
from collections.abc import Iterable

from opendataframework import DocumentView, LocationView, Repository, Storage, TimeseriesView

from app.entities import CafeSale, Contract, Message, Product, Restaurant, StandingOrder
from app.storages import SQLite


class _Table:
    """Reads and writes one table's rows as ``entity``s, keyed on its first field.

    The repositories below differ only in their table, their view, and a few
    lookups of their own. Column names are the entity's field names, which
    come from this module, never from a request.
    """

    table: str
    entity: type

    def __init__(self, sqlite: SQLite) -> None:
        """Store the shared ``SQLite`` component to persist through.

        Args:
            sqlite: The shared connection component.
        """
        self.db = sqlite

    @property
    def _columns(self) -> list[str]:
        """The table's columns: the entity's fields, key first."""
        return [f.name for f in dataclasses.fields(self.entity)]

    def _select(self, where: str = "", args: tuple = (), order: str = "") -> list:
        """Return the entities matching ``where``, in ``order`` (the key by default)."""
        sql = f"SELECT {', '.join(self._columns)} FROM {self.table} {where} "  # nosec B608
        sql += f"ORDER BY {order or self._columns[0]}"
        with self.db.lock:
            rows = self.db.conn.execute(sql, args).fetchall()
        return [self.entity(*row) for row in rows]

    def all(self) -> list:
        """Return every row."""
        return self._select()

    def save(self, item: object) -> None:
        """Create or replace a row. An unset key creates one and has it assigned."""
        columns = self._columns
        values = [getattr(item, c) for c in columns]
        if values[0] is None:
            columns, values = columns[1:], values[1:]
        sql = (
            f"INSERT OR REPLACE INTO {self.table} ({', '.join(columns)}) "  # nosec B608
            f"VALUES ({', '.join('?' * len(columns))})"
        )
        with self.db.lock:
            cursor = self.db.conn.execute(sql, values)
            self.db.conn.commit()
        if getattr(item, self._columns[0]) is None:
            setattr(item, self._columns[0], cursor.lastrowid)

    def delete(self, key: object) -> None:
        """Delete the row with ``key``, if there is one."""
        with self.db.lock:
            self.db.conn.execute(
                f"DELETE FROM {self.table} WHERE {self._columns[0]} = ?",  # nosec B608
                (key,),
            )
            self.db.conn.commit()

    def replace_all(self, items: Iterable) -> int:
        """Replace every row with ``items``: a re-imported sheet is the truth. Returns the count."""
        items = list(items)
        with self.db.lock:
            self.db.conn.execute(f"DELETE FROM {self.table}")  # nosec B608
            self.db.conn.commit()
        for item in items:
            self.save(item)
        return len(items)


@Storage
@Repository(Product)
class Products(_Table):
    """The bakery's products, from the products sheet."""

    table, entity = "products", Product


@Storage
@Repository(Restaurant)
class Restaurants(_Table):
    """The restaurants the bakery delivers to, on a map."""

    table, entity = "restaurants", Restaurant

    def by_contact(self, contact: str) -> Restaurant | None:
        """Return the restaurant with this phone number or email address, if any."""
        found = self._select("WHERE phone = ? OR lower(email) = lower(?)", (contact, contact))
        return found[0] if found else None

    def data_view(self) -> LocationView:
        """Show the restaurants on a map."""
        return LocationView(fields=("lat", "lon"))


@Storage
@Repository(StandingOrder)
class StandingOrders(_Table):
    """Each restaurant's usual order by weekday, from the standing orders sheet."""

    table, entity = "standing_orders", StandingOrder


@Storage
@Repository(Contract)
class Contracts(_Table):
    """This quarter's agreed prices, from the contracts sheet."""

    table, entity = "contracts", Contract


@Storage
@Repository(Message)
class Messages(_Table):
    """Messages to the bakery, by chat and email, newest first, each opened as a document."""

    table, entity = "messages", Message

    def all(self) -> list[Message]:
        """Return every message, newest first."""
        return self._select(order="received_at DESC")

    def match_restaurants(self, restaurants: Iterable[Restaurant]) -> None:
        """Set each message's restaurant from its sender: a phone number or email address."""
        by_contact = {}
        for r in restaurants:
            by_contact[r.phone] = r.name
            by_contact[r.email.lower()] = r.name
        with self.db.lock:
            rows = self.db.conn.execute("SELECT id, sender FROM messages").fetchall()
            self.db.conn.executemany(
                "UPDATE messages SET restaurant = ? WHERE id = ?",
                [(by_contact.get(sender.lower()), id_) for id_, sender in rows],
            )
            self.db.conn.commit()

    def by_external_id(self, external_id: str) -> Message | None:
        """Return the message with this id in the tool it came from, if it's been taken in."""
        found = self._select("WHERE external_id = ?", (external_id,))
        return found[0] if found else None

    def data_view(self) -> DocumentView:
        """Open each message's text as a document."""
        return DocumentView(field="text")


@Storage
@Repository(CafeSale)
class CafeSales(_Table):
    """Every café order line from the POS, charted over time by product."""

    table, entity = "cafe_sales", CafeSale

    def all(self) -> list[CafeSale]:
        """Return every sale line, oldest first."""
        return self._select(order="sold_at, id")

    def has_order(self, order_id: str) -> bool:
        """Return whether the POS order ``order_id`` has been taken in."""
        with self.db.lock:
            row = self.db.conn.execute(
                "SELECT 1 FROM cafe_sales WHERE order_id = ? LIMIT 1", (order_id,)
            ).fetchone()
        return row is not None

    def count_orders(self) -> int:
        """Return how many POS orders have been taken in."""
        with self.db.lock:
            return self.db.conn.execute(
                "SELECT COUNT(DISTINCT order_id) FROM cafe_sales"
            ).fetchone()[0]

    def save_many(self, sales: Iterable[CafeSale]) -> int:
        """Insert sale lines in one transaction, skipping lines already there. Returns the count."""
        rows = [(s.sold_at, s.order_id, s.sku, s.product, s.quantity, s.revenue) for s in sales]
        with self.db.lock:
            self.db.conn.executemany(
                "INSERT OR IGNORE INTO cafe_sales (sold_at, order_id, sku, product, quantity,"
                " revenue) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            self.db.conn.commit()
        return len(rows)

    def data_view(self) -> TimeseriesView:
        """Chart quantity and revenue over time, one line per product."""
        return TimeseriesView(field="sold_at", fields=("quantity", "revenue"), group="product")
