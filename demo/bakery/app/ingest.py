"""Taking things in from the tools: one call per item, saving it and telling whoever's interested.

Every way data arrives (a webhook, the mailbox, a sheet changing) hands each
item to one of these functions instead of handling it inside its own loop. So
each item is a call of its own: it's logged, it shows on the topology, and the
notification it publishes records that call as its ``parent``.
"""

import threading
from datetime import datetime
from functools import partial

from opendataframework import Function, Notifications, Publisher

from app.clients import Drive
from app.entities import (
    CafeSale,
    Contract,
    Ingredient,
    IngredientAllergen,
    Invoice,
    Message,
    Product,
    RecipeLine,
    Restaurant,
    StandingOrder,
)
from app.repositories import (
    Allergens,
    CafeSales,
    Contracts,
    Ingredients,
    Invoices,
    Messages,
    Products,
    Recipes,
    Restaurants,
    StandingOrders,
)

# One import of the sheets at a time: two at once would interleave their rows.
_IMPORTING = threading.Lock()

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


@Publisher("messages.received")
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


@Publisher("pos.sale")
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


@Publisher("sheets.changed")
@Function
def import_sheets(
    drive: Drive,
    products: Products,
    restaurants: Restaurants,
    standing_orders: StandingOrders,
    contracts: Contracts,
    ingredients: Ingredients,
    recipes: Recipes,
    allergens: Allergens,
    messages: Messages,
    notifications: Notifications,
    announce: bool = True,
) -> dict:
    """Read the shared drive's sheets into the bakery's repositories, replacing what was there.

    The sheets are where the owner keeps this data, so they win. Messages are
    then matched to the restaurants again, so a message that came in before
    its restaurant was on the sheet is linked to it now. A sheet that isn't
    on the drive leaves its records as they are, so a drive that's away for a
    moment doesn't empty the bakery; an empty sheet does empty them. Publishes
    ``sheets.changed``, unless no sheet was there.

    Args:
        drive: The shared drive, injected.
        products: Replaced from ``products.csv``, injected.
        restaurants: Replaced from ``restaurants.csv``, injected.
        standing_orders: Replaced from ``standing_orders.csv``, injected.
        contracts: Replaced from ``contracts.csv``, injected.
        ingredients: Replaced from ``ingredients.csv``, injected.
        recipes: Replaced from ``recipes.csv``, injected.
        allergens: The sheet's replaced from ``allergens.csv``; those an
            invoice declared are kept, injected.
        messages: Matched to the restaurants again, injected.
        notifications: Bound to this function, injected.
        announce: ``False`` while onboarding: imported, not announced.

    Returns:
        How many rows each sheet on the drive had.
    """
    with _IMPORTING:
        return _import_sheets(
            drive, products, restaurants, standing_orders, contracts, ingredients, recipes,
            allergens, messages, notifications, announce,
        )  # fmt: skip


def _import_sheets(
    drive: Drive,
    products: Products,
    restaurants: Restaurants,
    standing_orders: StandingOrders,
    contracts: Contracts,
    ingredients: Ingredients,
    recipes: Recipes,
    allergens: Allergens,
    messages: Messages,
    notifications: Notifications,
    announce: bool,
) -> dict:
    """Do ``import_sheets``' work, under its lock."""
    # What each sheet's rows are called, its file, where they go, and how a row reads.
    sheets = [
        ("products", "products.csv", products.replace_all, lambda r: Product(
            r["sku"], r["name"], r["kind"], float(r["cafe_price"]), _price(r["wholesale_price"])
        )),
        ("restaurants", "restaurants.csv", restaurants.replace_all, lambda r: Restaurant(
            None, r["name"], r["phone"], r["email"], r["address"], float(r["lat"]),
            float(r["lon"]), r["kitchen_opens"],
        )),
        ("standing orders", "standing_orders.csv", standing_orders.replace_all,
         lambda r: StandingOrder(None, r["restaurant"], r["weekday"], r["sku"],
                                 int(r["quantity"]))),
        ("contract prices", "contracts.csv", contracts.replace_all, lambda r: Contract(
            None, r["restaurant"], r["sku"], float(r["price"]), r["valid_until"]
        )),
        ("ingredients", "ingredients.csv", ingredients.replace_all, lambda r: Ingredient(
            r["code"], r["name"], r["unit"], r["supplier"], r["invoice_name"], float(r["price"])
        )),
        ("recipe lines", "recipes.csv", recipes.replace_all, lambda r: RecipeLine(
            None, r["sku"], r["ingredient"], float(r["quantity"])
        )),
        # Those an invoice declared are kept: only the sheet's own are replaced.
        ("allergens", "allergens.csv", partial(allergens.replace_where, "source", "sheet"),
         lambda r: IngredientAllergen(None, r["ingredient"], r["allergen"], r["kind"], "sheet",
                                      0.0)),
    ]  # fmt: skip
    on_drive = drive.versions()
    counts = {
        what: store(read(r) for r in drive.rows(sheet))
        for what, sheet, store, read in sheets
        if sheet in on_drive
    }
    missing = [sheet for _, sheet, _, _ in sheets if sheet not in on_drive]
    if counts:
        messages.match_restaurants(restaurants.all())
    if announce and counts:
        summary = "Sheets updated: " + ", ".join(f"{n} {what}" for what, n in counts.items())
        notifications.publish(
            "sheets.changed",
            counts,
            summary=summary + (f"; not on the drive: {', '.join(missing)}" if missing else ""),
            subject=Products,
        )
    return counts


@Publisher("invoices.received")
@Function
def ingest_invoice(
    external_id: str,
    sender: str,
    supplier: str,
    subject: str,
    filename: str,
    pdf: bytes,
    received_at: float,
    invoices: Invoices,
    notifications: Notifications,
    announce: bool = True,
) -> int | None:
    """Take in a supplier's invoice, the PDF attached to its email, once.

    Publishes ``invoices.received`` with a summary such as ``"Vale Dairy:
    Invoice VAL-2026-0012"``, about the saved invoice. Reading it is the
    invoice-clerk's job.

    Args:
        external_id: The email's ``Message-ID``.
        sender: The address it came from.
        supplier: Who sent it, as the email names them.
        subject: The email's subject.
        filename: The attachment's name.
        pdf: The attachment.
        received_at: When it was sent, as a Unix time.
        invoices: Where it's saved, injected.
        notifications: Bound to this function, injected.
        announce: ``False`` while catching up on history: saved, not announced.

    Returns:
        The saved invoice's id, or ``None`` if it had been taken in already.
    """
    if invoices.by_external_id(external_id) is not None:
        return None
    invoice = Invoice(
        id=None,
        received_at=received_at,
        supplier=supplier,
        sender=sender,
        subject=subject,
        number=None,
        date=None,
        total=None,
        status="new",
        external_id=external_id,
        filename=filename,
        pdf=pdf,
    )
    invoices.save(invoice)
    if announce:
        notifications.publish(
            "invoices.received",
            {"invoice": invoice.id, "supplier": supplier},
            summary=f"{supplier}: {subject}",
            subject=Invoices,
            record=invoice.id,
        )
    return invoice.id
