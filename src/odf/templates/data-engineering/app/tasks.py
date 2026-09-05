import csv
import json
from pathlib import Path

from opendataframework import Logger, Task

from app.entities import Item
from app.repositories import Items


@Task
class SeedItems:
    """Ingests ``data/raw/items.csv`` into the ``Items`` repository.

    Dedup guard (skip if items already exist) so re-running the pipeline
    against a persisted ``app.db`` doesn't double-ingest the same rows.
    """

    def __init__(self, items: Items, logger: Logger) -> None:
        self.items = items
        self.logger = logger

    def execute(self) -> int:
        if self.items.all():
            self.logger.debug("skipped already-seeded items")
            return 0
        count = 0
        with open("data/raw/items.csv", newline="") as f:
            for row in csv.DictReader(f):
                self.items.save(Item(id=None, name=row["name"], quantity=int(row["quantity"])))
                count += 1
        self.logger.info(f"seeded {count} item(s) from data/raw/items.csv")
        return count


@Task
class ExportItemsSummary:
    """Aggregates ``Items`` and writes the result to ``data/processed/`` —
    the "processed" half of the raw-to-processed pipeline ``SeedItems`` starts.
    """

    def __init__(self, items: Items, logger: Logger) -> None:
        self.items = items
        self.logger = logger

    def execute(self) -> str:
        all_items = self.items.all()
        summary = {
            "item_count": len(all_items),
            "total_quantity": sum(item.quantity for item in all_items),
        }

        path = Path("data/processed/items_summary.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"wrote summary {summary} to {path}")
        return str(path)
