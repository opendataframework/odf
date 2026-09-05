import sqlite3
import threading

from opendataframework import Component, Config, Storage


@Storage
@Component
class SQLite:
    def __init__(self, config: Config) -> None:
        path = config.get("sqlite").get("path", "app.db")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.conn.commit()
