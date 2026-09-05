from app.entities import Ticket
from app.repositories import Tickets

# Deliberately builds Tickets directly rather than going through Project/
# Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_tickets_save_assigns_incrementing_ids():
    tickets = Tickets()
    seeded = len(tickets.all())

    tickets.save(Ticket(id=None, subject="Login page 500s", status="open"))
    tickets.save(Ticket(id=None, subject="Typo in footer", status="closed"))

    assert [t.id for t in tickets.all()][seeded:] == [seeded + 1, seeded + 2]


def test_tickets_save_updates_existing_record():
    tickets = Tickets()
    before = len(tickets.all())
    tickets.save(Ticket(id=None, subject="Login page 500s", status="open"))
    saved = tickets.all()[-1]

    saved.status = "closed"
    tickets.save(saved)

    assert len(tickets.all()) == before + 1
    assert tickets.all()[-1].status == "closed"
