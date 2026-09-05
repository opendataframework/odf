"""In-memory repository backing the MCP + chat example."""

from opendataframework import Repository, Storage

from app.entities import Ticket

# (subject, status) — so there are real tickets for TriageTickets to
# triage and the MCP tools/chat model to act on without hand-triggering a
# save() first.
_SEED_TICKETS: tuple[tuple[str, str], ...] = (
    ("Login page 500s", "open"),
    ("Typo in footer", "closed"),
    ("Slow dashboard load", "open"),
)


@Storage
@Repository(Ticket)
class Tickets:
    """In-memory ``Ticket`` repository, pre-seeded with ``_SEED_TICKETS``
    and exposed over MCP for a client (or chat model) to inspect and
    update through ``TriageTickets``.
    """

    def __init__(self) -> None:
        """Seed the in-memory ticket store from ``_SEED_TICKETS``."""
        self._records: dict[int, Ticket] = {
            ticket_id: Ticket(id=ticket_id, subject=subject, status=status)
            for ticket_id, (subject, status) in enumerate(_SEED_TICKETS, start=1)
        }
        self._next_id = len(self._records) + 1

    def all(self) -> list[Ticket]:
        """Return every ticket."""
        return list(self._records.values())

    def save(self, ticket: Ticket) -> None:
        """Create or update a ticket.

        Args:
            ticket: The ticket to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if ticket.id is None:
            ticket.id = self._next_id
            self._next_id += 1
        self._records[ticket.id] = ticket
