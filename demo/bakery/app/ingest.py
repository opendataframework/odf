"""Taking things in from the tools: one call per item, saving it and telling whoever's interested.

Every way data arrives (a webhook, the mailbox, a sheet changing) hands each
item to one of these functions instead of handling it inside its own loop. So
each item is a call of its own: it's logged, it shows on the topology, and the
notification it publishes records that call as its ``parent``.
"""

from datetime import datetime

from opendataframework import Function, Notifications

from app.clients import Drive
from app.entities import CafeSale, Contract, Message, Product, Restaurant, StandingOrder
from app.repositories import CafeSales, Contracts, Messages, Products, Restaurants, StandingOrders

# Lines that are only a greeting, as an email's first line usually is.
_GREETINGS = ("hi", "hello", "hey", "morning", "good morning", "good evening")


def _is_greeting(line: str) -> bool:
    """Return whether ``line`` only greets: "Hi,", "Hello!", "Dear Sam," and the like."""
    bare = line.rstrip(",!.").lower()
    return line.endswith(",") or bare in _GREETINGS or bare.startswith("dear ")


def gist(text: str) -> str:
    """Return the line of ``text`` that says what it's about: the first that isn't a greeting."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return next((line for line in lines if not _is_greeting(line)), lines[0] if lines else "")


@Function
def ingest_message(
    channel: str,
    external_id: str,
    sender: str,
    text: str,
    received_at: float,
    messages: Messages,
    restaurants: Restaurants,
    notifications: Notifications,
    subject: str = "",
    announce: bool = True,
) -> int | None:
    """Take in a message from a restaurant (or anyone), once.

    Publishes ``messages.received`` with a summary such as ``"Le Petit: 2 extra
    baguettes tomorrow please"``, about the saved message.

    Args:
        channel: ``"messenger"`` or ``"email"``.
        external_id: Its id in the tool it came from.
        sender: The phone number or email address it came from.
        text: What it says.
        received_at: When it was sent, as a Unix time.
        messages: Where it's saved, injected.
        restaurants: To tell which restaurant sent it, injected.
        notifications: Bound to this function, injected.
        subject: An email's subject.
        announce: ``False`` while catching up on history: saved, not announced.

    Returns:
        The saved message's id, or ``None`` if it had been taken in already.
    """
    if messages.by_external_id(external_id) is not None:
        return None
    restaurant = restaurants.by_contact(sender)
    message = Message(
        id=None,
        received_at=received_at,
        channel=channel,
        sender=sender,
        restaurant=restaurant.name if restaurant else None,
        subject=subject or None,
        text=text.strip(),
        external_id=external_id,
    )
    messages.save(message)
    if announce:
        who = message.restaurant or sender
        first_line = gist(message.text)
        notifications.publish(
            "messages.received",
            {"message": message.id, "channel": channel, "restaurant": message.restaurant},
            summary=f"{who}: {first_line[:90]}",
            subject=Messages,
            record=message.id,
        )
    return message.id


def sale_lines(order: dict) -> list[CafeSale]:
    """Return a POS order's lines as ``CafeSale``s."""
    sold_at = datetime.fromisoformat(order["created_at"]).timestamp()
    return [
        CafeSale(
            id=None,
            sold_at=sold_at,
            order_id=order["id"],
            sku=line["sku"],
            product=line["name"],
            quantity=int(line["quantity"]),
            revenue=round(line["quantity"] * line["unit_price"], 2),
        )
        for line in order["line_items"]
    ]


@Function
def ingest_sale(order: dict, sales: CafeSales, notifications: Notifications) -> bool:
    """Take in a café order from the POS, once.

    Publishes ``pos.sale`` with no summary: a sale every few minutes is for
    components (a forecast, a stock count), not a notice for people.

    Args:
        order: The order, as the POS API and webhooks give it.
        sales: Where its lines are saved, injected.
        notifications: Bound to this function, injected.

    Returns:
        Whether it was new.
    """
    if sales.has_order(order["id"]):
        return False
    sales.save_many(sale_lines(order))
    notifications.publish(
        "pos.sale",
        {
            "order": order["id"],
            "total": order["total"],
            "items": {line["sku"]: line["quantity"] for line in order["line_items"]},
        },
    )
    return True


def _price(value: str) -> float | None:
    """Return a price cell as a float, or ``None`` if it's empty."""
    return float(value) if value.strip() else None


@Function
def import_sheets(
    drive: Drive,
    products: Products,
    restaurants: Restaurants,
    standing_orders: StandingOrders,
    contracts: Contracts,
    notifications: Notifications,
    announce: bool = True,
) -> dict:
    """Read the shared drive's sheets into the bakery's repositories, replacing what was there.

    The sheets are where the owner keeps this data, so they win. Publishes
    ``sheets.changed``.

    Args:
        drive: The shared drive, injected.
        products: Replaced from ``products.csv``, injected.
        restaurants: Replaced from ``restaurants.csv``, injected.
        standing_orders: Replaced from ``standing_orders.csv``, injected.
        contracts: Replaced from ``contracts.csv``, injected.
        notifications: Bound to this function, injected.
        announce: ``False`` while onboarding: imported, not announced.

    Returns:
        How many rows each sheet had.
    """
    counts = {
        "products": products.replace_all(
            Product(
                r["sku"], r["name"], r["kind"], float(r["cafe_price"]), _price(r["wholesale_price"])
            )
            for r in drive.rows("products.csv")
        ),
        "restaurants": restaurants.replace_all(
            Restaurant(
                None,
                r["name"],
                r["phone"],
                r["email"],
                r["address"],
                float(r["lat"]),
                float(r["lon"]),
                r["kitchen_opens"],
            )
            for r in drive.rows("restaurants.csv")
        ),
        "standing orders": standing_orders.replace_all(
            StandingOrder(None, r["restaurant"], r["weekday"], r["sku"], int(r["quantity"]))
            for r in drive.rows("standing_orders.csv")
        ),
        "contract prices": contracts.replace_all(
            Contract(None, r["restaurant"], r["sku"], float(r["price"]), r["valid_until"])
            for r in drive.rows("contracts.csv")
        ),
    }
    if announce:
        notifications.publish(
            "sheets.changed",
            counts,
            summary="Sheets updated: " + ", ".join(f"{n} {what}" for what, n in counts.items()),
            subject=Products,
        )
    return counts
