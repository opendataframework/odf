"""Confirming or rejecting what an agent drafted: the step that keeps a person in charge.

Confirming an order change is the only way one reaches the bake sheet, and
the only way the agent's reply reaches the restaurant.
"""

import json
from collections.abc import Callable
from typing import Annotated

from opendataframework import Function, Notifications

from app.clients import Mail, Messenger
from app.entities import OrderChange
from app.planning import bake_sheet, plan_deliveries
from app.repositories import BakeSheets, Drafts, Messages, OrderChanges


@Function
def confirm_draft(
    draft_id: int,
    drafts: Drafts,
    messages: Messages,
    order_changes: OrderChanges,
    sheets: BakeSheets,
    messenger: Messenger,
    mail: Mail,
    notifications: Notifications,
    rebake: Annotated[Callable[..., list], bake_sheet],
    replan: Annotated[Callable[..., list], plan_deliveries],
) -> dict:
    """Confirm a draft: an order change is applied and its reply sent; specials go on the board.

    The reply goes back the way the message came: by messenger, or by email.
    It's sent first, so a reply that can't be sent leaves the draft as it
    was. A bake sheet already worked out for a day the change touches is
    worked out again, with its delivery run.

    Args:
        draft_id: The draft's id in Drafts.
        drafts: The drafts, injected.
        messages: The message it answers, injected.
        order_changes: Where the changes go, injected.
        sheets: Which days have a bake sheet already, injected.
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
    draft.status = "confirmed"
    drafts.save(draft)
    done = {"order-change": "applied", "specials": "on the board"}.get(draft.kind, "confirmed")
    sent = f", reply sent by {replied}" if replied else ""
    notifications.publish(
        "drafts.confirmed",
        {"draft": draft.id, "kind": draft.kind, "rebaked": rebaked},
        summary=f"{draft.title}: {done}{sent}",
        level="success",
        subject=Drafts,
        record=draft.id,
    )
    return {"draft": draft.id, "changes": changes, "replied": replied, "rebaked": rebaked}


@Function
def reject_draft(
    draft_id: int,
    drafts: Drafts,
    messages: Messages,
    notifications: Notifications,
    reason: str = "",
) -> dict:
    """Reject a draft: nothing is applied or sent, and its message is back to new.

    Args:
        draft_id: The draft's id in Drafts.
        drafts: The drafts, injected.
        messages: The message it answers, injected.
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
    notifications.publish(
        "drafts.rejected",
        {"draft": draft.id, "kind": draft.kind, "reason": reason},
        summary=f"{draft.title}: rejected" + (f" ({reason})" if reason else ""),
        subject=Drafts,
        record=draft.id,
    )
    return {"draft": draft.id, "status": draft.status}
