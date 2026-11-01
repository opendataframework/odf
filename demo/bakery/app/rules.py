"""The rules the agents read with before they ask a model: plain, deterministic, and checkable.

Most order changes come in one of a handful of phrasings, and those don't
need a model. What the rules can't read, they say so (``None``), and the
agent asks the model, or marks the draft for a person to review.
"""

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from app.entities import Leftover, Product

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MODES = ("add", "set", "set-from")


@dataclass(frozen=True)
class Change:
    """A change to a restaurant's order, as read from a message.

    Attributes:
        sku: The product.
        date: The day, or the first day of a lasting change, ``"YYYY-MM-DD"``.
        mode: ``"add"``, ``"set"`` or ``"set-from"`` (see ``OrderChange``).
        quantity: How many.
    """

    sku: str
    date: str
    mode: str
    quantity: int

    def as_dict(self) -> dict:
        """Return the change as a JSON-ready dict."""
        return asdict(self)


# Products nobody counts with a plural.
UNCOUNTABLE = frozenset({"brioche", "focaccia"})


def plural(name: str) -> str:
    """Return a product's name as a restaurant writes more than one, lower case.

    ``"Baguette"`` is ``"baguettes"``, ``"Sourdough loaf"`` ``"sourdough
    loaves"``, ``"Pain au chocolat"`` ``"pains au chocolat"`` and
    ``"Brioche"`` stays ``"brioche"``.
    """
    words = name.lower().split()
    if " ".join(words) in UNCOUNTABLE:
        return " ".join(words)
    if words[-1] == "loaf":
        return " ".join([*words[:-1], "loaves"])
    if len(words) > 1 and words[1] in ("au", "aux", "de"):
        return " ".join([words[0] + "s", *words[1:]])
    return " ".join([*words[:-1], words[-1] + "s"])


def aliases(products: Iterable[Product]) -> dict[str, str]:
    """Return every way a restaurant writes a baked product, lower case, mapped to its SKU.

    That's its name, its plural (see ``plural``), and for a loaf its name
    without "loaf": ``"sourdough"``.
    """
    found: dict[str, str] = {}
    for p in products:
        if p.wholesale_price is None:
            continue
        name = p.name.lower()
        forms = {name, plural(name)}
        if name.endswith(" loaf"):
            forms.add(name.removesuffix(" loaf"))
        for form in forms:
            found[form] = p.sku
    return found


def next_weekday(after: date, weekday: str) -> date:
    """Return the first ``weekday`` (``"friday"``) after the day ``after``."""
    ahead = (WEEKDAYS.index(weekday.lower()) - after.weekday() - 1) % 7 + 1
    return after + timedelta(days=ahead)


# The phrasings rules read: (pattern, mode, when), with the groups ``n``,
# ``item`` and ``weekday``. ``when`` is ``"tomorrow"`` or ``"weekday"``.
_TEMPLATES = (
    (r"(?P<n>\d+) extra (?P<item>[a-z ]+?) tomorrow(?: please)?", "add", "tomorrow"),
    (r"could we get (?P<n>\d+) (?P<item>[a-z ]+?) on (?P<weekday>[a-z]+)", "set", "weekday"),
    (r"no (?P<item>[a-z ]+?) on (?P<weekday>[a-z]+) this week(?:,? thanks)?", "set", "weekday"),
    (r"please drop the (?P<item>[a-z ]+?) to (?P<n>\d+) from tomorrow", "set-from", "tomorrow"),
)


def read_order_change(
    text: str, products: Iterable[Product], received: date
) -> list[Change] | None:
    """Read a templated order change, such as "2 extra baguettes tomorrow please".

    Args:
        text: The line of the message that says what it wants (see ``ingest.gist``).
        products: The bakery's products, for what the restaurant names.
        received: The day it was sent, for "tomorrow" and "on Friday".

    Returns:
        The changes it asks for, or ``None`` if it isn't a phrasing the rules
        know, or names a product or day they don't.
    """
    names = aliases(products)
    line = " ".join(text.lower().split()).strip(" .!?")
    for pattern, mode, when in _TEMPLATES:
        found = re.fullmatch(pattern, line)
        if not found:
            continue
        groups = found.groupdict()
        sku = names.get(groups["item"].strip())
        if sku is None:
            return None
        if when == "tomorrow":
            day = received + timedelta(days=1)
        elif groups["weekday"] in WEEKDAYS:
            day = next_weekday(received, groups["weekday"])
        else:
            return None
        return [Change(sku, day.isoformat(), mode, int(groups.get("n") or 0))]
    return None


def check_changes(
    answer: object, products: Iterable[Product], received: date
) -> list[Change] | None:
    """Return the model's changes if every one is well formed, or ``None``.

    A change must name a baked product's SKU, a mode the bakery knows, a
    quantity from -500 to 500 (only ``"add"`` can be negative) and a day
    from the day it was sent to four weeks on.
    """
    skus = {p.sku for p in products if p.wholesale_price is not None}
    if not isinstance(answer, list) or not answer:
        return None
    changes = []
    for item in answer:
        try:
            change = Change(
                str(item["sku"]), str(item["date"]), str(item["mode"]), int(item["quantity"])
            )
            day = date.fromisoformat(change.date)
        except KeyError, TypeError, ValueError:
            return None
        if (
            change.sku not in skus
            or change.mode not in MODES
            or not -500 <= change.quantity <= 500
            or (change.quantity < 0 and change.mode != "add")
            or not received <= day <= received + timedelta(weeks=4)
        ):
            return None
        changes.append(change)
    return changes


# What yesterday's bake becomes on the specials board: (dish, how it's described, price).
SPECIALS = {
    "CRO": ("Almond croissant", "twice-baked with frangipane and flaked almonds", 3.20),
    "PAC": ("Pain perdu", "chocolate pastry soaked in custard and fried, with crème fraîche", 6.50),
    "SD-LOAF": ("Panzanella", "torn sourdough, tomatoes, red onion and basil", 7.50),
    "BAG": ("Garlic baguette", "with parsley butter, baked to order", 3.50),
    "BRI": ("Brioche French toast", "with poached pears and maple", 7.90),
    "FOC": ("Soup and focaccia", "today's soup with toasted focaccia", 6.90),
    "RYE": ("Rye crispbreads", "with smoked mackerel pâté and pickles", 6.50),
}
# Leftovers worth a special: fewer go in the staff's lunch.
SPECIAL_MIN = 3


def specials_for(leftovers: Iterable[Leftover]) -> list[dict]:
    """Return tomorrow's specials for what's left over, most left first.

    Returns:
        ``{"sku", "dish", "description", "price", "uses"}`` dicts, one per
        product with at least ``SPECIAL_MIN`` left that has a special.
    """
    found = [
        {
            "sku": left.sku,
            "dish": SPECIALS[left.sku][0],
            "description": SPECIALS[left.sku][1],
            "price": SPECIALS[left.sku][2],
            "uses": f"{left.unsold} × {left.product}",
        }
        for left in sorted(leftovers, key=lambda left: -left.unsold)
        if left.unsold >= SPECIAL_MIN and left.sku in SPECIALS
    ]
    return found
