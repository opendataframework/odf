"""One-off and scheduled imports: catching up on history, and reconciling the POS."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Annotated

from opendataframework import Logger, Notifications, Publisher, Task

from app import layers
from app.clients import Clock, Messenger, Pos
from app.ingest import ingest_message, ingest_sale, sale_lines, sync_sheets
from app.repositories import CafeSales


@layers.Integrations
@Task
class ImportSheets:
    """Imports the shared drive's sheets, without announcing it."""

    def __init__(self, sync: Annotated[Callable[..., dict], sync_sheets]) -> None:
        """Store ``sync_sheets``.

        Args:
            sync: ``sync_sheets``.
        """
        self.sync = sync

    def execute(self) -> dict:
        """Import the sheets; return how many rows each had."""
        return self.sync(announce=False)


@layers.Integrations
@Task
class ImportPosHistory:
    """Takes in every past café order from the POS API, in bulk, without announcing each."""

    def __init__(self, pos: Pos, sales: CafeSales, logger: Logger) -> None:
        """Store the POS client and the sales to fill.

        Args:
            pos: The POS API.
            sales: Where the orders' lines go.
            logger: The task's logger.
        """
        self.pos, self.sales, self.logger = pos, sales, logger

    def execute(self) -> int:
        """Take in every order not taken in yet; return how many orders there are now."""
        before = self.sales.count_orders()
        batch = []
        for order in self.pos.orders():
            batch.extend(sale_lines(order))
            if len(batch) >= 2000:
                self.sales.save_many(batch)
                batch = []
        self.sales.save_many(batch)
        after = self.sales.count_orders()
        self.logger.info(f"took in {after - before} past orders", orders=after - before)
        return after


@layers.Integrations
@Task
class ImportMessengerHistory:
    """Takes in the restaurants' past chat messages, without announcing them."""

    def __init__(
        self,
        messenger: Messenger,
        take_message: Annotated[Callable[..., int | None], ingest_message],
    ) -> None:
        """Store the messenger client and ``ingest_message``.

        Args:
            messenger: The messenger API.
            take_message: ``ingest_message``.
        """
        self.messenger, self.take_message = messenger, take_message

    def execute(self) -> int:
        """Take in every message restaurants sent; return how many were new."""
        new = 0
        for m in self.messenger.history():
            if m["direction"] != "in":
                continue
            sent = datetime.fromisoformat(m["sent_at"]).timestamp()
            if self.take_message(
                "messenger", m["id"], m["contact"], m["text"], sent, announce=False
            ):
                new += 1
        return new


@layers.Integrations
@Publisher("pos.reconciled")
@Task
class ReconcilePos:
    """Catches café orders whose webhook never arrived, by reading the POS's last two days.

    Webhooks get lost: the bakery's server restarts, the network blips, the
    POS gives up retrying. Reading the orders back each night and taking in
    any that are missing keeps the sales complete.
    """

    def __init__(
        self,
        pos: Pos,
        clock: Clock,
        take_sale: Annotated[Callable[..., bool], ingest_sale],
        notifications: Notifications,
    ) -> None:
        """Store what the reconciliation reads and writes.

        Args:
            pos: The POS API.
            clock: The demo clock, for "the last two days".
            take_sale: ``ingest_sale``.
            notifications: Bound to this task.
        """
        self.pos, self.clock, self.take_sale = pos, clock, take_sale
        self.notifications = notifications

    def execute(self) -> int:
        """Take in the missing orders; return how many there were."""
        since = (self.clock.now() - timedelta(days=2)).isoformat(timespec="seconds")
        recovered = sum(
            1 for order in self.pos.orders(created_after=since) if self.take_sale(order)
        )
        if recovered:
            self.notifications.publish(
                "pos.reconciled",
                {"recovered": recovered},
                summary=f"POS reconciliation took in {recovered} sale(s) whose webhook never came",
                level="warning",
                subject=CafeSales,
            )
        return recovered
