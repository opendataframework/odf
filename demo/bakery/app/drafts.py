"""Confirming or rejecting what an agent drafted: the step that keeps a person in charge.

Confirming an order change is the only way one reaches the bake sheet, and
the only way the agent's reply reaches the restaurant. Confirming an
invoice's reading records its prices; confirming new prices emails them to
the restaurant.
"""

import json
from collections.abc import Callable
from datetime import date
from typing import Annotated

from opendataframework import Function, Notifications, Publisher

from app.clients import Mail, Messenger
from app.entities import OrderChange
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
    Restaurants,
)


@Publisher("drafts.confirmed", "prices.changed")
@Function
def confirm_draft(
    draft_id: int,
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
) -> dict:
    """Confirm a draft: whatever it prepared happens.

    - An order change is applied, and its reply sent the way the message
      came: by messenger, or by email. The reply is sent first, so one that
      can't be sent leaves the draft as it was. A bake sheet already worked
      out for a day the change touches is worked out again, with its
      delivery run.
    - Specials go on the board.
    - An invoice's reading has its prices recorded, and ``prices.changed``
      published.
    - New prices are emailed to the restaurant.

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

    Returns:
        ``{"draft", "changes", "replied", "rebaked"}``.

    Raises:
        KeyError: If there's no such draft.
        ValueError: If it isn't pending: it needs review, or was confirmed or
            rejected already.
    """
    draft = drafts.get(draft_id)
    if draft.status != "pending":
        detail = f": {draft.note}" if draft.note else ""
        raise ValueError(f"draft {draft_id} is {draft.status}, not pending{detail}")
    changes = json.loads(draft.changes)
    replied, rebaked = None, []
    if draft.kind == "order-change":
        message = messages.where("id", draft.message)[0] if draft.message else None
        if message is not None and draft.reply:
            if message.channel == "email":
                subject = f"Re: {message.subject or 'Order change'}"
                mail.send(message.sender, subject, draft.reply)
            else:
                messenger.send(message.sender, draft.reply)
            replied = message.channel
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
        if message is not None:
            message.status = "done"
            messages.save(message)
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
        mail.send(found[0].email, f"Our prices from {label(_day(draft.date))}", draft.reply)
        replied = "email"
    draft.status = "confirmed"
    drafts.save(draft)
    done = {
        "order-change": "applied",
        "specials": "on the board",
        "invoice": "prices recorded",
        "renegotiation": "emailed",
    }.get(draft.kind, "confirmed")
    sent = f", reply sent by {replied}" if replied and draft.kind == "order-change" else ""
    notifications.publish(
        "drafts.confirmed",
        {"draft": draft.id, "kind": draft.kind, "rebaked": rebaked},
        summary=f"{draft.title}: {done}{sent}",
        level="success",
        subject=Drafts,
        record=draft.id,
    )
    return {"draft": draft.id, "changes": changes, "replied": replied, "rebaked": rebaked}


@Publisher("drafts.rejected")
@Function
def reject_draft(
    draft_id: int,
    drafts: Drafts,
    messages: Messages,
    invoices: Invoices,
    notifications: Notifications,
    reason: str = "",
) -> dict:
    """Reject a draft: nothing is applied or sent, and its message is back to new.

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
        ValueError: If it was confirmed or rejected already.
    """
    draft = drafts.get(draft_id)
    if draft.status not in Drafts.OPEN:
        raise ValueError(f"draft {draft_id} is {draft.status} already")
    draft.status, draft.note = "rejected", reason or draft.note
    drafts.save(draft)
    if draft.message:
        for message in messages.where("id", draft.message):
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


def _day(value: str) -> date:
    """Return a draft's ``"YYYY-MM-DD"`` date."""
    return date.fromisoformat(value)
