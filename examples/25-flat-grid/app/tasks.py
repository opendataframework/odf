"""Sorting task for the flat-grid example."""

from opendataframework import Logger, Task

from app.repositories import Parcels


@Task
class SortParcels:
    """Sorts every unsorted parcel onto its route."""

    def __init__(self, parcels: Parcels, logger: Logger) -> None:
        """Wire up the parcels to sort and the logger.

        Args:
            parcels: The repository to sort.
            logger: Logger to report the sort to.
        """
        self.parcels = parcels
        self.logger = logger

    def execute(self) -> int:
        """Mark every unsorted parcel sorted.

        Returns:
            The number of parcels sorted (``0`` once all of them are).
        """
        count = 0
        for parcel in self.parcels.all():
            if not parcel.sorted:
                parcel.sorted = True
                self.parcels.save(parcel)
                count += 1
        self.logger.info(f"sorted {count} parcel(s)")
        return count
