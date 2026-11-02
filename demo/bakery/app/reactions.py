"""What the bakery does on its own when something arrives: reactions to notifications.

Each reaction is a ``@Subscriber``. The ``Context`` subscribes it once it
starts and unsubscribes it before it stops, and each delivery is a traced
call whose ``cause`` is the notification it reacts to, so a trace runs from
the webhook that brought a message in to the draft it became.
"""

from opendataframework import Component, Logger, Notification, Subscriber

from app.agents import OrderDesk


@Subscriber("messages.received", deliver="background")
@Component
class Drafting:
    """Drafts the order change a restaurant's message asks for, as soon as it arrives.

    Runs in the background, on a worker of its own, so the model a draft may
    ask doesn't hold up the webhook or the mailbox that took the message in.
    Only a restaurant on the restaurants sheet gets a draft this way;
    anyone else's message waits in Messages for a person, who can still run
    **order-desk** on it.
    """

    def __init__(self, order_desk: OrderDesk, logger: Logger) -> None:
        """Store the agent that drafts.

        Args:
            order_desk: Drafts the change and its reply.
            logger: This component's log.
        """
        self.order_desk = order_desk
        self.logger = logger

    def on_notification(self, notification: Notification) -> None:
        """Draft for the message ``notification`` announces, if a restaurant sent it."""
        restaurant = notification.payload.get("restaurant")
        if restaurant is None:
            self.logger.info(
                "not from a restaurant: left for a person", message=notification.record
            )
            return
        self.order_desk.invoke(message_id=notification.record)
