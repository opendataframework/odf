"""The kitchen, reacting to the tickets the counter sends it."""

from opendataframework import Component, Notification, Subscriber


@Subscriber("kitchen.ticket")
@Component
class Kitchen:
    """Keeps the tickets ``take_order`` publishes as ``kitchen.ticket``.

    Those notifications have no ``summary``: they're for this component, not
    for people, so the UI doesn't show them. The kitchen doesn't know who
    sends them, only the topic: the ``Context`` subscribes it once it starts
    and unsubscribes it before it stops. Its **Details** show what it has
    received.
    """

    def __init__(self) -> None:
        """Start with no tickets."""
        self.tickets: list[dict] = []

    def on_notification(self, notification: Notification) -> None:
        """Keep one ticket. Runs in the publisher's thread, so it stays quick."""
        self.tickets.append(dict(notification.payload))

    def details(self) -> dict[str, str]:
        """Return how many tickets came in, and the latest."""
        latest = self.tickets[-1] if self.tickets else None
        return {
            "tickets": str(len(self.tickets)),
            "latest": f"table {latest['table']}: {latest['item']}" if latest else "none yet",
        }
