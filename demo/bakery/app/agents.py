"""The bakery's agents. Each one drafts, and a person confirms (see ``app.drafts``).

Each reads with plain rules first (``app.rules``), asks the ``Model`` only for
what the rules can't read, and when there's no model it marks the draft
for a person to review rather than guessing. Nothing an agent does reaches
a restaurant or the bake sheet until someone confirms the draft.

In this phase a person (the UI, MCP or chat) or the ``Scheduler`` starts
them. Starting ``order-desk`` on its own when a message arrives comes with
``opendataframework`` 0.6.0's declared listeners.
"""

import json
from datetime import date, datetime, timedelta

from opendataframework import Agent, Notifications, Publisher

from app import layers
from app.clients import Clock
from app.entities import Draft, Message, OrderChange
from app.ingest import gist
from app.model import Model
from app.planning import day_of, label, restaurant_orders, wholesale_order
from app.repositories import (
    Drafts,
    Leftovers,
    Messages,
    OrderChanges,
    Products,
    StandingOrders,
)
from app.rules import Change, check_changes, plural, read_order_change, specials_for

_ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "date": {"type": "string"},
                    "mode": {"type": "string", "enum": ["add", "set", "set-from"]},
                    "quantity": {"type": "integer"},
                },
                "required": ["sku", "date", "mode", "quantity"],
            },
        },
        "reply": {"type": "string"},
        "unclear": {"type": "boolean"},
        "note": {"type": "string"},
    },
    "required": ["changes", "reply", "unclear", "note"],
}

_ORDER_SYSTEM = """You read the messages a bakery's restaurant customers send about \
their bread and pastry orders, and turn each into changes to the order.

Each change has a product's SKU, a date (YYYY-MM-DD) and a mode:
- "add": quantity more on that date (negative for fewer);
- "set": exactly quantity on that date (0 for none);
- "set-from": exactly quantity on every day it's usually ordered, from that date on.

Use only the SKUs listed. Work out dates from the day the message was sent. \
A change is for one day unless the message says it lasts ("from now on", "every \
day", "going forward"), which is "set-from". With no day named, it's for the next \
day the restaurant has an order, usually tomorrow: "10 more baguettes" is one \
"add" of 10 for that day, not one for every day. "The weekend" is the coming \
Saturday and Sunday. Quantities are whole items: round to the nearest, halves \
up. A number of people or guests is not a quantity of anything. If the message \
is unclear, asks for something these changes can't express, \
or you would have to guess a number, set "unclear" to true, leave out what \
you can't express, and say why in "note". Otherwise "note" is empty.

"reply" is a short, friendly answer to the restaurant from the bakery, in \
British English, saying what will change. It is sent only after a person \
at the bakery checks your changes.

There may be several messages, oldest first: read them together, as one \
request, a later one correcting an earlier one ("actually, make it 6"). If a \
person at the bakery asks for the changes drafted so far to be changed, do \
what they ask, keeping the rest."""


def _describe(change: Change, names: dict[str, str]) -> str:
    """Return a change as the reply says it: "2 extra baguettes on Tue 3 Nov"."""
    item = plural(names.get(change.sku, change.sku))
    day = label(date.fromisoformat(change.date))
    if change.mode == "add":
        more = "extra" if change.quantity >= 0 else "fewer"
        return f"{abs(change.quantity)} {more} {item} on {day}"
    if change.mode == "set-from":
        return f"{change.quantity} {item} from {day} on"
    if change.quantity == 0:
        return f"no {item} on {day}"
    return f"{change.quantity} {item} on {day}"


@layers.Wholesale
@Publisher("drafts.created", "drafts.outdated")
@Agent
class OrderDesk:
    """Reads a restaurant's messages and drafts the order change they ask for, with a reply.

    ``invoke(message_id)`` drafts for a message from Messages, together with
    the messages the restaurant's open draft answers already: a restaurant
    that writes again before its draft is confirmed ("actually, make it 6")
    gets one draft reading both, and the older draft is outdated, so the two
    can't both be sent. A message nobody drafted for (history caught up on,
    one a rejected draft put back) isn't folded in.
    ``invoke(message_id, instruction=...)`` drafts again with a person's
    instruction ("make it 30 croissants"), outdating the open draft the same
    way.

    The draft shows each product's quantity before and after, and the reply
    that confirming it sends. Rules read the usual phrasings; the model, if
    there is one, reads the rest; otherwise the draft waits for a person.
    """

    def __init__(
        self,
        clock: Clock,
        messages: Messages,
        products: Products,
        standing_orders: StandingOrders,
        order_changes: OrderChanges,
        drafts: Drafts,
        model: Model,
        notifications: Notifications,
    ) -> None:
        """Store what the agent reads and where it drafts.

        Args:
            clock: The demo clock, for when it drafted.
            messages: The messages it reads.
            products: The products a message can name.
            standing_orders: The restaurants' usual orders, for "before".
            order_changes: The changes already confirmed, for "before".
            drafts: Where it drafts.
            model: Asked for what the rules can't read.
            notifications: Bound to this agent.
        """
        self.clock, self.messages, self.products = clock, messages, products
        self.standing_orders, self.order_changes = standing_orders, order_changes
        self.drafts, self.model, self.notifications = drafts, model, notifications

    def invoke(self, message_id: int, instruction: str = "") -> dict:
        """Draft the order change message ``message_id`` asks for.

        A message the open draft already answers gets that draft back, not
        a second one, unless there's an ``instruction``.

        Args:
            message_id: The message's id in Messages.
            instruction: What a person wants changed in the open draft, such
                as "make it 30 croissants". Needs the model.

        Returns:
            ``{"draft", "status", "author", "changes", "reply"}``, and
            ``"outdated"``, the draft this one replaced, if any.

        Raises:
            KeyError: If there's no such message.
            ValueError: If there's an instruction but no model to read it.
        """
        found = self.messages.where("id", message_id)
        if not found:
            raise KeyError(f"no message {message_id}")
        message = found[0]
        if instruction and not self.model.available():
            raise ValueError("Drafting again from an instruction needs the model, and there's none")
        if message.restaurant is None:
            open_draft = self.drafts.open_for_message(message_id)
        else:
            open_draft = self.drafts.open_for_restaurant("order-change", message.restaurant)
        answered = open_draft is not None and (open_draft.message or 0) >= message_id
        if answered and not instruction:
            return self._result(open_draft)
        if message.restaurant is None:
            thread = [message]
        else:
            up_to = max(message_id, open_draft.message or 0) if open_draft else message_id
            thread = self.messages.unanswered(message.restaurant, up_to) or [message]
        draft = self._draft(thread, instruction, open_draft)
        self.drafts.save(draft)
        if open_draft is not None:
            self._outdate(open_draft, draft, instruction)
        for answered_message in thread:
            answered_message.status = "drafted"
            self.messages.save(answered_message)
        who = message.restaurant or message.sender
        waiting = "awaits confirmation" if draft.status == "pending" else "needs review"
        self.notifications.publish(
            "drafts.created",
            {"draft": draft.id, "kind": draft.kind, "status": draft.status},
            summary=f"Order change for {who} {waiting}",
            level="info" if draft.status == "pending" else "warning",
            subject=Drafts,
            record=draft.id,
        )
        result = self._result(draft)
        if open_draft is not None:
            result["outdated"] = open_draft.id
        return result

    def describe(self, draft: Draft) -> str:
        """Return ``draft``'s body again, from the messages it answers and its changes now.

        After a person edits a draft (see ``app.drafts.edit_draft``), its
        table and reply are redrawn from what they changed.
        """
        found = self.messages.where("id", draft.message) if draft.message else []
        if not found:
            return draft.body
        message = found[0]
        thread = (
            self.messages.unanswered(message.restaurant, message.id) or [message]
            if message.restaurant
            else [message]
        )
        names = {p.sku: p.name for p in self.products.all()}
        changes = [Change(**c) for c in json.loads(draft.changes)]
        return self._body(thread, changes, draft.reply, draft.author, draft.note, names)

    def _result(self, draft: Draft) -> dict:
        return {
            "draft": draft.id,
            "status": draft.status,
            "author": draft.author,
            "changes": json.loads(draft.changes),
            "reply": draft.reply,
        }

    def _outdate(self, old: Draft, new: Draft, instruction: str) -> None:
        """Mark ``old`` outdated by ``new``, and say so."""
        why = (
            f"Drafted again as draft {new.id}, as asked: {instruction}"
            if instruction
            else f"A newer message came in: draft {new.id} answers it too."
        )
        old.status, old.note = "outdated", why
        old.body = f"{old.body.rstrip()}\n\n**Outdated.** {why}\n"
        self.drafts.save(old)
        who = old.restaurant or "a sender"
        self.notifications.publish(
            "drafts.outdated",
            {"draft": old.id, "by": new.id},
            summary=f"Order change for {who} drafted again",
            subject=Drafts,
            record=old.id,
        )

    def _draft(
        self, thread: list[Message], instruction: str = "", previous: Draft | None = None
    ) -> Draft:
        """Read ``thread`` (oldest first) and return its draft, unsaved."""
        message = thread[-1]
        received = datetime.fromtimestamp(message.received_at).date()
        first_sent = datetime.fromtimestamp(thread[0].received_at).date()
        products = self.products.all()
        names = {p.sku: p.name for p in products}
        changes, reply, author, note = None, "", "nobody", ""
        read = [
            read_order_change(gist(m.text), products, datetime.fromtimestamp(m.received_at).date())
            for m in thread
        ]
        if message.restaurant is None:
            note = "It isn't from a restaurant on the restaurants sheet."
        elif not instruction and all(r is not None for r in read):
            changes = [c for r in read for c in r]
            author = "rules"
            reply = (
                "Thanks, that's noted: "
                + "; ".join(_describe(c, names) for c in changes)
                + ". See you in the morning!"
            )
        elif self.model.available():
            changes, reply, note = self._ask_model(thread, first_sent, instruction, previous)
            author = self.model.author
        else:
            note = (
                "The rules don't know this phrasing, and there's no model to read it. "
                "Edit this draft with the changes and a reply, or reply to it yourself "
                "and reject it."
            )
        status = "pending" if changes and not note else "needs-review"
        first = min((c.date for c in changes), default=None) if changes else None
        body = self._body(thread, changes or [], reply, author, note, names)
        if previous is not None and previous.author == "edited":
            edited = ", ".join(_describe(Change(**c), names) for c in json.loads(previous.changes))
            body += (
                f"\n**Draft {previous.id} had been edited** before this one replaced it: "
                f"{edited or 'no changes'}. Its reply: {previous.reply or '(none)'}\n"
            )
        return Draft(
            id=None,
            created_at=self.clock.now().timestamp(),
            kind="order-change",
            status=status,
            title=f"Order change for {message.restaurant or message.sender}",
            date=first or (received + timedelta(days=1)).isoformat(),
            restaurant=message.restaurant,
            message=message.id,
            changes=json.dumps([c.as_dict() for c in changes or []]),
            reply=reply,
            author=author,
            note=note,
            body=body,
        )

    def _ask_model(
        self,
        thread: list[Message],
        received: date,
        instruction: str = "",
        previous: Draft | None = None,
    ) -> tuple[list[Change] | None, str, str]:
        """Ask the model for ``thread``'s changes. Returns the changes, the reply and a note."""
        restaurant = thread[-1].restaurant
        products = self.products.all()
        week = []
        for offset in range(1, 8):
            day = received + timedelta(days=offset)
            usual = restaurant_orders(day, self.standing_orders, self.order_changes).get(
                restaurant, {}
            )
            items = ", ".join(f"{sku} {q}" for sku, q in usual.items()) or "nothing"
            week.append(f"- {day:%A} {day.isoformat()}: {items}")
        catalogue = "\n".join(
            f"- {p.sku}: {p.name}" for p in products if p.wholesale_price is not None
        )
        sent = []
        for m in thread:
            day = datetime.fromtimestamp(m.received_at).date()
            sent.append(f"Sent on {day:%A} {day.isoformat()} by {restaurant}:\n{m.text}")
        prompt = (
            f"Products:\n{catalogue}\n\n"
            f"{restaurant}'s order for the next seven days:\n"
            + "\n".join(week)
            + "\n\n"
            + "\n\n".join(sent)
        )
        if instruction:
            drafted = previous.changes if previous is not None else "[]"
            prompt += (
                f"\n\nThe changes drafted so far: {drafted}\n"
                f"A person at the bakery asks for them to be changed: {instruction}"
            )
        answer = self.model.ask(_ORDER_SYSTEM, prompt, _ORDER_SCHEMA)
        if not isinstance(answer, dict):
            return (
                None,
                "",
                "The model didn't answer. Edit this draft, or reply to it yourself and reject it.",
            )
        changes = check_changes(answer.get("changes"), products, received)
        note = str(answer.get("note") or "")
        if answer.get("unclear") or changes is None:
            note = note or "The model's changes didn't check out against the products and dates."
            note = f"The model wasn't sure: {note} Check the changes before confirming."
            return changes, str(answer.get("reply") or ""), note
        return changes, str(answer.get("reply") or ""), ""

    def _body(
        self,
        thread: list[Message],
        changes: list[Change],
        reply: str,
        author: str,
        note: str,
        names: dict[str, str],
    ) -> str:
        """Return the draft as a person reads it, in Markdown."""
        message = thread[-1]
        lines = [f"## Order change for {message.restaurant or message.sender}", ""]
        for m in thread:
            sent = datetime.fromtimestamp(m.received_at)
            lines += [
                "\n".join(f"> {line}" for line in m.text.splitlines() if line.strip()),
                "",
                f"*{m.channel.capitalize()}, {label(sent.date())} {sent:%H:%M}.*",
                "",
            ]
        read_by = "Edited by a person" if author == "edited" else f"Read by {author}"
        lines += [f"*{read_by}.*", ""]
        if note:
            lines += [f"**Needs review.** {note}", ""]
        if changes:
            lines += ["| Day | Product | Before | After |", "|---|---|---|---|"]
            for change in changes:
                day = date.fromisoformat(change.date)
                before, after = self._before_after(message.restaurant, change, day)
                every = " and after" if change.mode == "set-from" else ""
                lines.append(
                    f"| {label(day)}{every} | {names.get(change.sku, change.sku)} "
                    f"| {before} | **{after}** |"
                )
            lines.append("")
        if reply:
            lines += [f"**Reply**, sent when you confirm: {reply}", ""]
        return "\n".join(lines)

    def _before_after(self, restaurant: str | None, change: Change, day: date) -> tuple[int, int]:
        """Return how many of ``change``'s product ``restaurant`` takes on ``day``, then with it."""
        standing = self.standing_orders.for_weekday(f"{day:%A}")
        existing = self.order_changes.for_day(day)
        proposed = OrderChange(
            None,
            restaurant or "",
            change.sku,
            change.date,
            change.mode,
            change.quantity,
            None,
            None,
        )
        before = wholesale_order(standing, existing, day).get(restaurant, {}).get(change.sku, 0)
        after = (
            wholesale_order(standing, [*existing, proposed], day)
            .get(restaurant, {})
            .get(change.sku, 0)
        )
        return before, after


_SPECIALS_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"sku": {"type": "string"}, "line": {"type": "string"}},
                "required": ["sku", "line"],
            },
        }
    },
    "required": ["lines"],
}

_SPECIALS_SYSTEM = """You write the specials board for a bakery's café. For each \
special, write one short, appetising line (at most 15 words) describing the dish \
as given. Don't add ingredients, prices or claims that aren't in the description. \
British English. Answer with one line per SKU given."""


@layers.Cafe
@Publisher("drafts.created")
@Agent
class Specials:
    """Turns what the café didn't sell into tomorrow's specials board, as a draft.

    ``invoke(date)`` reads that day's Leftovers (``count-leftovers``) and
    drafts the next day's board: a special for each product with a few
    left. The rules pick the dishes and prices; the model, if there is one,
    only writes the board's lines.
    """

    def __init__(
        self,
        clock: Clock,
        leftovers: Leftovers,
        drafts: Drafts,
        model: Model,
        notifications: Notifications,
    ) -> None:
        """Store what the agent reads and where it drafts.

        Args:
            clock: The demo clock, for "today".
            leftovers: What the café didn't sell.
            drafts: Where it drafts.
            model: Asked to write the board's lines.
            notifications: Bound to this agent.
        """
        self.clock, self.leftovers, self.drafts = clock, leftovers, drafts
        self.model, self.notifications = model, notifications

    def invoke(self, date: str = "") -> dict:
        """Draft the specials board for the day after ``date``, from that day's leftovers.

        A board already waiting for that day is returned, not drafted again.

        Args:
            date: The day whose leftovers to use, ``"YYYY-MM-DD"``; today by default.

        Returns:
            ``{"draft", "specials"}``; ``"draft"`` is ``None`` if too little
            was left over for a special.
        """
        day = day_of(date, self.clock)
        board = day + timedelta(days=1)
        waiting = self.drafts.open_for("specials", board.isoformat())
        if waiting is not None:
            return {"draft": waiting.id, "specials": json.loads(waiting.changes)}
        specials = specials_for(self.leftovers.where("date", day.isoformat()))
        if not specials:
            return {"draft": None, "specials": []}
        author = "rules"
        if self.model.available():
            answer = self.model.ask(
                _SPECIALS_SYSTEM,
                "\n".join(f"- {s['sku']}: {s['dish']}, {s['description']}" for s in specials),
                _SPECIALS_SCHEMA,
            )
            lines = {}
            if isinstance(answer, dict) and isinstance(answer.get("lines"), list):
                lines = {
                    str(item.get("sku")): str(item.get("line", "")).strip()
                    for item in answer["lines"]
                    if isinstance(item, dict)
                }
            if all(lines.get(s["sku"]) for s in specials):
                for s in specials:
                    s["description"] = lines[s["sku"]]
                author = self.model.author
        rows = [
            f"| **{s['dish']}** | {s['description']} | £{s['price']:.2f} | {s['uses']} |"
            for s in specials
        ]
        body = "\n".join(
            [
                f"## Specials for {label(board)}",
                "",
                f"From what the café didn't sell on {label(day)}. Written by {author}.",
                "",
                "| Special | | Price | Uses |",
                "|---|---|---|---|",
                *rows,
                "",
                "Confirm it to put it on the board.",
            ]
        )
        draft = Draft(
            id=None,
            created_at=self.clock.now().timestamp(),
            kind="specials",
            status="pending",
            title=f"Specials for {label(board)}",
            date=board.isoformat(),
            restaurant=None,
            message=None,
            changes=json.dumps(specials),
            reply="",
            author=author,
            note="",
            body=body,
        )
        self.drafts.save(draft)
        self.notifications.publish(
            "drafts.created",
            {"draft": draft.id, "kind": "specials", "status": draft.status},
            summary=f"Specials for {label(board)} await confirmation",
            subject=Drafts,
            record=draft.id,
        )
        return {"draft": draft.id, "specials": specials}
