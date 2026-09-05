"""Analytics task for the data-analytics example."""

import json
from pathlib import Path

from opendataframework import Analytics, Config, Logger, Task

from app.repositories import Readings


@Analytics
@Task
class SummarizeReadings:
    """Aggregates the readings table into a small report — a starting point
    for turning repository data into something a stakeholder can read,
    written to the `reports/` folder rather than back into the database.
    """

    def __init__(self, readings: Readings, config: Config, logger: Logger) -> None:
        """Wire up the readings source, report destination, and logger.

        Args:
            readings: The repository to aggregate.
            config: Project config; reads ``summarize-readings.report-path``
                (default ``"reports/summary.json"``).
            logger: Logger to report the write to.
        """
        self.readings = readings
        self.report_path = config.get("summarize-readings").get(
            "report-path", "reports/summary.json"
        )
        self.logger = logger

    def execute(self) -> dict:
        """Aggregate all readings and write the result to ``report_path``.

        Returns:
            The summary dict, keyed by reading count and per-sensor average.
        """
        all_readings = self.readings.all()
        by_sensor: dict[str, list[float]] = {}
        for reading in all_readings:
            by_sensor.setdefault(reading.sensor, []).append(reading.celsius)

        summary = {
            "reading_count": len(all_readings),
            "average_celsius_by_sensor": {
                sensor: round(sum(values) / len(values), 2) for sensor, values in by_sensor.items()
            },
        }

        path = Path(self.report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"wrote summary {summary} to {path}")
        return summary
