"""Experiment task for the research example."""

import csv
import json
from pathlib import Path

from opendataframework import Logger, Task

from app.entities import Reading
from app.repositories import Readings


@Task
class RunExperiment:
    """Loads `data/readings.csv` — the raw, read-only source data — into the
    `Readings` repository if it isn't already loaded, computes summary
    statistics, and writes them to `results/summary.json`: the `data` /
    `results` split from "Good Enough Practices in Scientific Computing"
    (Wilson et al., 2017) — raw input and generated output never share a
    directory. Unlike 04-data-engineering's SeedItems/ExportItemsSummary
    split, loading and computing are one Task here — a single, rerunnable
    step, closer to how an experiment script is actually run by hand.
    """

    def __init__(self, readings: Readings, logger: Logger) -> None:
        """Wire up the readings sink and logger.

        Args:
            readings: The repository to load into and aggregate.
            logger: Logger to report the write to.
        """
        self.readings = readings
        self.logger = logger

    def execute(self) -> dict:
        """Load (if needed), summarize, and persist.

        Returns:
            The summary dict written to ``results/summary.json``.
        """
        if not self.readings.all():
            with open("data/readings.csv", newline="") as f:
                for row in csv.DictReader(f):
                    self.readings.save(
                        Reading(id=None, sensor=row["sensor"], celsius=float(row["celsius"]))
                    )

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

        path = Path("results/summary.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"wrote experiment results {summary} to {path}")
        return summary
