"""SQLite-backed repositories, one per entity, all through the shared ``SQLite`` component."""

import dataclasses
from collections.abc import Iterable
from datetime import date

from opendataframework import (
    ContentMetadata,
    DocumentView,
    LocationView,
    Repository,
    TimeseriesView,
)

from app import layers
from app.entities import (
    BakeSheetLine,
    CafeSale,
    Contract,
    DeliveryStop,
    Draft,
    Forecast,
    Ingredient,
    IngredientAllergen,
    IngredientPrice,
    Invoice,
    Leftover,
    Message,
    OrderChange,
    Product,
    RecipeLine,
    Restaurant,
    StandingOrder,
)
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

    def where(self, column: str, value: object) -> list:
        """Return the rows whose ``column`` (one of the entity's fields) equals ``value``."""
        if column not in self._columns:
            raise KeyError(column)
        return self._select(f"WHERE {column} = ?", (value,))  # nosec B608

    def replace_where(self, column: str, value: object, items: Iterable) -> int:
        """Replace the rows whose ``column`` equals ``value`` with ``items``. Returns the count.

        A day's forecast or bake sheet worked out again replaces that day's
        rows, and leaves the other days' alone.
        """
        if column not in self._columns:
            raise KeyError(column)
        items = list(items)
        with self.db.lock:
            self.db.conn.execute(
                f"DELETE FROM {self.table} WHERE {column} = ?",  # nosec B608
                (value,),
            )
            self.db.conn.commit()
        for item in items:
            self.save(item)
        return len(items)

    def replace_all(self, items: Iterable) -> int:
        """Replace every row with ``items``: a re-imported sheet is the truth. Returns the count."""
        items = list(items)
        with self.db.lock:
            self.db.conn.execute(f"DELETE FROM {self.table}")  # nosec B608
            self.db.conn.commit()
        for item in items:
            self.save(item)
        return len(items)


@layers.Production
@Repository(Product)
class Products(_Table):
    """The bakery's products, from the products sheet."""

    table, entity = "products", Product


@layers.Wholesale
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


@layers.Wholesale
@Repository(StandingOrder)
class StandingOrders(_Table):
    """Each restaurant's usual order by weekday, from the standing orders sheet."""

    table, entity = "standing_orders", StandingOrder

    def for_weekday(self, weekday: str) -> list[StandingOrder]:
        """Return every restaurant's usual order on ``weekday`` (``"Monday"`` to ``"Sunday"``)."""
        return self._select("WHERE weekday = ?", (weekday,), order="restaurant, sku")


@layers.Wholesale
@Repository(Contract)
class Contracts(_Table):
    """This quarter's agreed prices, from the contracts sheet."""

    table, entity = "contracts", Contract


@layers.Wholesale
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


@layers.Cafe
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

    def daily(self, since: date, until: date) -> dict[tuple[str, str], int]:
        """Return how many of each product sold each day, from ``since`` to ``until`` inclusive.

        Returns:
            ``{("YYYY-MM-DD", sku): quantity}``, leaving out what didn't sell.
        """
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT date(sold_at, 'unixepoch', 'localtime') AS day, sku, SUM(quantity)"
                " FROM cafe_sales GROUP BY day, sku HAVING day BETWEEN ? AND ?",
                (since.isoformat(), until.isoformat()),
            ).fetchall()
        return {(day, sku): quantity for day, sku, quantity in rows}

    def data_view(self) -> TimeseriesView:
        """Chart quantity and revenue over time, one line per product."""
        return TimeseriesView(field="sold_at", fields=("quantity", "revenue"), group="product")


@layers.Wholesale
@Repository(OrderChange)
class OrderChanges(_Table):
    """Confirmed changes to what the restaurants take, on top of their standing orders."""

    table, entity = "order_changes", OrderChange

    def for_day(self, day: date) -> list[OrderChange]:
        """Return the changes that apply on ``day``: that day's, and lasting ones from before it."""
        return self._select(
            "WHERE date = ? OR (mode = 'set-from' AND date <= ?)",
            (day.isoformat(), day.isoformat()),
            order="date, id",
        )


@layers.Drafts
@Repository(Draft)
class Drafts(_Table):
    """What the agents prepared, newest first: the control room, each draft opened as a document."""

    table, entity = "drafts", Draft

    OPEN = ("pending", "needs-review")

    def all(self) -> list[Draft]:
        """Return every draft, newest first."""
        return self._select(order="created_at DESC, id DESC")

    def get(self, draft_id: int) -> Draft:
        """Return the draft ``draft_id``.

        Raises:
            KeyError: If there's no such draft.
        """
        found = self.where("id", draft_id)
        if not found:
            raise KeyError(f"no draft {draft_id}")
        return found[0]

    def open_for_message(self, message_id: int) -> Draft | None:
        """Return the draft still waiting on a person for message ``message_id``, if any."""
        found = self._select(
            "WHERE message = ? AND status IN (?, ?)", (message_id, *self.OPEN), order="id DESC"
        )
        return found[0] if found else None

    def open_for_restaurant(self, kind: str, restaurant: str) -> Draft | None:
        """Return the ``kind`` draft for ``restaurant`` still waiting on a person, if any."""
        found = self._select(
            "WHERE kind = ? AND restaurant = ? AND status IN (?, ?)",
            (kind, restaurant, *self.OPEN),
            order="id",
        )
        return found[0] if found else None

    def open_titled(self, kind: str, title: str) -> Draft | None:
        """Return the ``kind`` draft titled ``title`` still waiting on a person, if any."""
        found = self._select(
            "WHERE kind = ? AND title = ? AND status IN (?, ?)",
            (kind, title, *self.OPEN),
            order="id",
        )
        return found[0] if found else None

    def open_for(self, kind: str, day: str) -> Draft | None:
        """Return the ``kind`` draft for ``day`` still waiting on a person, if any."""
        found = self._select(
            "WHERE kind = ? AND date = ? AND status IN (?, ?)", (kind, day, *self.OPEN), order="id"
        )
        return found[0] if found else None

    def data_view(self) -> DocumentView:
        """Open each draft as the Markdown a person reads it in."""
        return DocumentView(field="body")

    def content_metadata(self, draft: Draft) -> ContentMetadata:
        """Declare each draft's body Markdown, so the UI renders it."""
        return ContentMetadata(filename=f"draft-{draft.id}.md", content_type="text/markdown")


@layers.Cafe
@Repository(Forecast)
class Forecasts(_Table):
    """What the café expects to sell, per product per day."""

    table, entity = "forecasts", Forecast

    def all(self) -> list[Forecast]:
        """Return every forecast, newest day first."""
        return self._select(order="date DESC, sku")


@layers.Production
@Repository(BakeSheetLine)
class BakeSheets(_Table):
    """What to bake each night, per product, for the restaurants and the café."""

    table, entity = "bake_sheets", BakeSheetLine

    def all(self) -> list[BakeSheetLine]:
        """Return every bake sheet's lines, newest day first."""
        return self._select(order="date DESC, sku")

    def dates(self) -> list[str]:
        """Return the days there's a bake sheet for, ``"YYYY-MM-DD"``, oldest first."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT DISTINCT date FROM bake_sheets ORDER BY date"
            ).fetchall()
        return [row[0] for row in rows]


@layers.Cafe
@Repository(Leftover)
class Leftovers(_Table):
    """What the café didn't sell each day, of what was baked for it."""

    table, entity = "leftovers", Leftover

    def all(self) -> list[Leftover]:
        """Return every day's leftovers, newest day first."""
        return self._select(order="date DESC, sku")


@layers.Production
@Repository(DeliveryStop)
class DeliveryRuns(_Table):
    """The morning delivery runs, the latest one on a map."""

    table, entity = "delivery_runs", DeliveryStop

    def all(self) -> list[DeliveryStop]:
        """Return the latest run's stops, in order: one run on the map at a time."""
        return self._select("WHERE date = (SELECT MAX(date) FROM delivery_runs)", order="stop")

    def data_view(self) -> LocationView:
        """Show the run's stops on a map."""
        return LocationView(fields=("lat", "lon"))


@layers.Purchasing
@Repository(Ingredient)
class Ingredients(_Table):
    """What the bakery bakes with, who sells it, and what it cost on the sheet."""

    table, entity = "ingredients", Ingredient


@layers.Production
@Repository(RecipeLine)
class Recipes(_Table):
    """What one of each wholesale product takes, from the recipes sheet."""

    table, entity = "recipes", RecipeLine

    def all(self) -> list[RecipeLine]:
        """Return every recipe line, by product."""
        return self._select(order="sku, id")


@layers.Purchasing
@Repository(Invoice)
class Invoices(_Table):
    """The suppliers' invoices, newest first, each opened as the PDF it came as."""

    table, entity = "invoices", Invoice

    def all(self) -> list[Invoice]:
        """Return every invoice, newest first."""
        return self._select(order="received_at DESC, id DESC")

    def get(self, invoice_id: int) -> Invoice:
        """Return the invoice ``invoice_id``.

        Raises:
            KeyError: If there's no such invoice.
        """
        found = self.where("id", invoice_id)
        if not found:
            raise KeyError(f"no invoice {invoice_id}")
        return found[0]

    def by_external_id(self, external_id: str) -> Invoice | None:
        """Return the invoice from the email with this ``Message-ID``, if it's been taken in."""
        found = self._select("WHERE external_id = ?", (external_id,))
        return found[0] if found else None

    def data_view(self) -> DocumentView:
        """Open each invoice's PDF."""
        return DocumentView(field="pdf")

    def content_metadata(self, invoice: Invoice) -> ContentMetadata:
        """Declare each invoice's content a PDF, under its attachment's name."""
        return ContentMetadata(filename=invoice.filename, content_type="application/pdf")


@layers.Purchasing
@Repository(IngredientPrice)
class IngredientPrices(_Table):
    """Every price an invoice charged, charted over time by ingredient."""

    table, entity = "ingredient_prices", IngredientPrice

    def all(self) -> list[IngredientPrice]:
        """Return every price, oldest first."""
        return self._select(order="priced_at, id")

    def latest(self) -> dict[str, float]:
        """Return each invoiced ingredient's latest price: ``{code: unit_price}``."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT ingredient, unit_price FROM ingredient_prices AS p WHERE id = ("
                " SELECT id FROM ingredient_prices WHERE ingredient = p.ingredient"
                " ORDER BY priced_at DESC, id DESC LIMIT 1)"
            ).fetchall()
        return dict(rows)

    def data_view(self) -> TimeseriesView:
        """Chart each ingredient's price over time."""
        return TimeseriesView(field="priced_at", fields=("unit_price",), group="name")


@layers.Allergens
@Repository(IngredientAllergen)
class Allergens(_Table):
    """What each ingredient contains or may contain: the sheet's, and what invoices declared."""

    table, entity = "allergens", IngredientAllergen

    def all(self) -> list[IngredientAllergen]:
        """Return every allergen, by ingredient."""
        return self._select(order="ingredient, allergen, id")
