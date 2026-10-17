"""A task built on the adopted functions."""

from collections.abc import Callable
from typing import Annotated

from opendataframework import Analytics, Task

from app.reports import store_total
from app.repositories import Orders


@Analytics
@Task
class ReportTotals:
    """Report every store's takings in euros.

    New code can ask for an adopted function the way it asks for a class:
    ``total`` is ``store_total`` with ``orders`` and ``convert`` already
    filled in, so it takes only the store.
    """

    def __init__(
        self,
        orders: Orders,
        total: Annotated[Callable[..., float], store_total],
    ) -> None:
        """Store the orders and the function to total them with.

        Args:
            orders: The orders, to list the stores from.
            total: ``store_total``, taking only the store.
        """
        self.orders = orders
        self.total = total

    def execute(self) -> dict[str, float]:
        """Return each store's total, by store name."""
        stores = sorted({order.store for order in self.orders.all()})
        return {store: self.total(store) for store in stores}
