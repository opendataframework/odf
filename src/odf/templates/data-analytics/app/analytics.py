import json
from pathlib import Path

from opendataframework import Analytics, Config, Logger, Task

from app.repositories import Items


@Analytics
@Task
class SummarizeItems:
    """Aggregates the items table into a small report — a starting point for
    turning repository data into something a stakeholder can read.
    """

    def __init__(self, items: Items, config: Config, logger: Logger) -> None:
        self.items = items
        self.report_path = config.get("summarize-items").get("report-path", "reports/summary.json")
        self.logger = logger

    def execute(self) -> dict:
        all_items = self.items.all()
        summary = {
            "item_count": len(all_items),
            "total_quantity": sum(item.quantity for item in all_items),
        }

        path = Path(self.report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"wrote summary {summary} to {path}")
        return summary
