from app.entities import Ticket
from app.repositories import Tickets
from app.tasks import TriageTickets

# Deliberately builds Tickets/TriageTickets directly rather than going
# through Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_triage_counts_open_and_closed_tickets():
    tickets = Tickets()
    baseline = TriageTickets(tickets).execute()
    tickets.save(Ticket(id=None, subject="Login page 500s", status="open"))
    tickets.save(Ticket(id=None, subject="Typo in footer", status="closed"))
    tickets.save(Ticket(id=None, subject="Slow dashboard load", status="open"))

    summary = TriageTickets(tickets).execute()

    assert summary == {
        "total": baseline["total"] + 3,
        "open": baseline["open"] + 2,
        "closed": baseline["closed"] + 1,
    }


def test_triage_handles_no_tickets():
    class _EmptyTickets:
        def all(self):
            return []

    summary = TriageTickets(_EmptyTickets()).execute()

    assert summary == {"total": 0, "open": 0, "closed": 0}
