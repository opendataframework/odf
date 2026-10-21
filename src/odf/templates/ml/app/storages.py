import sqlite3
import threading

from opendataframework import Component, Config, Storage


@Storage
@Component(name="sqlite")
class SQLite:
    def __init__(self, config: Config) -> None:
        path = config.get("component").get("sqlite").get("path", "app.db")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
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
                content TEXT NOT NULL
            );
        """)
        self.conn.commit()
