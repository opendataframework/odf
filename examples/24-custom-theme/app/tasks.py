"""Tasks for the custom-theme example."""

from opendataframework import Task

from app.repositories import Accounts


@Task
class Revenue:
    """Totals monthly recurring revenue per plan.

    Gives the topology a second node, wired to ``Accounts``, so the theme's
    icons and links have something to show.
    """

    def __init__(self, accounts: Accounts) -> None:
        """Wire up the accounts to total.

        Args:
            accounts: The repository to read accounts from.
        """
        self.accounts = accounts

    def execute(self) -> dict[str, int]:
        """Return each plan's total MRR, highest first."""
        totals: dict[str, int] = {}
        for account in self.accounts.all():
            totals[account.plan] = totals.get(account.plan, 0) + account.mrr
        return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))
