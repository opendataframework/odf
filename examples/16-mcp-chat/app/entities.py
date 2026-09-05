"""Entities for the MCP + chat example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Ticket:
    """A support ticket, triaged by the ``TriageTickets`` task.

    Attributes:
        id: Primary key, ``None`` until ``Tickets.save()`` assigns one.
        subject: A short summary of the ticket.
        status: The ticket's status, e.g. ``"open"`` or ``"closed"``.
    """

    id: int | None
    subject: str
    status: str
