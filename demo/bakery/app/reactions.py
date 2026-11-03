"""What the bakery does on its own when something arrives: reactions to notifications.

Each reaction is a ``@Subscriber``. The ``Context`` subscribes it once it
starts and unsubscribes it before it stops, and each delivery is a traced
call whose ``cause`` is the notification it reacts to, so a trace runs from
the webhook that brought a message in to the draft it became.
"""

from opendataframework import Component, Logger, Notification, Notifications, Publisher, Subscriber

from app import layers
from app.agents import OrderDesk
from app.allergens import (
    AllergenOfficer,
    ingredient_allergens,
    label_text,
    product_labels,
    trace,
)
from app.clients import Clock
from app.entities import IngredientAllergen
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
    Allergens,
    Contracts,
    IngredientPrices,
    Ingredients,
    Products,
    Recipes,
    StandingOrders,
)


@layers.Wholesale
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


@layers.Purchasing
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


@layers.Purchasing
@Publisher("margins.below-cost")
@Subscriber("prices.changed", deliver="background")
@Component
class Costing:
    """Watches what the contracts leave as prices change, and charts it.

    When an invoice's prices put a contract below cost that wasn't before,
    it publishes ``margins.below-cost``, naming each one. Its chart is the
    weekly margin by restaurant at today's prices. Delivered in the
    background, so its warning comes after the price notice that caused it,
    not inside it.
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
                f"{thinnest['restaurant']}: {thinnest['product']}, "
                f"{_pounds(thinnest['margin'])} each"
                if thinnest
                else "no contracts yet"
            ),
            "weekly margin": f"£{sum(r['weekly_margin'] for r in rows):,.2f}",
        }


@layers.Purchasing
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


def _pounds(value: float) -> str:
    """Return an amount as ``"£0.12"``, or ``"-£0.07"`` when it's negative."""
    return f"{'-' if value < 0 else ''}£{abs(value):.2f}"


@layers.Allergens
@Publisher("allergens.changed")
@Subscriber("ingredients.changed", deliver="background")
@Component
class Labelling:
    """Records an allergen a supplier declared, and says which labels it changes.

    Recording it errs on the safe side, so it happens at once, before
    anyone is told: every label the bakery works out from then on declares
    it. When it changes a product's label, ``allergens.changed`` names the
    products and the restaurants taking them.
    """

    def __init__(
        self,
        clock: Clock,
        ingredients: Ingredients,
        allergens: Allergens,
        recipes: Recipes,
        products: Products,
        standing_orders: StandingOrders,
        notifications: Notifications,
    ) -> None:
        """Store where allergens are recorded and what labels are worked out from.

        Args:
            clock: The demo clock, for when an allergen was recorded.
            ingredients: What an ingredient can be.
            allergens: Where they're recorded.
            recipes: What goes into each product.
            products: The products' names.
            standing_orders: Which restaurants take each product.
            notifications: Bound to this component.
        """
        self.clock, self.ingredients, self.allergens = clock, ingredients, allergens
        self.recipes, self.products, self.standing_orders = recipes, products, standing_orders
        self.notifications = notifications

    def _labels(self) -> dict[str, dict]:
        """Return each product's label, as the allergens recorded now make it."""
        names = {p.sku: p.name for p in self.products.all()}
        return product_labels(self.recipes, ingredient_allergens(self.allergens), names)

    def on_notification(self, notification: Notification) -> None:
        """Record what the invoice declared, and announce the labels it changed."""
        code = notification.payload["ingredient"]
        known = ingredient_allergens(self.allergens).get(code, {})
        before = self._labels()
        for a in notification.payload["allergens"]:
            if known.get(a["allergen"]) in ("contains", a["kind"]):
                continue  # already declared, as strongly
            self.allergens.save(
                IngredientAllergen(
                    id=None,
                    ingredient=code,
                    allergen=a["allergen"],
                    kind=a["kind"],
                    source=f"invoice {notification.payload.get('invoice')}",
                    since=self.clock.now().timestamp(),
                )
            )
        after = self._labels()
        changed = [sku for sku in after if after[sku] != before.get(sku)]
        if not changed:
            return
        found = trace(
            code, self.ingredients, self.allergens, self.recipes, self.products,
            self.standing_orders,
        )  # fmt: skip
        restaurants = [
            r["restaurant"] for r in found["restaurants"] if set(r["weekly"]) & set(changed)
        ]
        what = ", ".join(f"{a['kind']} {a['allergen']}" for a in notification.payload["allergens"])
        names = ", ".join(after[sku]["name"].lower() for sku in changed)
        self.notifications.publish(
            "allergens.changed",
            {
                "ingredient": code,
                "allergens": list(notification.payload["allergens"]),
                "products": [
                    {"sku": sku, "name": after[sku]["name"], "before": label_text(before[sku]),
                     "after": label_text(after[sku])}
                    for sku in changed
                ],
                "restaurants": restaurants,
            },
            summary=(
                f"{len(changed)} labels now {what}: {names}. "
                f"{len(restaurants)} restaurants to tell"
            ),
            level="warning",
            subject=Allergens,
        )  # fmt: skip

    def details(self) -> dict[str, str]:
        """Return the allergens invoices declared, beyond the sheet's."""
        added = [a for a in self.allergens.all() if a.source != "sheet"]
        names = {i.code: i.name for i in self.ingredients.all()}
        return {
            "declared by invoices": ", ".join(
                f"{names.get(a.ingredient, a.ingredient)}: {a.kind} {a.allergen} ({a.source})"
                for a in added
            )
            or "none",
        }


@layers.Allergens
@Subscriber("allergens.changed", deliver="background")
@Component
class AllergenNotices:
    """Has the allergen-officer draft the notices for each ingredient whose allergens changed."""

    def __init__(self, allergen_officer: AllergenOfficer) -> None:
        """Store the agent that drafts the notices.

        Args:
            allergen_officer: Drafts a notice for each restaurant to tell.
        """
        self.allergen_officer = allergen_officer

    def on_notification(self, notification: Notification) -> None:
        """Draft the notices for the ingredient the notification names."""
        self.allergen_officer.invoke(ingredient=notification.payload["ingredient"])
