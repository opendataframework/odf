"""Shared SQLite connection component for the research example."""

import sqlite3
import threading

from opendataframework import Component, Config, Storage


@Storage
@Component
class SQLite:
    """Thread-safe SQLite connection, shared by every component that
    depends on it (here, ``Readings``).

    A ``Component``, not a ``Repository`` — it only owns the connection and
    schema; ``Readings`` composes it rather than talking to sqlite3 directly.
    """

    def __init__(self, config: Config) -> None:
        """Open the connection at the configured path and create tables.

        Args:
            config: Project config; reads ``sqlite.path`` (default ``"app.db"``).
        """
        path = config.get("sqlite").get("path", "app.db")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()  # guards the shared connection across threads
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the ``readings`` table if it doesn't already exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor  TEXT NOT NULL,
                celsius REAL NOT NULL
            )
        """)
        self.conn.commit()
