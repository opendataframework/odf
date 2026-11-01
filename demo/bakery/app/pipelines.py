"""The bakery's runs: onboarding once, then each day's night run and closing the café."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Annotated

from opendataframework import Notifications, Pipeline, Publisher

from app.agents import Specials
from app.clients import Clock
from app.planning import bake_sheet, count_leftovers, forecast, label, plan_deliveries
from app.repositories import BakeSheets, CafeSales
from app.tasks import ImportMessengerHistory, ImportPosHistory, ImportSheets


@Publisher("bakery.onboarded")
@Pipeline
class Onboard:
    """Imports the sheets, the POS's order history and the messenger's chats, in that order.

    The mailbox catches up on its own, on its first check. ``Scheduler`` runs
    this once, on a bakery with no sales yet; **Execute** runs it again, and
    only what's new is taken in.
    """

    def __init__(
        self,
        sheets: ImportSheets,
        pos_history: ImportPosHistory,
        messenger_history: ImportMessengerHistory,
        notifications: Notifications,
    ) -> None:
        """Store the steps.

        Args:
            sheets: Imports the shared drive's sheets.
            pos_history: Takes in the POS's past orders.
            messenger_history: Takes in the restaurants' past chats.
            notifications: Bound to this pipeline.
        """
        self.sheets, self.pos_history, self.messenger_history = (
            sheets,
            pos_history,
            messenger_history,
        )
        self.notifications = notifications

    def execute(self) -> None:
        """Run the steps, then announce what was taken in."""
        counts = self.sheets.execute()
        orders = self.pos_history.execute()
        chats = self.messenger_history.execute()
        self.notifications.publish(
            "bakery.onboarded",
            {**counts, "orders": orders, "messages": chats},
            summary=(
                f"Onboarded: {orders} café orders, {chats} chat messages, "
                f"{counts['restaurants']} restaurants, {counts['products']} products"
            ),
            level="success",
            subject=CafeSales,
        )


@Publisher("night-run.done")
@Pipeline
class NightRun:
    """Plans tomorrow: the café's forecast, then the bake sheet, then the delivery run.

    ``Scheduler`` runs it at 21:00 on the demo clock, after the evening's
    order changes are in; **Execute** runs it now. An order change
    confirmed after it works its day out again (see ``confirm-draft``).
    """

    def __init__(
        self,
        clock: Clock,
        cafe_forecast: Annotated[Callable[..., list], forecast],
        sheet: Annotated[Callable[..., list], bake_sheet],
        deliveries: Annotated[Callable[..., list], plan_deliveries],
        notifications: Notifications,
    ) -> None:
        """Store the steps.

        Args:
            clock: The demo clock, for "tomorrow".
            cafe_forecast: ``forecast``.
            sheet: ``bake_sheet``.
            deliveries: ``plan_deliveries``.
            notifications: Bound to this pipeline.
        """
        self.clock = clock
        self.cafe_forecast, self.sheet, self.deliveries = cafe_forecast, sheet, deliveries
        self.notifications = notifications

    def execute(self) -> dict:
        """Plan tomorrow on the demo clock; see ``plan``."""
        return self.plan(self.clock.now().date() + timedelta(days=1))

    def plan(self, day: date) -> dict:
        """Forecast, bake sheet and delivery run for ``day``, then announce them.

        Returns:
            ``{"date", "bake", "deliveries", "late"}``: how many items to
            bake, how many stops, and which restaurants the van reaches late.
        """
        self.cafe_forecast(date=day.isoformat())
        lines = self.sheet(date=day.isoformat())
        stops = self.deliveries(date=day.isoformat())
        bake = sum(line["total"] for line in lines)
        late = [s["restaurant"] for s in stops if s.get("late")]
        self.notifications.publish(
            "night-run.done",
            {"date": day.isoformat(), "bake": bake, "deliveries": len(stops), "late": late},
            summary=(
                f"Night run for {label(day)}: bake {bake} items, {len(stops)} deliveries"
                + (f", late at {', '.join(late)}" if late else "")
            ),
            level="warning" if late else "success",
            subject=BakeSheets,
        )
        return {"date": day.isoformat(), "bake": bake, "deliveries": len(stops), "late": late}


@Pipeline
class CloseCafe:
    """Closes the café's day: counts what didn't sell, then drafts tomorrow's specials from it.

    ``Scheduler`` runs it at 15:00 on the demo clock, when the café has
    closed; **Execute** runs it now.
    """

    def __init__(
        self,
        clock: Clock,
        leftovers: Annotated[Callable[..., list], count_leftovers],
        specials: Specials,
    ) -> None:
        """Store the steps.

        Args:
            clock: The demo clock, for "today".
            leftovers: ``count_leftovers``.
            specials: The ``specials`` agent.
        """
        self.clock, self.leftovers, self.specials = clock, leftovers, specials

    def execute(self) -> dict:
        """Count today's leftovers and draft tomorrow's specials from them.

        Returns:
            ``{"unsold", "draft"}``: how many items didn't sell, and the
            specials draft's id (``None`` if too little was left).
        """
        today = self.clock.now().date().isoformat()
        counted = self.leftovers(date=today)
        drafted = self.specials.invoke(date=today)
        return {"unsold": sum(c["unsold"] for c in counted), "draft": drafted["draft"]}
