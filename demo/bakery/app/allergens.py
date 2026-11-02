"""Allergens: what each product's label must say, and who to tell when that changes.

A product's label is worked out from its recipe: every allergen any of its
ingredients contains, then those any may contain. An ingredient's allergens
are the allergens sheet's, plus any a supplier's invoice declared, such as a
substituted flour that "may contain sesame". Recording one an invoice
declared errs on the safe side, so it happens at once; telling the
restaurants waits for a person, and the notice is never written by a model:
its wording has to be exact.
"""

import json
import re
from collections import defaultdict

from opendataframework import Agent, Function, Notifications, Publisher

from app.clients import Clock
from app.entities import Draft
from app.planning import label
from app.repositories import (
    Allergens,
    Drafts,
    Ingredients,
    Products,
    Recipes,
    Restaurants,
    StandingOrders,
)

# The 14 allergens UK food law says a label must declare.
ALLERGENS = (
    "celery", "gluten", "crustaceans", "eggs", "fish", "lupin", "milk", "molluscs", "mustard",
    "nuts", "peanuts", "sesame", "soya", "sulphites",
)  # fmt: skip

# Other words a supplier may use for one of them.
_SAME = {
    "wheat": "gluten", "rye": "gluten", "barley": "gluten", "oats": "gluten", "egg": "eggs",
    "nut": "nuts", "tree nuts": "nuts", "peanut": "peanuts", "soy": "soya", "sulphur dioxide":
    "sulphites", "dairy": "milk", "sesame seeds": "sesame",
}  # fmt: skip

_STATEMENT = re.compile(r"\b(may contain|contains?)\b([^.;:]*)", re.IGNORECASE)


def declared(note: str) -> list[tuple[str, str]]:
    """Return the allergens a note declares, as ``(allergen, "contains" | "may contain")``.

    Reads statements such as "May contain sesame." or "Contains milk and
    soya", naming the 14 allergens or a few other words for them.
    """
    found = []
    for statement, rest in _STATEMENT.findall(note):
        kind = "may contain" if statement.lower() == "may contain" else "contains"
        words = re.split(r",|\band\b|&|/", rest.lower())
        for word in (w.strip() for w in words):
            allergen = _SAME.get(word, word)
            if allergen in ALLERGENS and (allergen, kind) not in found:
                found.append((allergen, kind))
    return found


def ingredient_allergens(allergens: Allergens) -> dict[str, dict[str, str]]:
    """Return each ingredient's allergens: ``{code: {allergen: "contains" | "may contain"}}``.

    Where the sheet and an invoice disagree, "contains" wins.
    """
    found: dict[str, dict[str, str]] = defaultdict(dict)
    for a in allergens.all():
        if found[a.ingredient].get(a.allergen) != "contains":
            found[a.ingredient][a.allergen] = a.kind
    return found


def product_labels(
    recipes: Recipes, allergens: dict[str, dict[str, str]], names: dict[str, str]
) -> dict[str, dict]:
    """Return each product's label: ``{sku: {"name", "contains", "may_contain"}}``, sorted."""
    contains: dict[str, set] = defaultdict(set)
    may: dict[str, set] = defaultdict(set)
    skus = []
    for line in recipes.all():
        if line.sku not in skus:
            skus.append(line.sku)
        for allergen, kind in allergens.get(line.ingredient, {}).items():
            (contains if kind == "contains" else may)[line.sku].add(allergen)
    return {
        sku: {
            "name": names.get(sku, sku),
            "contains": sorted(contains[sku]),
            "may_contain": sorted(may[sku] - contains[sku]),
        }
        for sku in skus
    }


def label_text(entry: dict) -> str:
    """Return a label as a line: ``"contains gluten, milk; may contain sesame"``."""
    parts = []
    if entry["contains"]:
        parts.append("contains " + ", ".join(entry["contains"]))
    if entry["may_contain"]:
        parts.append("may contain " + ", ".join(entry["may_contain"]))
    return "; ".join(parts) or "no allergens declared"


def _find(ingredients: Ingredients, ingredient: str):
    """Return the ingredient a code or name names.

    Raises:
        KeyError: If there's no such ingredient.
    """
    for i in ingredients.all():
        if ingredient.lower() in (i.code.lower(), i.name.lower()):
            return i
    raise KeyError(f"no ingredient {ingredient!r}")


def trace(
    ingredient: str,
    ingredients: Ingredients,
    allergens: Allergens,
    recipes: Recipes,
    products: Products,
    standing_orders: StandingOrders,
) -> dict:
    """Do ``trace_ingredient``'s work: see there."""
    found = _find(ingredients, ingredient)
    names = {p.sku: p.name for p in products.all()}
    labels = product_labels(recipes, ingredient_allergens(allergens), names)
    uses = {line.sku: line.quantity for line in recipes.all() if line.ingredient == found.code}
    weekly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for order in standing_orders.all():
        if order.sku in uses:
            weekly[order.restaurant][order.sku] += order.quantity
    return {
        "ingredient": found.code,
        "name": found.name,
        "supplier": found.supplier,
        "allergens": dict(ingredient_allergens(allergens).get(found.code, {})),
        "products": [
            {"sku": sku, "name": names.get(sku, sku), "uses": quantity, "label": labels[sku]}
            for sku, quantity in uses.items()
        ],
        "restaurants": [
            {"restaurant": restaurant, "weekly": dict(by_sku)}
            for restaurant, by_sku in sorted(weekly.items())
        ],
    }


@Function
def trace_ingredient(
    ingredient: str,
    ingredients: Ingredients,
    allergens: Allergens,
    recipes: Recipes,
    products: Products,
    standing_orders: StandingOrders,
) -> dict:
    """Follow an ingredient to the products it goes into, their labels, and who takes them.

    Args:
        ingredient: The ingredient's code (``"FLOUR"``) or name.
        ingredients: What it can be, injected.
        allergens: Its allergens and every other's, injected.
        recipes: What goes into each product, injected.
        products: The products' names, injected.
        standing_orders: Which restaurants take each product, injected.

    Returns:
        ``{"ingredient", "name", "supplier", "allergens", "products",
        "restaurants"}``: its allergens; each product it goes into, with how
        much and the product's label; each restaurant taking any of them,
        with how many a week.

    Raises:
        KeyError: If there's no such ingredient.
    """
    return trace(ingredient, ingredients, allergens, recipes, products, standing_orders)


@Function
def labels(allergens: Allergens, recipes: Recipes, products: Products) -> list[dict]:
    """Return what each product's label must declare, from its recipe.

    Args:
        allergens: Each ingredient's allergens, injected.
        recipes: What goes into each product, injected.
        products: The products' names, injected.

    Returns:
        ``{"sku", "name", "contains", "may_contain", "label"}`` per product.
    """
    names = {p.sku: p.name for p in products.all()}
    found = product_labels(recipes, ingredient_allergens(allergens), names)
    return [{"sku": sku, **entry, "label": label_text(entry)} for sku, entry in found.items()]


@Publisher("drafts.created")
@Agent
class AllergenOfficer:
    """Drafts the notices telling restaurants that what they take now has a new allergen.

    ``invoke(ingredient)`` traces the ingredient to the products it goes into
    and the restaurants taking them, and drafts one notice for each
    restaurant, naming its products and their labels as they are now. The
    allergens it calls new are those an invoice declared, not the sheet.
    The draft also lists the label changes for the café. Written by rules
    only: an allergen notice's wording has to be exact. Confirming emails
    every notice.
    """

    def __init__(
        self,
        clock: Clock,
        ingredients: Ingredients,
        allergens: Allergens,
        recipes: Recipes,
        products: Products,
        standing_orders: StandingOrders,
        restaurants: Restaurants,
        drafts: Drafts,
        notifications: Notifications,
    ) -> None:
        """Store what the agent reads and where it drafts.

        Args:
            clock: The demo clock, for the notices' date.
            ingredients: What can be traced.
            allergens: Each ingredient's allergens.
            recipes: What goes into each product.
            products: The products' names.
            standing_orders: Which restaurants take each product.
            restaurants: Where each notice goes.
            drafts: Where it drafts.
            notifications: Bound to this agent.
        """
        self.clock, self.ingredients, self.allergens = clock, ingredients, allergens
        self.recipes, self.products, self.standing_orders = recipes, products, standing_orders
        self.restaurants, self.drafts, self.notifications = restaurants, drafts, notifications

    def invoke(self, ingredient: str) -> dict:
        """Draft the notices for the allergens an invoice declared for ``ingredient``.

        A notice already waiting for that ingredient is returned, not drafted
        again.

        Args:
            ingredient: The ingredient's code or name.

        Returns:
            ``{"draft", "allergens", "restaurants"}``; ``"draft"`` is ``None``
            when no invoice declared an allergen for it.

        Raises:
            KeyError: If there's no such ingredient.
        """
        found = trace(
            ingredient, self.ingredients, self.allergens, self.recipes, self.products,
            self.standing_orders,
        )  # fmt: skip
        new = sorted(
            {
                (a.allergen, a.kind)
                for a in self.allergens.where("ingredient", found["ingredient"])
                if a.source != "sheet"
            }
        )
        if not new:
            return {"draft": None, "allergens": [], "restaurants": []}
        what = ", ".join(f"{kind} {allergen}" for allergen, kind in new)
        title = f"Allergen notice: {found['name'].lower()} now {what}"
        waiting = self.drafts.open_titled("allergen-notice", title)
        if waiting is not None:
            changes = json.loads(waiting.changes)
            return {
                "draft": waiting.id,
                "allergens": changes["allergens"],
                "restaurants": [n["restaurant"] for n in changes["notices"]],
            }
        today = self.clock.now().date()
        labels_by_sku = {p["sku"]: p for p in found["products"]}
        contacts = {r.name: r.email for r in self.restaurants.all()}
        notices = [
            self._notice(r, labels_by_sku, contacts.get(r["restaurant"], ""), what, today)
            for r in found["restaurants"]
        ]
        rows = [f"| {p['name']} | {label_text(p['label'])} |" for p in found["products"]]
        recipients = (
            ", ".join(n["restaurant"] for n in notices) or "nobody: no restaurant takes them"
        )
        body = "\n".join(
            [
                f"## {title}",
                "",
                f"An invoice from {found['supplier']} declared that {found['name'].lower()} "
                f"now {what}. It's recorded, so every label below already says so. Confirming "
                f"emails a notice to each restaurant taking these products: {recipients}.",
                "",
                "### Labels, for the café too",
                "",
                "| Product | Label |",
                "|---|---|",
                *rows,
                "",
                *(
                    [f"### The notice to {notices[0]['restaurant']}", ""]
                    + [f"> {line}" if line else ">" for line in notices[0]["text"].splitlines()]
                    if notices
                    else []
                ),
            ]
        )
        draft = Draft(
            id=None,
            created_at=self.clock.now().timestamp(),
            kind="allergen-notice",
            status="pending",
            title=title,
            date=today.isoformat(),
            restaurant=None,
            message=None,
            changes=json.dumps(
                {
                    "ingredient": found["ingredient"],
                    "allergens": [{"allergen": a, "kind": k} for a, k in new],
                    "notices": notices,
                }
            ),
            reply="",
            author="rules",
            note="",
            body=body,
        )
        self.drafts.save(draft)
        self.notifications.publish(
            "drafts.created",
            {"draft": draft.id, "kind": "allergen-notice", "status": draft.status},
            summary=f"{title}: {len(notices)} notices await confirmation",
            level="warning",
            subject=Drafts,
            record=draft.id,
        )
        return {
            "draft": draft.id,
            "allergens": [{"allergen": a, "kind": k} for a, k in new],
            "restaurants": [n["restaurant"] for n in notices],
        }

    def _notice(self, taken: dict, labels_by_sku: dict, email: str, what: str, today) -> dict:
        """Return one restaurant's notice: ``{"restaurant", "email", "subject", "text"}``."""
        products = [labels_by_sku[sku] for sku in taken["weekly"]]
        items = "\n".join(f"- {p['name']}: {label_text(p['label'])}" for p in products)
        names = ", ".join(p["name"].lower() for p in products)
        text = (
            f"Hello {taken['restaurant']},\n\n"
            f"An ingredient in some of what we deliver to you has changed: it now {what}. "
            f"From {label(today)}, until we tell you otherwise, please treat these as "
            f"labelled below:\n\n{items}\n\n"
            "Please update your menus and allergen information, and let your staff know.\n\n"
            "Thanks,\nThe Bakery"
        )
        return {
            "restaurant": taken["restaurant"],
            "email": email,
            "subject": f"Allergen notice: {names}",
            "text": text,
        }
