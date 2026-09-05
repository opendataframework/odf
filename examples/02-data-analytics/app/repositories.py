"""SQLite-backed repository for the data-analytics example."""

from opendataframework import Repository, Storage

from app.entities import Reading
from app.storages import SQLite


@Storage
@Repository(Reading)
class Readings:
    """SQLite-backed ``Reading`` repository.

    Persists through the shared ``SQLite`` component rather than talking to
    sqlite3 directly (see ../06-location-view for an in-memory repository).
    """

    def __init__(self, sqlite: SQLite) -> None:
        """Store the shared ``SQLite`` component to persist through.

        Args:
            sqlite: The shared connection component.
        """
        self.db = sqlite

    def all(self) -> list[Reading]:
        """Return every reading."""
        with self.db.lock:
            rows = self.db.conn.execute("SELECT id, sensor, celsius FROM readings").fetchall()
        return [Reading(id=r[0], sensor=r[1], celsius=r[2]) for r in rows]

    def save(self, reading: Reading) -> None:
        """Insert a new reading.

        Args:
            reading: The reading to persist. ``id`` is ignored on input and
                set to the row's autoincremented primary key afterward —
                unlike ../06-location-view's ``Stores.save()``, this always
                inserts; there's no update-by-id path.
        """
        with self.db.lock:
            cursor = self.db.conn.execute(
                "INSERT INTO readings (sensor, celsius) VALUES (?, ?)",
                (reading.sensor, reading.celsius),
            )
            reading.id = cursor.lastrowid
            self.db.conn.commit()
