"""In-memory repository backing the custom-theme example."""

from opendataframework import Repository, Storage

from app.entities import Account

# (name, plan, mrr): a few accounts to look at without hand-typing records
# through the UI first.
_SEED_ACCOUNTS: tuple[tuple[str, str, int], ...] = (
    ("Northwind Labs", "Enterprise", 4800),
    ("Brightline", "Pro", 490),
    ("Kestrel Analytics", "Enterprise", 3200),
    ("Fieldnote", "Free", 0),
    ("Parallel Studio", "Pro", 290),
)


@Storage
@Repository(Account)
class Accounts:
    """In-memory ``Account`` repository, pre-seeded with ``_SEED_ACCOUNTS``.

    Implements no ``data_view()``. The concept this example isolates is the
    project's own UI theme (see ``../themes/mono/`` and this project's
    ``config.toml``), so it renders as the same plain default table as
    ../01-table-view, in the theme's look.
    """

    def __init__(self) -> None:
        """Seed the in-memory account list from ``_SEED_ACCOUNTS``."""
        self._accounts: list[Account] = [
            Account(id=account_id, name=name, plan=plan, mrr=mrr)
            for account_id, (name, plan, mrr) in enumerate(_SEED_ACCOUNTS, start=1)
        ]
        self._next_id = len(self._accounts) + 1

    def all(self) -> list[Account]:
        """Return every account."""
        return list(self._accounts)

    def save(self, account: Account) -> None:
        """Create or update an account.

        Args:
            account: The account to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if account.id is None:
            account.id = self._next_id
            self._next_id += 1
            self._accounts.append(account)
            return
        for i, existing in enumerate(self._accounts):
            if existing.id == account.id:
                self._accounts[i] = account
                return

    def delete(self, account_id: int) -> None:
        """Delete the account matching ``account_id``, if one exists.

        Args:
            account_id: The ``id`` of the account to remove.
        """
        self._accounts = [a for a in self._accounts if a.id != account_id]
