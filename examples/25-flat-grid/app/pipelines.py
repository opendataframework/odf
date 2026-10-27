"""Nightly pipeline for the flat-grid example."""

from opendataframework import Pipeline

from app.tasks import SortParcels


@Pipeline
class NightlyRun:
    """The depot's nightly run: sorts the day's parcels."""

    def __init__(self, sort: SortParcels) -> None:
        """Wire up the task to run.

        Args:
            sort: Sorts the unsorted parcels.
        """
        self.sort = sort

    def execute(self) -> None:
        """Run ``SortParcels``."""
        print(f"Sorted {self.sort.execute()} parcel(s).")
