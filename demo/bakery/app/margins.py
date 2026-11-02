"""What each product costs to make, and what each restaurant's contract leaves.

A product's unit cost is its recipe priced at each ingredient's latest
invoiced price (the sheet's price until an invoice says otherwise), bake
time included. A contract's margin is its agreed price less that cost;
only the contracts a restaurant actually orders count, weighted by how many
a week its standing orders take. All plain arithmetic, so a renegotiation
draft can be checked against it.
"""

import json
import math
from collections import defaultdict
from datetime import timedelta
from html import escape

from opendataframework import Agent, Function, Notifications, Publisher

from app.clients import Clock
from app.entities import Draft
from app.model import Model
from app.planning import label
from app.repositories import (
    Contracts,
    Drafts,
    IngredientPrices,
    Ingredients,
    Products,
    Recipes,
    StandingOrders,
)

# The margin a renegotiated price aims for, over cost.
TARGET_MARGIN = 0.15
# What a caller (a model, say) may pass as a restaurant to mean all of them.
EVERY = frozenset({"", "all", "*", "every", "any"})


def ingredient_prices(
    ingredients: Ingredients, prices: IngredientPrices, overrides: dict[str, float] | None = None
) -> dict[str, float]:
    """Return each ingredient's price now: the latest invoiced, else the sheet's.

    ``overrides`` replace any of them: a what-if, or the prices before an invoice.
    """
    return {i.code: i.price for i in ingredients.all()} | prices.latest() | dict(overrides or {})


def unit_costs(recipes: Recipes, prices: dict[str, float]) -> dict[str, float]:
    """Return what one of each product with a recipe costs to make, at ``prices``."""
    costs: dict[str, float] = defaultdict(float)
    for line in recipes.all():
        costs[line.sku] += line.quantity * prices.get(line.ingredient, 0.0)
    return {sku: round(cost, 4) for sku, cost in costs.items()}


def contract_margins(
    contracts: Contracts,
    standing_orders: StandingOrders,
    products: Products,
    costs: dict[str, float],
    restaurant: str = "",
) -> list[dict]:
    """Return the margin on each contract a restaurant orders, thinnest first.

    Returns:
        ``{"restaurant", "sku", "product", "price", "cost", "margin",
        "weekly", "weekly_margin"}`` per contract: ``weekly`` is how many its
        standing orders take a week.
    """
    weekly: dict[tuple[str, str], int] = defaultdict(int)
    for order in standing_orders.all():
        weekly[(order.restaurant, order.sku)] += order.quantity
    names = {p.sku: p.name for p in products.all()}
    rows = []
    for contract in contracts.all():
        key = (contract.restaurant, contract.sku)
        if key not in weekly or contract.sku not in costs:
            continue
        wanted = restaurant.strip().lower()
        if wanted not in EVERY and contract.restaurant.lower() != wanted:
            continue
        cost = costs[contract.sku]
        margin = round(contract.price - cost, 4)
        rows.append(
            {
                "restaurant": contract.restaurant,
                "sku": contract.sku,
                "product": names.get(contract.sku, contract.sku),
                "price": contract.price,
                "cost": round(cost, 2),
                "margin": round(margin, 2),
                "weekly": weekly[key],
                "weekly_margin": round(margin * weekly[key], 2),
            }
        )
    return sorted(rows, key=lambda r: (r["margin"] / r["price"], r["restaurant"], r["sku"]))


def below_cost(rows: list[dict]) -> list[dict]:
    """Return the contracts in ``rows`` that no longer cover their cost."""
    return [r for r in rows if r["margin"] < 0]


def proposed_price(cost: float) -> float:
    """Return the price a renegotiation asks for: cost plus ``TARGET_MARGIN``, up to 5p."""
    return math.ceil(round(cost * (1 + TARGET_MARGIN) / 0.05, 6)) * 0.05


@Function
def margins(
    contracts: Contracts,
    standing_orders: StandingOrders,
    products: Products,
    recipes: Recipes,
    ingredients: Ingredients,
    prices: IngredientPrices,
    restaurant: str = "",
) -> dict:
    """Return every restaurant's contract margins at today's prices, and those losing money.

    Leave ``restaurant`` empty to get every restaurant at once: one call
    answers "which restaurants are we losing money on?" (``below_cost``).

    Args:
        contracts: The agreed prices, injected.
        standing_orders: How many each restaurant takes, injected.
        products: The products' names, injected.
        recipes: What each product takes, injected.
        ingredients: The sheet's prices, injected.
        prices: The invoiced prices, injected.
        restaurant: Only this restaurant's contracts; all by default.

    Returns:
        ``{"contracts": [...], "below_cost": [...], "weekly_margin"}``:
        each contract's margin (thinnest first), those below cost, and what
        they leave together each week.
    """
    costs = unit_costs(recipes, ingredient_prices(ingredients, prices))
    rows = contract_margins(contracts, standing_orders, products, costs, restaurant)
    return {
        "contracts": rows,
        "below_cost": below_cost(rows),
        "weekly_margin": round(sum(r["weekly_margin"] for r in rows), 2),
    }


@Function
def what_if(
    ingredient: str,
    price: float,
    contracts: Contracts,
    standing_orders: StandingOrders,
    products: Products,
    recipes: Recipes,
    ingredients: Ingredients,
    prices: IngredientPrices,
) -> dict:
    """Return what the contracts would leave if ``ingredient`` cost ``price`` a unit.

    Args:
        ingredient: The ingredient's code (``"BUTTER"``) or name (``"Butter"``).
        price: Its price per unit, in pounds.
        contracts: The agreed prices, injected.
        standing_orders: How many each restaurant takes, injected.
        products: The products' names, injected.
        recipes: What each product takes, injected.
        ingredients: The sheet's prices, injected.
        prices: The invoiced prices, injected.

    Returns:
        ``{"ingredient", "now", "then", "weekly_margin": {"now", "then"},
        "below_cost": [...], "changed": [...]}``: the contracts that would be
        below cost, and every contract whose margin would change.

    Raises:
        KeyError: If there's no such ingredient.
    """
    sheet = {i.code: i for i in ingredients.all()}
    code = next(
        (c for c, i in sheet.items() if ingredient.lower() in (c.lower(), i.name.lower())), None
    )
    if code is None:
        raise KeyError(f"no ingredient {ingredient!r}")
    today = ingredient_prices(ingredients, prices)
    now = contract_margins(contracts, standing_orders, products, unit_costs(recipes, today))
    then = contract_margins(
        contracts,
        standing_orders,
        products,
        unit_costs(recipes, today | {code: float(price)}),
    )
    before = {(r["restaurant"], r["sku"]): r for r in now}
    changed = [
        {**r, "margin_now": before[(r["restaurant"], r["sku"])]["margin"]}
        for r in then
        if r["margin"] != before[(r["restaurant"], r["sku"])]["margin"]
    ]
    return {
        "ingredient": sheet[code].name,
        "now": today[code],
        "then": float(price),
        "weekly_margin": {
            "now": round(sum(r["weekly_margin"] for r in now), 2),
            "then": round(sum(r["weekly_margin"] for r in then), 2),
        },
        "below_cost": below_cost(then),
        "changed": changed,
    }


def margin_chart(rows: list[dict]) -> str:
    """Return the weekly margin by restaurant as a self-contained HTML bar chart (inline SVG).

    Each bar is what a restaurant's contracts leave a week, at today's
    prices; a restaurant with a contract below cost is drawn in red, with
    how many in its label.
    """
    by_restaurant: dict[str, float] = defaultdict(float)
    losing: dict[str, int] = defaultdict(int)
    for r in rows:
        by_restaurant[r["restaurant"]] += r["weekly_margin"]
        losing[r["restaurant"]] += r["margin"] < 0
    bars = sorted(by_restaurant.items(), key=lambda item: item[1])
    if not bars:
        return "<html><body><p>No contracts with standing orders yet.</p></body></html>"
    top = max(max(v for _, v in bars), 1.0)
    width, left, height = 640, 170, 30
    scale = (width - left - 90) / top
    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {len(bars) * height + 40}'"
        " font-family='system-ui, sans-serif' font-size='13'>",
        "<text x='0' y='16' font-weight='600' fill='currentColor'>"
        "Weekly margin by restaurant, at today's prices</text>",
    ]
    for n, (restaurant, value) in enumerate(bars):
        y = 34 + n * height
        colour = "#d9534f" if losing[restaurant] else "#3a9d6e"
        note = f" ({losing[restaurant]} below cost)" if losing[restaurant] else ""
        out += [
            f"<text x='{left - 8}' y='{y + 15}' text-anchor='end' fill='currentColor'>"
            f"{escape(restaurant)}</text>",
            f"<rect x='{left}' y='{y}' width='{max(value, 0) * scale:.1f}' height='20'"
            f" fill='{colour}' rx='3'/>",
            f"<text x='{left + max(value, 0) * scale + 6:.1f}' y='{y + 15}' fill='currentColor'>"
            f"£{value:,.2f}{escape(note)}</text>",
        ]
    out.append("</svg>")
    return (
        "<html><body style='margin:12px;color-scheme:light dark'>" + "".join(out) + "</body></html>"
    )


_LETTER_SYSTEM = """You write a short, friendly email from a bakery to a restaurant \
it supplies, asking to change the price of some products because ingredient costs \
went up. Use exactly the products, current prices, new prices and start date \
given; don't add any others or any discounts. British English, at most 120 words, \
signed "The Bakery". Answer with the email's body only."""

_LETTER_SCHEMA = {
    "type": "object",
    "properties": {"body": {"type": "string"}},
    "required": ["body"],
}


@Publisher("drafts.created")
@Agent
class AccountManager:
    """Drafts the email asking a restaurant for new prices, where its contract no longer pays.

    ``invoke(restaurant)`` works out that restaurant's contracts below cost
    at today's prices, and drafts an email proposing, for each, cost plus
    ``TARGET_MARGIN``, from the Monday after next. The numbers are the
    rules'; the model, if there is one, only writes the email. Confirming
    sends it. The contracts sheet stays as it is until the restaurant agrees
    and the owner changes it.
    """

    def __init__(
        self,
        clock: Clock,
        contracts: Contracts,
        standing_orders: StandingOrders,
        products: Products,
        recipes: Recipes,
        ingredients: Ingredients,
        prices: IngredientPrices,
        drafts: Drafts,
        model: Model,
        notifications: Notifications,
    ) -> None:
        """Store what the agent reads and where it drafts.

        Args:
            clock: The demo clock, for the new prices' start date.
            contracts: The agreed prices.
            standing_orders: How many each restaurant takes.
            products: The products' names.
            recipes: What each product takes.
            ingredients: The sheet's prices.
            prices: The invoiced prices.
            drafts: Where it drafts.
            model: Asked to write the email.
            notifications: Bound to this agent.
        """
        self.clock, self.contracts, self.standing_orders = clock, contracts, standing_orders
        self.products, self.recipes, self.ingredients = products, recipes, ingredients
        self.prices, self.drafts = prices, drafts
        self.model, self.notifications = model, notifications

    def invoke(self, restaurant: str) -> dict:
        """Draft new prices for ``restaurant``'s contracts below cost.

        A renegotiation already waiting for that restaurant is returned, not
        drafted again.

        Args:
            restaurant: The restaurant's name.

        Returns:
            ``{"draft", "changes"}``; ``"draft"`` is ``None`` when every
            contract it orders still covers its cost.
        """
        waiting = self.drafts.open_for_restaurant("renegotiation", restaurant)
        if waiting is not None:
            return {"draft": waiting.id, "changes": json.loads(waiting.changes)}
        costs = unit_costs(self.recipes, ingredient_prices(self.ingredients, self.prices))
        rows = below_cost(
            contract_margins(self.contracts, self.standing_orders, self.products, costs, restaurant)
        )
        if not rows:
            return {"draft": None, "changes": []}
        name = rows[0]["restaurant"]
        today = self.clock.now().date()
        start = today + timedelta(days=7 - today.weekday() + 7)
        changes = [
            {
                "sku": r["sku"],
                "product": r["product"],
                "price": r["price"],
                "cost": r["cost"],
                "proposed": round(proposed_price(r["cost"]), 2),
                "weekly": r["weekly"],
            }
            for r in rows
        ]
        letter, author = self._letter(name, changes, label(start))
        table = [
            f"| {c['product']} | £{c['price']:.2f} | £{c['cost']:.2f} | **£{c['proposed']:.2f}** "
            f"| {c['weekly']} |"
            for c in changes
        ]
        body = "\n".join(
            [
                f"## New prices for {name}",
                "",
                f"At today's ingredient prices, {len(changes)} of {name}'s contracts no longer "
                f"cover their cost. Each new price is cost plus {TARGET_MARGIN:.0%}, from "
                f"{label(start)}. Written by {author}.",
                "",
                "| Product | Contract | Cost now | Proposed | A week |",
                "|---|---|---|---|---|",
                *table,
                "",
                "Confirming emails this to the restaurant. Change the contracts sheet once "
                "they agree.",
                "",
                *(f"> {line}" if line else ">" for line in letter.splitlines()),
            ]
        )
        draft = Draft(
            id=None,
            created_at=self.clock.now().timestamp(),
            kind="renegotiation",
            status="pending",
            title=f"New prices for {name}",
            date=start.isoformat(),
            restaurant=name,
            message=None,
            changes=json.dumps(changes),
            reply=letter,
            author=author,
            note="",
            body=body,
        )
        self.drafts.save(draft)
        self.notifications.publish(
            "drafts.created",
            {"draft": draft.id, "kind": "renegotiation", "status": draft.status},
            summary=f"New prices for {name} await confirmation",
            subject=Drafts,
            record=draft.id,
        )
        return {"draft": draft.id, "changes": changes}

    def _letter(self, restaurant: str, changes: list[dict], start: str) -> tuple[str, str]:
        """Return the email and who wrote it.

        The model's, if there's one and its email names every new price; else the rules'.
        """
        lines = [
            f"- {c['product']}: £{c['price']:.2f} now, £{c['proposed']:.2f} from {start}"
            for c in changes
        ]
        if self.model.available():
            answer = self.model.ask(
                _LETTER_SYSTEM,
                f"Restaurant: {restaurant}\nStart date: {start}\n" + "\n".join(lines),
                _LETTER_SCHEMA,
            )
            body = str(answer.get("body", "")).strip() if isinstance(answer, dict) else ""
            prices = [f"£{c['proposed']:.2f}" for c in changes]
            if body and all(p in body for p in prices):
                return body, self.model.author
        items = "\n".join(
            f"- {c['product'].lower()}: £{c['proposed']:.2f} each (now £{c['price']:.2f})"
            for c in changes
        )
        letter = (
            f"Hello {restaurant},\n\n"
            "Our ingredient costs have gone up, and at our current prices some of what we bake "
            f"for you now costs us more to make than you pay for it. From {start}, we'd like to "
            f"change:\n\n{items}\n\n"
            "Everything else stays as it is. Happy to talk it through.\n\n"
            "Thanks,\nThe Bakery"
        )
        return letter, "rules"
