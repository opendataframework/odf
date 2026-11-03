"""In-memory repositories for the channels example, both in the ``support`` channel.

``Messages`` declares a ``conversation()`` with a ``direction``: its records
are messages, one thread per customer, on the side they were sent from.
``Tickets`` declares one in the same channel with no ``direction``: its
records are cards in their customer's thread, each with the functions that
take one (``app.functions.send_reply``) as its actions.
"""

import time
from datetime import UTC, datetime

from opendataframework import ContentMetadata, Conversation, DocumentView, Repository, Storage

from app.entities import Message, Ticket

# Each customer's messages, minutes ago: (minutes, customer, direction, email, text).
_MESSAGES = (
    (50, "Ada", "in", "ada@example.com", "My order #1042 hasn't arrived, it's been a week."),
    (40, "Bob", "in", "bob@example.com", "The jacket I got is a size too small."),
    (35, "Bob", "out", "bob@example.com", "Sorry about that! Which size would you like?"),
    (20, "Bob", "in", "bob@example.com", "A large, please."),
)


def _ago(minutes: int) -> float:
    return time.time() - minutes * 60


@Storage
@Repository(Message)
class Messages:
    """Every message to and from customers, in-memory, pre-seeded."""

    def __init__(self) -> None:
        """Start with a few customers' messages."""
        self._messages = [
            Message(i, _ago(minutes), customer, direction, sender, text)
            for i, (minutes, customer, direction, sender, text) in enumerate(_MESSAGES, start=1)
        ]

    def all(self) -> list[Message]:
        """Return every message, oldest first."""
        return list(self._messages)

    def send(self, customer: str, sender: str, text: str) -> Message:
        """Save a message the help desk sent ``customer``, now."""
        message = Message(len(self._messages) + 1, time.time(), customer, "out", sender, text)
        self._messages.append(message)
        return message

    def conversation(self) -> Conversation:
        """One thread per customer, both sides, in the ``support`` channel."""
        return Conversation(
            channel="support",
            thread="customer",
            time="sent_at",
            text="text",
            direction="direction",
            sender="sender",
        )


@Storage
@Repository(Ticket)
class Tickets:
    """The help desk's tickets, in-memory, one open for Ada's late order."""

    def __init__(self) -> None:
        """Start with a ticket answering Ada."""
        opened = datetime.fromtimestamp(_ago(45), UTC).isoformat()
        self._tickets = {
            1: Ticket(
                1,
                opened,
                "Ada",
                "### Late order #1042\n\nThe courier lost it. Send a new one today, "
                "by express, and say so.",
                "So sorry, Ada: the courier lost it. A new one goes out by express today.",
            )
        }

    def all(self) -> list[Ticket]:
        """Return every ticket, oldest first."""
        return list(self._tickets.values())

    def get(self, ticket_id: int) -> Ticket:
        """Return the ticket ``ticket_id``.

        Raises:
            KeyError: If there's no such ticket.
        """
        return self._tickets[ticket_id]

    def save(self, ticket: Ticket) -> None:
        """Create or update a ticket."""
        self._tickets[ticket.id] = ticket

    def conversation(self) -> Conversation:
        """Each ticket as a card in its customer's thread: no ``direction``."""
        return Conversation(channel="support", thread="customer", time="opened_at", text="body")

    def data_view(self) -> DocumentView:
        """Open each ticket's body as a document."""
        return DocumentView(field="body")

    def content_metadata(self, ticket: Ticket) -> ContentMetadata:
        """Declare each body Markdown, so the UI renders it, in its card too."""
        return ContentMetadata(filename=f"ticket-{ticket.id}.md", content_type="text/markdown")
