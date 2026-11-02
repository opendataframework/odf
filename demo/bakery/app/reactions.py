"""What the bakery does on its own when something arrives: reactions to notifications.

Each reaction is a ``@Subscriber``. The ``Context`` subscribes it once it
starts and unsubscribes it before it stops, and each delivery is a traced
call whose ``cause`` is the notification it reacts to, so a trace runs from
the webhook that brought a message in to the draft it became.
"""

from opendataframework import Component, Logger, Notification, Notifications, Publisher, Subscriber

from app.agents import OrderDesk
from app.margins import (
    AccountManager,
    below_cost,
    contract_margins,
    ingredient_prices,
    margin_chart,
    unit_costs,
)
from app.purchasing import InvoiceClerk
from app.repositories import (
    Contracts,
    IngredientPrices,
    Ingredients,
    Products,
    Recipes,
    StandingOrders,
)


@Subscriber("messages.received", deliver="background")
@Component
class Drafting:
    """Drafts the order change a restaurant's message asks for, as soon as it arrives.

    Runs in the background, on a worker of its own, so the model a draft may
    ask doesn't hold up the webhook or the mailbox that took the message in.
    Only a restaurant on the restaurants sheet gets a draft this way;
    anyone else's message waits in Messages for a person, who can still run
    **order-desk** on it.
    """

    def __init__(self, order_desk: OrderDesk, logger: Logger) -> None:
        """Store the agent that drafts.

        Args:
            order_desk: Drafts the change and its reply.
            logger: This component's log.
        """
        self.order_desk = order_desk
        self.logger = logger

    def on_notification(self, notification: Notification) -> None:
        """Draft for the message ``notification`` announces, if a restaurant sent it."""
        restaurant = notification.payload.get("restaurant")
        if restaurant is None:
            self.logger.info(
                "not from a restaurant: left for a person", message=notification.record
            )
            return
        self.order_desk.invoke(message_id=notification.record)


@Subscriber("invoices.received", deliver="background")
@Component
class Purchasing:
    """Has the invoice-clerk read each supplier's invoice as it arrives, on a worker of its own."""

    def __init__(self, invoice_clerk: InvoiceClerk) -> None:
        """Store the agent that reads invoices.

        Args:
            invoice_clerk: Records an invoice's prices, or drafts its reading.
        """
        self.invoice_clerk = invoice_clerk

    def on_notification(self, notification: Notification) -> None:
        """Read the invoice ``notification`` announces."""
        self.invoice_clerk.invoke(invoice_id=notification.record)


@Publisher("margins.below-cost")
@Subscriber("prices.changed")
@Component
class Costing:
    """Watches what the contracts leave as prices change, and charts it.

    When an invoice's prices put a contract below cost that wasn't before,
    it publishes ``margins.below-cost``, naming each one. Its chart is the
    weekly margin by restaurant at today's prices.
    """

    def __init__(
        self,
        contracts: Contracts,
        standing_orders: StandingOrders,
        products: Products,
        recipes: Recipes,
        ingredients: Ingredients,
        prices: IngredientPrices,
        notifications: Notifications,
    ) -> None:
        """Store what margins are worked out from.

        Args:
            contracts: The agreed prices.
            standing_orders: How many each restaurant takes.
            products: The products' names.
            recipes: What each product takes.
            ingredients: The sheet's prices.
            prices: The invoiced prices.
            notifications: Bound to this component.
        """
        self.contracts, self.standing_orders, self.products = contracts, standing_orders, products
        self.recipes, self.ingredients, self.prices = recipes, ingredients, prices
        self.notifications = notifications

    def _margins(self, overrides: dict[str, float] | None = None) -> list[dict]:
        """Return every ordered contract's margin, at today's prices with ``overrides``."""
        prices = ingredient_prices(self.ingredients, self.prices, overrides)
        costs = unit_costs(self.recipes, prices)
        return contract_margins(self.contracts, self.standing_orders, self.products, costs)

    def on_notification(self, notification: Notification) -> None:
        """Compare the contracts' margins before and after an invoice's prices."""
        changes = notification.payload.get("changes", ())
        before = {c["ingredient"]: c["was"] for c in changes}
        was_below = {(r["restaurant"], r["sku"]) for r in below_cost(self._margins(before))}
        newly = [
            r for r in below_cost(self._margins()) if (r["restaurant"], r["sku"]) not in was_below
        ]
        if not newly:
            return
        named = ", ".join(f"{r['restaurant']}'s {r['product'].lower()}" for r in newly)
        count = f"{len(newly)} contract{'s' if len(newly) > 1 else ''}"
        self.notifications.publish(
            "margins.below-cost",
            {
                "contracts": [
                    {k: r[k] for k in ("restaurant", "sku", "product", "price", "cost")}
                    for r in newly
                ],
                "invoice": notification.payload.get("invoice"),
            },
            summary=f"{count} now below cost: {named}",
            level="warning",
            subject=Contracts,
        )

    def chart(self) -> str:
        """Return the weekly margin by restaurant, at today's prices."""
        return margin_chart(self._margins())

    def details(self) -> dict[str, str]:
        """Return the contracts below cost and the thinnest margin, at today's prices."""
        rows = self._margins()
        losing = below_cost(rows)
        thinnest = rows[0] if rows else None
        return {
            "below cost": ", ".join(f"{r['restaurant']}: {r['product']}" for r in losing) or "none",
            "thinnest": (
                f"{thinnest['restaurant']}: {thinnest['product']}, £{thinnest['margin']:.2f} each"
                if thinnest
                else "no contracts yet"
            ),
            "weekly margin": f"£{sum(r['weekly_margin'] for r in rows):,.2f}",
        }


@Subscriber("margins.below-cost", deliver="background")
@Component
class Renegotiating:
    """Has the account-manager draft new prices for each restaurant with a contract below cost."""

    def __init__(self, account_manager: AccountManager) -> None:
        """Store the agent that drafts new prices.

        Args:
            account_manager: Drafts the email proposing them.
        """
        self.account_manager = account_manager

    def on_notification(self, notification: Notification) -> None:
        """Draft for each restaurant the notification names, once each."""
        restaurants = dict.fromkeys(c["restaurant"] for c in notification.payload["contracts"])
        for restaurant in restaurants:
            self.account_manager.invoke(restaurant=restaurant)
