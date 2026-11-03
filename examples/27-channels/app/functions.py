"""The help desk's one action on a ticket: sending its reply.

``ticket_id`` is marked ``Annotated[int, Record(Tickets)]``, so the chat
shows ``send_reply`` as an action on each ticket's card, passing the
ticket's id. ``reply`` is named like ``Ticket.reply``, so the card's form
starts with the ticket's reply, to change before it's sent.
"""

from typing import Annotated

from opendataframework import Function, Notifications, Publisher, Record

from app.repositories import Messages, Tickets

EMAILS = {"Ada": "ada@example.com", "Bob": "bob@example.com"}


@Publisher("tickets.answered")
@Function
def send_reply(
    ticket_id: Annotated[int, Record(Tickets)],
    tickets: Tickets,
    messages: Messages,
    notifications: Notifications,
    reply: str | None = None,
) -> str:
    """Send a ticket's reply to its customer, and close it.

    Args:
        ticket_id: The ticket's id in Tickets.
        tickets: The tickets, injected.
        messages: Where the reply is saved as sent, injected.
        notifications: Bound to this function, injected.
        reply: The reply to send instead of the ticket's.

    Returns:
        The reply sent.

    Raises:
        KeyError: If there's no such ticket.
        ValueError: If it's answered already.
    """
    ticket = tickets.get(ticket_id)
    if ticket.status != "open":
        raise ValueError(f"ticket {ticket_id} is {ticket.status} already")
    if reply is not None:
        ticket.reply = reply.strip()
    messages.send(ticket.customer, EMAILS[ticket.customer], ticket.reply)
    ticket.status = "answered"
    ticket.body = f"{ticket.body}\n\n**Answered.**"
    tickets.save(ticket)
    # A notification about Tickets refreshes the customer's thread in every open UI.
    notifications.publish(
        "tickets.answered",
        {"ticket": ticket.id},
        summary=f"Replied to {ticket.customer}",
        level="success",
        subject=Tickets,
        record=ticket.id,
    )
    return ticket.reply
