import csv
import json
from pathlib import Path

from opendataframework import Logger, Task

from app.entities import Item
from app.repositories import Items


@Task
class RunExperiment:
    """Seeds ``data/items.csv`` (read-only source data, never edited in place) into
    the ``Items`` repository if it isn't already loaded, computes summary
    statistics, and writes them to ``results/summary.json`` — the ``data`` /
    ``results`` split from "Good Enough Practices in Scientific Computing"
    (Wilson et al., 2017): raw input and generated output never share a directory.
    """

    def __init__(self, items: Items, logger: Logger) -> None:
        self.items = items
        self.logger = logger

    def execute(self) -> dict:
        if not self.items.all():
            with open("data/items.csv", newline="") as f:
                for row in csv.DictReader(f):
                    self.items.save(Item(id=None, name=row["name"], quantity=int(row["quantity"])))

        all_items = self.items.all()
        summary = {
            "item_count": len(all_items),
            "total_quantity": sum(item.quantity for item in all_items),
        }

        path = Path("results/summary.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"wrote experiment results {summary} to {path}")
        return summary
