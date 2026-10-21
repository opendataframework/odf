"""Shared SQLite connection component for the ml example."""

import sqlite3
import threading

from opendataframework import Component, Config, Storage


@Storage
@Component(name="sqlite")
class SQLite:
    """Thread-safe SQLite connection, shared by the four repositories.

    A ``Component``, not a ``Repository``: it only owns the connection and
    schema, and each repository composes it.
    """

    def __init__(self, config: Config) -> None:
        """Open the connection at the configured path and create tables.

        Args:
            config: Project config; reads ``component.sqlite.path`` (default ``"app.db"``).
        """
        path = config.get("component").get("sqlite").get("path", "app.db")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()  # guards the shared connection across threads
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the ``runs``/``params``/``metrics``/``artifacts`` tables if missing."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                status      TEXT NOT NULL,
                started_at  REAL NOT NULL,
                finished_at REAL
            );
            CREATE TABLE IF NOT EXISTS params (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                key    TEXT NOT NULL,
                value  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id   INTEGER NOT NULL,
                step     INTEGER NOT NULL,
                loss     REAL NOT NULL,
                accuracy REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id  INTEGER NOT NULL,
                name    TEXT NOT NULL,
                kind    TEXT NOT NULL,
                content BLOB NOT NULL
            );
        """)
        self.conn.commit()
