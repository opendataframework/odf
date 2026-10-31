"""The kitchen, reacting to the tickets the counter sends it."""

from opendataframework import Component, Notification, Notifications


@Component
class Kitchen:
    """Keeps the tickets ``take_order`` publishes as ``kitchen.ticket``.

    Those notifications have no ``summary``: they're for this component, not
    for people, so the UI doesn't show them. The kitchen doesn't know who
    sends them, only the topic. Its **Details** show what it has received.
    """

    def __init__(self, notifications: Notifications) -> None:
        """Subscribe to the counter's tickets.

        Args:
            notifications: Bound to this component's key.
        """
        self.tickets: list[dict] = []
        self._unsubscribe = notifications.subscribe(self.receive, topic="kitchen.ticket")

    def receive(self, notification: Notification) -> None:
        """Keep one ticket. Runs in the publisher's thread, so it stays quick."""
        self.tickets.append(dict(notification.payload))

    def details(self) -> dict[str, str]:
        """Return how many tickets came in, and the latest."""
        latest = self.tickets[-1] if self.tickets else None
        return {
            "tickets": str(len(self.tickets)),
            "latest": f"table {latest['table']}: {latest['item']}" if latest else "none yet",
        }

    def on_stop(self) -> None:
        """Stop receiving tickets when the project stops."""
        self._unsubscribe()
