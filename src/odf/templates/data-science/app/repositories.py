from opendataframework import Repository, Storage

from app.entities import Item
from app.storages import SQLite


@Storage
@Repository(Item)
class Items:
    def __init__(self, sqlite: SQLite) -> None:
        self.db = sqlite

    def all(self) -> list[Item]:
        with self.db.lock:
            rows = self.db.conn.execute("SELECT id, name, quantity FROM items").fetchall()
        return [Item(id=r[0], name=r[1], quantity=r[2]) for r in rows]

    def get(self, item_id: int) -> Item | None:
        with self.db.lock:
            row = self.db.conn.execute(
                "SELECT id, name, quantity FROM items WHERE id = ?", (item_id,)
            ).fetchone()
        return Item(id=row[0], name=row[1], quantity=row[2]) if row else None

    def save(self, item: Item) -> None:
        with self.db.lock:
            if item.id is None:
                cursor = self.db.conn.execute(
                    "INSERT INTO items (name, quantity) VALUES (?, ?)",
                    (item.name, item.quantity),
                )
                item.id = cursor.lastrowid
            else:
                self.db.conn.execute(
                    "UPDATE items SET name = ?, quantity = ? WHERE id = ?",
                    (item.name, item.quantity, item.id),
                )
            self.db.conn.commit()

    def delete(self, item_id: int) -> None:
        with self.db.lock:
            self.db.conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            self.db.conn.commit()
