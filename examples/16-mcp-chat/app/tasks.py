"""Analytics task for the MCP + chat example."""

from opendataframework import Analytics, Task

from app.repositories import Tickets


@Analytics
@Task
class TriageTickets:
    """Counts open vs. closed tickets — the kind of one-off task an MCP
    client (or a chat model calling the same tool) triggers on demand via
    execute_task, rather than something scheduled or run from the UI."""

    def __init__(self, tickets: Tickets) -> None:
        """Store the tickets source to triage.

        Args:
            tickets: The repository to count open/closed tickets from.
        """
        self.tickets = tickets

    def execute(self) -> dict:
        """Count open vs. closed tickets.

        Returns:
            A dict with ``total``, ``open``, and ``closed`` counts.
        """
        all_tickets = self.tickets.all()
        open_count = sum(1 for t in all_tickets if t.status == "open")
        summary = {
            "total": len(all_tickets),
            "open": open_count,
            "closed": len(all_tickets) - open_count,
        }
        print(f"TriageTickets.execute -> {summary}")
        return summary
