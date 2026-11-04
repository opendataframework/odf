"""Tours: the world console playing one of the bakery's flows end to end, saying what to look at.

A scenario only starts a flow. A tour starts one too, then follows the
bakery's notifications through each step that comes after, saying as it goes
what to look at in which tool, until a person confirms what the agent
drafted. Each step waits for a notification: its topic, and payload fields
that tie it to this tour (the restaurant that wrote, the drafts it drafted).
The last step waits for the presenter.

This module is the tours themselves, and how a step matches a notification.
``tools/world.py`` plays them.
"""

from dataclasses import dataclass, field

from tools.data import RESTAURANTS

# Who writes in the order-change tour, and what: a phrasing the rules read.
ORDER_RESTAURANT = RESTAURANTS[1]
ORDER_MESSAGE = "2 extra baguettes tomorrow please"


@dataclass(frozen=True)
class Step:
    """One step of a tour, and the notification that completes it.

    Attributes:
        say: What's happening, and what to look at. ``{name}`` is a captured
            value; ``**bold**`` and backquoted names are shown as such.
        look: Which tool to look in, a key of the console's links.
        topic: The notification's topic that completes the step. ``None``:
            the presenter moves on.
        where: Payload fields the notification must have. ``"{name}"`` is
            any of the values captured as ``name``.
        count: How many such notifications complete it, or the name of a
            capture holding one value per notification to wait for.
        capture: Values to keep from each notification it matches, by name:
            a payload field, or a path through lists, such as
            ``"contracts.*.restaurant"``.
        confirms: The capture holding draft ids the console's **Do it for
            me** confirms.
    """

    say: str
    look: str | None = None
    topic: str | None = None
    where: dict[str, str] = field(default_factory=dict)
    count: int | str = 1
    capture: dict[str, str] = field(default_factory=dict)
    confirms: str | None = None


@dataclass(frozen=True)
class Tour:
    """A flow to play: its title, the values known before it starts, and its steps."""

    title: str
    steps: tuple[Step, ...]
    given: dict[str, str] = field(default_factory=dict)


def pick(payload: object, path: str) -> list:
    """Return the values at ``path`` in ``payload``, each once, in order.

    ``path`` is dotted field names, with ``*`` for every item of a list.
    """
    found = [payload]
    for part in path.split("."):
        nxt = []
        for value in found:
            if part == "*" and isinstance(value, list):
                nxt.extend(value)
            elif isinstance(value, dict) and part in value:
                nxt.append(value[part])
        found = nxt
    return list(dict.fromkeys(v for v in found if v is not None and not isinstance(v, dict)))


def matches(step: Step, notification: dict, captured: dict[str, list]) -> bool:
    """Return whether ``notification`` is one ``step`` waits for."""
    if step.topic is None or notification.get("topic") != step.topic:
        return False
    payload = notification.get("payload") or {}
    for name, wanted in step.where.items():
        values = pick(payload, name)
        if wanted.startswith("{") and wanted.endswith("}"):
            allowed = {str(v) for v in captured.get(wanted[1:-1], ())}
        else:
            allowed = {wanted}
        if not any(str(v) in allowed for v in values):
            return False
    return True


def capture(step: Step, notification: dict, captured: dict[str, list]) -> None:
    """Keep the values ``step`` captures from ``notification`` in ``captured``."""
    payload = notification.get("payload") or {}
    for name, path in step.capture.items():
        kept = captured.setdefault(name, [])
        kept.extend(v for v in pick(payload, path) if v not in kept)


def needed(step: Step, captured: dict[str, list]) -> int:
    """Return how many notifications complete ``step``: at least one."""
    if isinstance(step.count, str):
        return max(1, len(captured.get(step.count, ())))
    return max(1, step.count)


class _Filled(dict):
    """Captured values for ``str.format_map``, joined, with a placeholder for those not yet seen."""

    def __missing__(self, key: str) -> str:
        return "…"


def say(step: Step, captured: dict[str, list]) -> str:
    """Return ``step``'s caption, with the values captured so far."""
    return step.say.format_map(
        _Filled({k: ", ".join(str(v) for v in vs) for k, vs in captured.items() if vs})
    )


TOURS: dict[str, Tour] = {
    "order-change": Tour(
        title="A restaurant's message becomes a draft, and you confirm it",
        given={"restaurant": ORDER_RESTAURANT.name},
        steps=(
            Step(
                say=f'{{restaurant}} messages "{ORDER_MESSAGE}". The messenger\'s webhook '
                "reaches the bakery, and a notice in its UI says so: **Open** goes to the "
                "message in `Messages`, **Show logs** to the call that took it in.",
                look="Bakery (odf)",
                topic="messages.received",
                where={"restaurant": "{restaurant}"},
            ),
            Step(
                say="`Drafting` reacts to the message in the background and has the "
                "**order-desk** agent draft the change, so the webhook never waits. On the "
                "topology, the dotted link from `ingest-message` to `Drafting` lights up, and "
                "a second notice says the draft awaits confirmation.",
                look="Bakery (odf)",
                topic="drafts.created",
                where={"kind": "order-change"},
                capture={"drafts": "draft"},
            ),
            Step(
                say="Open **Chat** in the header: under **restaurants**, {restaurant}'s thread "
                "has the message and the draft answering it as a card, each product before "
                "and after. **Show run** on either notice shows the whole run as one tree. "
                "Then **Confirm draft** on the card, changing the reply first if you like.",
                look="Bakery (odf)",
                topic="drafts.confirmed",
                where={"draft": "{drafts}"},
                count="drafts",
                capture={"confirmed": "draft"},
                confirms="drafts",
            ),
            Step(
                say="The reply is in {restaurant}'s thread in the messenger, and in the "
                "bakery's thread on its side. The change has reached the bake sheet.",
                look="Messenger",
            ),
        ),
    ),
    "butter-spike": Tour(
        title="Butter goes up: an invoice, the margins, and new prices to confirm",
        steps=(
            Step(
                say="Vale Dairy emails its invoice early, a PDF with butter up sharply. The "
                "bakery's mailbox poll takes it in, and a notice says so; the PDF is in "
                "`Invoices`.",
                look="Mail",
                topic="invoices.received",
                where={"supplier": "Vale Dairy"},
            ),
            Step(
                say="`Purchasing` reacts and the **invoice-clerk** reads the PDF by rules, "
                "recording each ingredient's price in `IngredientPrices`. A warning names the "
                "rise.",
                look="Bakery (odf)",
                topic="prices.changed",
                where={"supplier": "Vale Dairy"},
            ),
            Step(
                say="`Costing` works out what each restaurant's contract leaves at the new "
                "price, and a second warning names those no longer covering their cost. "
                "`Costing`'s **Chart** shows the weekly margin by restaurant.",
                look="Bakery (odf)",
                topic="margins.below-cost",
                capture={"restaurants": "contracts.*.restaurant"},
            ),
            Step(
                say="`Renegotiating` has the **account-manager** draft an email to each of "
                "{restaurants}, asking for cost plus 15% from the Monday after next. "
                "**Show run** on any of these notices shows the chain as one tree, from the "
                "invoice to the drafts.",
                look="Bakery (odf)",
                topic="drafts.created",
                where={"kind": "renegotiation"},
                count="restaurants",
                capture={"drafts": "draft"},
            ),
            Step(
                say="Open each draft in `Drafts` and **Confirm draft** to email it to the "
                "restaurant.",
                look="Bakery (odf)",
                topic="drafts.confirmed",
                where={"draft": "{drafts}"},
                count="drafts",
                capture={"confirmed": "draft"},
                confirms="drafts",
            ),
            Step(
                say="The emails to {restaurants} are in the mailbox. In the bakery, "
                '**what-if** answers "what if butter cost £12?" without an invoice, and '
                "**margins** lists every contract's margin.",
                look="Mail",
            ),
        ),
    ),
    "sesame-substitution": Tour(
        title="A flour that may contain sesame: labels, and a notice to every restaurant",
        steps=(
            Step(
                say="Millers Ltd emails this week's invoice. Under the flour it says this "
                "week's comes from Hillside Mill, and may contain sesame.",
                look="Mail",
                topic="invoices.received",
                where={"supplier": "Millers Ltd"},
            ),
            Step(
                say="The **invoice-clerk** records the prices as usual, and a warning says the "
                "flour now may contain sesame.",
                look="Bakery (odf)",
                topic="ingredients.changed",
                where={"supplier": "Millers Ltd"},
            ),
            Step(
                say="`Labelling` records it at once, so every label says so, and a second "
                "warning names the labels it changed and the restaurants taking those "
                "products. **labels** gives every product's label, and **trace-ingredient** "
                "follows the flour to them.",
                look="Bakery (odf)",
                topic="allergens.changed",
                capture={"restaurants": "restaurants"},
            ),
            Step(
                say="The **allergen-officer** drafts one notice per restaurant, naming its "
                "own products and their labels, with the label changes for the café.",
                look="Bakery (odf)",
                topic="drafts.created",
                where={"kind": "allergen-notice"},
                capture={"drafts": "draft"},
            ),
            Step(
                say="Open the draft in `Drafts` and **Confirm draft** to email every notice.",
                look="Bakery (odf)",
                topic="drafts.confirmed",
                where={"draft": "{drafts}"},
                count="drafts",
                capture={"confirmed": "draft"},
                confirms="drafts",
            ),
            Step(
                say="The notices are in the mailbox, one for each of {restaurants}.",
                look="Mail",
            ),
        ),
    ),
}
