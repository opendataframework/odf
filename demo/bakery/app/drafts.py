"""Confirming, editing or rejecting what an agent drafted: the step that keeps a person in charge.

Confirming an order change is the only way one reaches the bake sheet, and
the only way the agent's reply reaches the restaurant. Confirming an
invoice's reading records its prices; confirming new prices emails them to
the restaurant. What's sent is saved in Messages as the bakery's side of the
restaurant's thread.

Each function takes the draft as ``Annotated[int, Record(Drafts)]``, so the
chat shows them as actions on a draft's card in its restaurant's thread, with
the reply and changes filled in to edit first.
"""

import json
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated

from opendataframework import Function, Notifications, Publisher, Record

from app import layers
from app.agents import OrderDesk
from app.clients import Clock, Mail, Messenger
from app.entities import Draft, Message, OrderChange
from app.planning import bake_sheet, label, plan_deliveries
from app.purchasing import announce_prices, record_prices
from app.repositories import (
    BakeSheets,
    Drafts,
    IngredientPrices,
    Ingredients,
    Invoices,
    Messages,
    OrderChanges,
    Products,
    Restaurants,
)
from app.rules import check_changes


@layers.Drafts
@Publisher("drafts.confirmed", "prices.changed")
@Function
def confirm_draft(
    draft_id: Annotated[int, Record(Drafts)],
    drafts: Drafts,
    messages: Messages,
    order_changes: OrderChanges,
    sheets: BakeSheets,
    restaurants: Restaurants,
    invoices: Invoices,
    ingredients: Ingredients,
    prices: IngredientPrices,
    messenger: Messenger,
    mail: Mail,
    notifications: Notifications,
    rebake: Annotated[Callable[..., list], bake_sheet],
    replan: Annotated[Callable[..., list], plan_deliveries],
    clock: Clock,
    order_desk: OrderDesk,
    products: Products,
    reply: str | None = None,
    changes: list[dict] | None = None,
) -> dict:
    """Confirm a draft: whatever it prepared happens.

    A ``reply`` or ``changes`` given here are the draft's from now on, as
    ``edit_draft`` makes them, so what's sent is what the record shows.

    - An order change is applied, and its reply sent the way the message
      came: by messenger, or by email. The reply is sent first, so one that
      can't be sent leaves the draft as it was. A bake sheet already worked
      out for a day the change touches is worked out again, with its
      delivery run.
    - Specials go on the board.
    - An invoice's reading has its prices recorded, and ``prices.changed``
      published.
    - New prices are emailed to the restaurant.
    - An allergen notice is emailed to each restaurant it's for.

    What's sent is saved in Messages, going out. Every message the draft
    answers is marked done.

    Args:
        draft_id: The draft's id in Drafts.
        drafts: The drafts, injected.
        messages: The message it answers, injected.
        order_changes: Where the changes go, injected.
        sheets: Which days have a bake sheet already, injected.
        restaurants: Where new prices are emailed, injected.
        invoices: The invoice a reading is of, injected.
        ingredients: The ingredients an invoice's lines are, injected.
        prices: Where an invoice's prices go, injected.
        messenger: Sends a chat reply, injected.
        mail: Sends an email reply, injected.
        notifications: Bound to this function, injected.
        rebake: ``bake_sheet``, injected.
        replan: ``plan_deliveries``, injected.
        clock: When what's sent was sent, injected.
        order_desk: Redraws an edited order change, injected.
        products: What edited changes are checked against, injected.
        reply: The reply to send instead of the drafted one.
        changes: An order change's changes to apply instead of the drafted
            ones: ``[{"sku", "date", "mode", "quantity"}]``.

    Returns:
        ``{"draft", "changes", "replied", "rebaked"}``.

    Raises:
        KeyError: If there's no such draft.
        ValueError: If it isn't pending: it needs review, or was confirmed,
            rejected or outdated already. Or the edit doesn't check out.
    """
    draft = drafts.get(draft_id)
    if draft.status not in Drafts.OPEN:
        raise ValueError(f"draft {draft_id} is {draft.status}, not pending")
    _edit(draft, reply, changes, messages, products, order_desk)
    if draft.status != "pending":
        detail = f": {draft.note}" if draft.note else ""
        raise ValueError(f"draft {draft_id} is {draft.status}, not pending{detail}")
    answered = _answered(draft, messages)
    changes = json.loads(draft.changes)
    replied, rebaked, sent = None, [], []
    if draft.kind == "order-change":
        message = messages.where("id", draft.message)[0] if draft.message else None
        if message is not None and draft.reply:
            subject = None
            if message.channel == "email":
                subject = f"Re: {message.subject or 'Order change'}"
                mail.send(message.sender, subject, draft.reply)
            else:
                messenger.send(message.sender, draft.reply)
            replied = message.channel
            sent.append((message.channel, message.sender, draft.restaurant, subject, draft.reply))
        for change in changes:
            order_changes.save(
                OrderChange(
                    id=None,
                    restaurant=draft.restaurant or "",
                    sku=change["sku"],
                    date=change["date"],
                    mode=change["mode"],
                    quantity=int(change["quantity"]),
                    message=draft.message,
                    draft=draft.id,
                )
            )
        for day in sheets.dates():
            touched = any(
                c["date"] == day or (c["mode"] == "set-from" and c["date"] <= day) for c in changes
            )
            if touched:
                rebake(date=day)
                replan(date=day)
                rebaked.append(day)
    elif draft.kind == "invoice":
        invoice = invoices.get(changes["invoice"])
        recorded = record_prices(invoice, changes["lines"], ingredients, prices, invoices)
        announce_prices(notifications, invoice, recorded)
    elif draft.kind == "renegotiation":
        found = restaurants.where("name", draft.restaurant)
        if not found:
            raise ValueError(f"{draft.restaurant} isn't on the restaurants sheet any more")
        subject = f"Our prices from {label(_day(draft.date))}"
        mail.send(found[0].email, subject, draft.reply)
        replied = "email"
        sent.append(("email", found[0].email, draft.restaurant, subject, draft.reply))
    elif draft.kind == "allergen-notice":
        missing = [n["restaurant"] for n in changes["notices"] if not n["email"]]
        if missing:
            raise ValueError(f"no email address for {', '.join(missing)}")
        for notice in changes["notices"]:
            mail.send(notice["email"], notice["subject"], notice["text"])
            sent.append(
                ("email", notice["email"], notice["restaurant"], notice["subject"], notice["text"])
            )
        replied = "email"
    for message in answered:
        message.status = "done"
        messages.save(message)
    now = clock.now().timestamp()
    for n, (channel, to, restaurant, subject, text) in enumerate(sent, start=1):
        messages.save(
            Message(
                id=None,
                received_at=now,
                channel=channel,
                sender=to,
                restaurant=restaurant,
                subject=subject,
                text=text,
                external_id=f"sent:draft-{draft.id}:{n}",
                status="sent",
                direction="out",
            )
        )
    done = {
        "order-change": "applied",
        "specials": "on the board",
        "invoice": "prices recorded",
        "renegotiation": "emailed",
    }.get(draft.kind, "confirmed")
    if draft.kind == "allergen-notice":
        done = f"{len(changes['notices'])} notices emailed"
    by = f", reply sent by {replied}" if replied and draft.kind == "order-change" else ""
    draft.status = "confirmed"
    _close(draft, f"**Confirmed**: {done}{by}.")
    drafts.save(draft)
    notifications.publish(
        "drafts.confirmed",
        {"draft": draft.id, "kind": draft.kind, "rebaked": rebaked},
        summary=f"{draft.title}: {done}{by}",
        level="success",
        subject=Drafts,
        record=draft.id,
    )
    return {"draft": draft.id, "changes": changes, "replied": replied, "rebaked": rebaked}


@layers.Drafts
@Publisher("drafts.rejected")
@Function
def reject_draft(
    draft_id: Annotated[int, Record(Drafts)],
    drafts: Drafts,
    messages: Messages,
    invoices: Invoices,
    notifications: Notifications,
    reason: str = "",
) -> dict:
    """Reject a draft: nothing is applied or sent, and the messages it answers are back to new.

    An invoice whose reading is rejected is marked rejected: its prices
    aren't recorded.

    Args:
        draft_id: The draft's id in Drafts.
        drafts: The drafts, injected.
        messages: The message it answers, injected.
        invoices: The invoice a reading is of, injected.
        notifications: Bound to this function, injected.
        reason: Why, kept on the draft.

    Returns:
        ``{"draft", "status"}``.

    Raises:
        KeyError: If there's no such draft.
        ValueError: If it was confirmed, rejected or outdated already.
    """
    draft = drafts.get(draft_id)
    if draft.status not in Drafts.OPEN:
        raise ValueError(f"draft {draft_id} is {draft.status} already")
    answered = _answered(draft, messages)
    draft.status, draft.note = "rejected", reason or draft.note
    _close(draft, "**Rejected**" + (f": {reason}." if reason else "."))
    drafts.save(draft)
    for message in answered:
        message.status = "new"
        messages.save(message)
    if draft.kind == "invoice":
        invoice = invoices.get(json.loads(draft.changes)["invoice"])
        invoice.status = "rejected"
        invoices.save(invoice)
    notifications.publish(
        "drafts.rejected",
        {"draft": draft.id, "kind": draft.kind, "reason": reason},
        summary=f"{draft.title}: rejected" + (f" ({reason})" if reason else ""),
        subject=Drafts,
        record=draft.id,
    )
    return {"draft": draft.id, "status": draft.status}


@layers.Drafts
@Publisher("drafts.edited")
@Function
def edit_draft(
    draft_id: Annotated[int, Record(Drafts)],
    drafts: Drafts,
    messages: Messages,
    products: Products,
    order_desk: OrderDesk,
    notifications: Notifications,
    reply: str | None = None,
    changes: list[dict] | None = None,
) -> dict:
    """Change a draft's reply, or an order change's changes, without sending anything.

    The draft's author becomes "edited", and its body is redrawn with the
    edit, so what's confirmed later is what a person checked. An order
    change that needed review and is given changes that check out is ready
    to confirm. An order change outdated by a newer message says, in the
    draft that replaced it, that it had been edited.

    Args:
        draft_id: The draft's id in Drafts.
        drafts: The drafts, injected.
        messages: The messages it answers, injected.
        products: What the changes are checked against, injected.
        order_desk: Redraws an order change, injected.
        notifications: Bound to this function, injected.
        reply: The reply confirming it will send.
        changes: An order change's changes: ``[{"sku", "date", "mode",
            "quantity"}]``, each for a baked product, within four weeks of
            the message, ``mode`` being ``"add"``, ``"set"`` or ``"set-from"``.

    Returns:
        ``{"draft", "status", "changes", "reply"}``.

    Raises:
        KeyError: If there's no such draft.
        ValueError: If it isn't open, there's nothing to change, or the
            changes don't check out.
    """
    draft = drafts.get(draft_id)
    if draft.status not in Drafts.OPEN:
        raise ValueError(f"draft {draft_id} is {draft.status} already")
    if not _edit(draft, reply, changes, messages, products, order_desk):
        raise ValueError("nothing to change: give a reply or changes unlike the draft's")
    drafts.save(draft)
    notifications.publish(
        "drafts.edited",
        {"draft": draft.id, "kind": draft.kind, "status": draft.status},
        summary=f"{draft.title}: edited",
        subject=Drafts,
        record=draft.id,
    )
    return {
        "draft": draft.id,
        "status": draft.status,
        "changes": json.loads(draft.changes),
        "reply": draft.reply,
    }


def _edit(
    draft: Draft,
    reply: str | None,
    changes: list[dict] | None,
    messages: Messages,
    products: Products,
    order_desk: OrderDesk,
) -> bool:
    """Apply a person's edit to ``draft``, unsaved. Returns whether it changed.

    A reply or changes the same as the draft's are no edit: a form filled in
    from the draft sends them as they are. Changes given for an order change
    that needs review are its review, though, edited or not: once they check
    out, it's ready to confirm.

    Raises:
        ValueError: If the draft's kind can't take the edit, or the changes
            don't check out.
    """
    edited = reviewed = False
    if changes is not None:
        same = changes == json.loads(draft.changes)
        if not same and draft.kind != "order-change":
            raise ValueError(f"a {draft.kind} draft's changes can't be edited, only its reply")
        if draft.kind == "order-change":
            checked = check_changes(changes, products.all(), _received(draft, messages))
            if checked is None:
                raise ValueError(
                    "the changes don't check out: each needs a baked product's sku, a day "
                    "from the message's to four weeks on, a mode (add, set or set-from) and "
                    "a quantity (only add can be negative)"
                )
            if not same:
                draft.changes = json.dumps([c.as_dict() for c in checked])
                draft.date = min(c.date for c in checked)
                edited = True
            if draft.status == "needs-review" and draft.restaurant:
                draft.status, draft.note = "pending", ""
                reviewed = True
    if reply is not None and reply.strip() != draft.reply.strip():
        if draft.kind not in ("order-change", "renegotiation"):
            raise ValueError(f"a {draft.kind} draft has no reply to edit")
        draft.reply = reply.strip()
        edited = True
    if not (edited or reviewed):
        return False
    if edited:
        draft.author = "edited"
    if draft.kind == "order-change":
        draft.body = order_desk.describe(draft)
    else:
        quoted = "\n".join(f"> {line}" if line else ">" for line in draft.reply.splitlines())
        draft.body = f"{draft.body.rstrip()}\n\n**Reply edited** before sending:\n\n{quoted}\n"
    return True


def _answered(draft: Draft, messages: Messages) -> list[Message]:
    """Return the messages ``draft`` answers: its own, and the restaurant's unanswered before it."""
    if not draft.message:
        return []
    found = messages.where("id", draft.message)
    if not found:
        return []
    message = found[0]
    if not message.restaurant:
        return [message]
    return messages.unanswered(message.restaurant, message.id) or [message]


def _received(draft: Draft, messages: Messages) -> date:
    """Return the day the message ``draft`` answers was sent, or the day it was drafted."""
    found = messages.where("id", draft.message) if draft.message else []
    sent = found[0].received_at if found else draft.created_at
    return datetime.fromtimestamp(sent).date()


def _close(draft: Draft, line: str) -> None:
    """Add how ``draft`` was closed to its body, so its card says so."""
    draft.body = f"{draft.body.rstrip()}\n\n{line}\n"


def _day(value: str) -> date:
    """Return a draft's ``"YYYY-MM-DD"`` date."""
    return date.fromisoformat(value)
