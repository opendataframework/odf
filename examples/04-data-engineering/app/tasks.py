"""ETL tasks for the data-engineering example."""

import csv
import json
from pathlib import Path

from opendataframework import Logger, Task

from app.entities import Reading
from app.repositories import Readings


@Task
class SeedReadings:
    """Ingests `data/raw/readings.csv` into the `Readings` repository.

    Dedup guard (skip if readings already exist) so re-running the pipeline
    against a persisted `app.db` doesn't double-ingest the same rows.
    """

    def __init__(self, readings: Readings, logger: Logger) -> None:
        """Wire up the readings sink and logger.

        Args:
            readings: The repository to seed.
            logger: Logger to report ingestion/dedup to.
        """
        self.readings = readings
        self.logger = logger

    def execute(self) -> int:
        """Seed readings from CSV, unless the repository is already populated.

        Returns:
            The number of readings inserted (``0`` if skipped as a dedup).
        """
        if self.readings.all():
            self.logger.debug("skipped already-seeded readings")
            return 0
        count = 0
        with open("data/raw/readings.csv", newline="") as f:
            for row in csv.DictReader(f):
                self.readings.save(
                    Reading(id=None, sensor=row["sensor"], celsius=float(row["celsius"]))
                )
                count += 1
        self.logger.info(f"seeded {count} reading(s) from data/raw/readings.csv")
        return count


@Task
class ExportReadingsSummary:
    """Aggregates `Readings` and writes the result to `data/processed/` —
    the "processed" half of the raw-to-processed pipeline `SeedReadings` starts.
    """

    def __init__(self, readings: Readings, logger: Logger) -> None:
        """Wire up the readings source and logger.

        Args:
            readings: The repository to aggregate.
            logger: Logger to report the write to.
        """
        self.readings = readings
        self.logger = logger

    def execute(self) -> str:
        """Aggregate all readings and write the summary to ``data/processed/``.

        Returns:
            The path the summary JSON was written to.
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

        path = Path("data/processed/readings_summary.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"wrote summary {summary} to {path}")
        return str(path)
