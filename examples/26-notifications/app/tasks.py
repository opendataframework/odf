"""Restocking the pantry."""

from opendataframework import Notifications, Publisher, Task

from app.repositories import Pantry


@Publisher("pantry.restocked")
@Task
class Restock:
    """Puts every ingredient back to its starting stock, and says so."""

    def __init__(self, pantry: Pantry, notifications: Notifications) -> None:
        """Store the pantry to restock.

        Args:
            pantry: The ingredients to restock.
            notifications: Bound to this task's key.
        """
        self.pantry = pantry
        self.notifications = notifications

    def execute(self) -> None:
        """Restock the pantry and publish ``pantry.restocked``."""
        self.pantry.restock()
        self.notifications.publish(
            "pantry.restocked",
            {s.name: s.stock for s in self.pantry.all()},
            summary="Pantry restocked",
            level="success",
            subject=Pantry,
        )
