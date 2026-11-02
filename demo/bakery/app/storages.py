"""The bakery's own database: one SQLite file every repository shares."""

import sqlite3
import threading
from pathlib import Path

from opendataframework import Component, Config, Storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
    cafe_price REAL NOT NULL, wholesale_price REAL
);
CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, phone TEXT NOT NULL,
    email TEXT NOT NULL, address TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
    kitchen_opens TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS standing_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, restaurant TEXT NOT NULL, weekday TEXT NOT NULL,
    sku TEXT NOT NULL, quantity INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, restaurant TEXT NOT NULL, sku TEXT NOT NULL,
    price REAL NOT NULL, valid_until TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, received_at REAL NOT NULL, channel TEXT NOT NULL,
    sender TEXT NOT NULL, restaurant TEXT, subject TEXT, text TEXT NOT NULL,
    external_id TEXT UNIQUE NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cafe_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sold_at REAL NOT NULL, order_id TEXT NOT NULL,
    sku TEXT NOT NULL, product TEXT NOT NULL, quantity INTEGER NOT NULL, revenue REAL NOT NULL,
    UNIQUE (order_id, sku)
);
CREATE INDEX IF NOT EXISTS cafe_sales_order ON cafe_sales (order_id);
CREATE TABLE IF NOT EXISTS mailbox_seen (uidl TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS order_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, restaurant TEXT NOT NULL, sku TEXT NOT NULL,
    date TEXT NOT NULL, mode TEXT NOT NULL, quantity INTEGER NOT NULL, message INTEGER,
    draft INTEGER
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL, kind TEXT NOT NULL,
    status TEXT NOT NULL, title TEXT NOT NULL, date TEXT NOT NULL, restaurant TEXT,
    message INTEGER, changes TEXT NOT NULL, reply TEXT NOT NULL, author TEXT NOT NULL,
    note TEXT NOT NULL, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, sku TEXT NOT NULL,
    product TEXT NOT NULL, baseline REAL NOT NULL, weather REAL NOT NULL, holiday REAL NOT NULL,
    quantity INTEGER NOT NULL, rain_mm REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS bake_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, sku TEXT NOT NULL,
    product TEXT NOT NULL, wholesale INTEGER NOT NULL, cafe INTEGER NOT NULL,
    buffer INTEGER NOT NULL, total INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS leftovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, sku TEXT NOT NULL,
    product TEXT NOT NULL, baked INTEGER NOT NULL, sold INTEGER NOT NULL, unsold INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ingredients (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, unit TEXT NOT NULL, supplier TEXT NOT NULL,
    invoice_name TEXT NOT NULL, price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT NOT NULL, ingredient TEXT NOT NULL,
    quantity REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT, received_at REAL NOT NULL, supplier TEXT NOT NULL,
    sender TEXT NOT NULL, subject TEXT NOT NULL, number TEXT, date TEXT, total REAL,
    status TEXT NOT NULL, external_id TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
    pdf BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS ingredient_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT, priced_at REAL NOT NULL, ingredient TEXT NOT NULL,
    name TEXT NOT NULL, unit TEXT NOT NULL, unit_price REAL NOT NULL, supplier TEXT NOT NULL,
    invoice INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ingredient_prices_latest ON ingredient_prices (ingredient, priced_at);
CREATE TABLE IF NOT EXISTS allergens (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ingredient TEXT NOT NULL, allergen TEXT NOT NULL,
    kind TEXT NOT NULL, source TEXT NOT NULL, since REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS delivery_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, stop INTEGER NOT NULL,
    restaurant TEXT NOT NULL, address TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
    arrive_by TEXT NOT NULL, eta TEXT NOT NULL, load TEXT NOT NULL, items INTEGER NOT NULL
);
"""


@Storage
@Component(name="sqlite")
class SQLite:
    """One thread-safe SQLite connection, shared by every repository.

    A ``Component``, not a ``Repository``: it owns the connection and the
    schema, and each repository composes it.
    """

    def __init__(self, config: Config) -> None:
        """Open the database at ``[component.sqlite] path`` and create the tables.

        Args:
            config: Project config; reads ``component.sqlite.path``
                (default ``"data/bakery.db"``).
        """
        path = Path(config.get("component").get("sqlite").get("path", "data/bakery.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()  # guards the shared connection across threads
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def on_stop(self) -> None:
        """Close the connection when the project stops."""
        with self.lock:
            self.conn.close()
