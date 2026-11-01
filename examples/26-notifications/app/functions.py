"""Taking an order, and the notifications it publishes."""

from opendataframework import Function, Notifications

from app.entities import Order
from app.repositories import Orders, Pantry

# What each menu item uses up, one portion of it.
MENU: dict[str, str] = {
    "flat white": "milk",
    "oat flat white": "oat milk",
    "croissant": "croissants",
}

# Portions left at which the pantry warns.
LOW_STOCK = 1


@Function
def take_order(
    table: int,
    item: str,
    orders: Orders,
    pantry: Pantry,
    notifications: Notifications,
) -> int | None:
    """Take an order for ``table`` and tell whoever's interested.

    Publishes ``orders.received`` for each order taken, ``pantry.low`` when an
    ingredient gets down to its last portion, and ``pantry.out`` (refusing
    the order) when there's none left. Each has a ``summary``, so the UI
    shows it. ``kitchen.ticket`` has none: it's for the ``Kitchen``
    component only.

    Args:
        table: The table the order is for.
        item: What was ordered, a key of ``MENU``.
        orders: Where the order is saved, injected by the ``Context``.
        pantry: The ingredients it uses up, injected by the ``Context``.
        notifications: Bound to this function's key, injected by the
            ``Context``.

    Returns:
        The order's id, or ``None`` if it couldn't be made.
    """
    supply = pantry.get(MENU[item])
    if supply.stock == 0:
        notifications.publish(
            "pantry.out",
            {"ingredient": supply.name, "table": table, "item": item},
            summary=f"Out of {supply.name}: table {table}'s {item} not taken",
            level="error",
            subject=Pantry,
            record=supply.id,
        )
        return None

    supply.stock -= 1
    pantry.save(supply)
    order = Order(id=None, table=table, item=item)
    orders.save(order)

    notifications.publish(
        "orders.received",
        {"table": table, "item": item},
        summary=f"Table {table}: {item}",
        subject=Orders,
        record=order.id,
    )
    notifications.publish("kitchen.ticket", {"order": order.id, "table": table, "item": item})
    if supply.stock <= LOW_STOCK:
        left = f"{supply.stock} left" if supply.stock else "the last used"
        notifications.publish(
            "pantry.low",
            {"ingredient": supply.name, "stock": supply.stock},
            summary=f"{supply.name.capitalize()} running low: {left}",
            level="warning",
            subject=Pantry,
            record=supply.id,
        )
    return order.id
