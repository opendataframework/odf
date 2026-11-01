"""Onboarding: connecting the bakery's tools for the first time and catching up on their history."""

from opendataframework import Notifications, Pipeline

from app.repositories import CafeSales
from app.tasks import ImportMessengerHistory, ImportPosHistory, ImportSheets


@Pipeline
class Onboard:
    """Imports the sheets, the POS's order history and the messenger's chats, in that order.

    The mailbox catches up on its own, on its first check. ``Scheduler`` runs
    this once, on a bakery with no sales yet; **Execute** runs it again, and
    only what's new is taken in.
    """

    def __init__(
        self,
        sheets: ImportSheets,
        pos_history: ImportPosHistory,
        messenger_history: ImportMessengerHistory,
        notifications: Notifications,
    ) -> None:
        """Store the steps.

        Args:
            sheets: Imports the shared drive's sheets.
            pos_history: Takes in the POS's past orders.
            messenger_history: Takes in the restaurants' past chats.
            notifications: Bound to this pipeline.
        """
        self.sheets, self.pos_history, self.messenger_history = (
            sheets,
            pos_history,
            messenger_history,
        )
        self.notifications = notifications

    def execute(self) -> None:
        """Run the steps, then announce what was taken in."""
        counts = self.sheets.execute()
        orders = self.pos_history.execute()
        chats = self.messenger_history.execute()
        self.notifications.publish(
            "bakery.onboarded",
            {**counts, "orders": orders, "messages": chats},
            summary=(
                f"Onboarded: {orders} café orders, {chats} chat messages, "
                f"{counts['restaurants']} restaurants, {counts['products']} products"
            ),
            level="success",
            subject=CafeSales,
        )
