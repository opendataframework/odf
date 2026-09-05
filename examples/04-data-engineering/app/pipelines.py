"""ETL pipeline for the data-engineering example."""

from opendataframework import Pipeline

from app.tasks import ExportReadingsSummary, SeedReadings


@Pipeline
class SetupPipeline:
    """Coordinates the raw-to-processed ETL flow: seed, then export.

    A ``Pipeline`` performs no work itself — it only sequences the two
    ``Task``s it depends on and reports what each one did.
    """

    def __init__(self, seed: SeedReadings, export: ExportReadingsSummary) -> None:
        """Wire up the two tasks to sequence.

        Args:
            seed: Ingests raw CSV data into the repository.
            export: Aggregates the repository and writes the summary.
        """
        self.seed = seed
        self.export = export

    def execute(self) -> None:
        """Run ``SeedReadings`` then ``ExportReadingsSummary``, in order."""
        count = self.seed.execute()
        print(f"Seeded {count} reading(s).")
        path = self.export.execute()
        print(f"Exported summary to {path}.")
