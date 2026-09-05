from opendataframework import Pipeline

from app.tasks import ExportItemsSummary, SeedItems


@Pipeline
class SetupPipeline:
    def __init__(self, seed: SeedItems, export: ExportItemsSummary) -> None:
        self.seed = seed
        self.export = export

    def execute(self) -> None:
        count = self.seed.execute()
        print(f"Seeded {count} item(s).")
        path = self.export.execute()
        print(f"Exported summary to {path}.")
