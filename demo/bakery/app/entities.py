"""What the bakery keeps track of. Each entity's first field is its key."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Product:
    """Something the bakery makes or serves, from the products sheet.

    Attributes:
        sku: The stock code the POS and the sheets share.
        name: Its name.
        kind: ``"bread"``, ``"pastry"`` or ``"cafe"``.
        cafe_price: Its price in the café, in pounds.
        wholesale_price: Its list price to restaurants, or ``None`` if the
            café only serves it.
    """

    sku: str
    name: str
    kind: str
    cafe_price: float
    wholesale_price: float | None


@Entity
@dataclass
class Restaurant:
    """A restaurant the bakery delivers to, from the restaurants sheet.

    Attributes:
        id: Primary key.
        name: Its name, as the other sheets refer to it.
        phone: The number it messages from.
        email: The address it emails from.
        address: Where the bread goes.
        lat: Latitude, for the map.
        lon: Longitude, for the map.
        kitchen_opens: When the bread has to be there, ``"HH:MM"``.
    """

    id: int | None
    name: str
    phone: str
    email: str
    address: str
    lat: float
    lon: float
    kitchen_opens: str


@Entity
@dataclass
class StandingOrder:
    """What a restaurant usually takes on a weekday, from the standing orders sheet.

    Attributes:
        id: Primary key.
        restaurant: The restaurant's name.
        weekday: ``"Monday"`` to ``"Sunday"``.
        sku: The product.
        quantity: How many.
    """

    id: int | None
    restaurant: str
    weekday: str
    sku: str
    quantity: int


@Entity
@dataclass
class Contract:
    """The price a restaurant pays for a product this quarter, from the contracts sheet.

    Attributes:
        id: Primary key.
        restaurant: The restaurant's name.
        sku: The product.
        price: The agreed price, in pounds.
        valid_until: The last day it holds, ``"YYYY-MM-DD"``.
    """

    id: int | None
    restaurant: str
    sku: str
    price: float
    valid_until: str


@Entity
@dataclass
class Message:
    """A message to the bakery, by chat or email.

    Attributes:
        id: Primary key.
        received_at: When it was sent, as a Unix time.
        channel: ``"messenger"`` or ``"email"``.
        sender: Who sent it: a phone number or an email address.
        restaurant: The restaurant that sent it, if it's one of them.
        subject: An email's subject; ``None`` for a chat message.
        text: What it says.
        external_id: Its id in the tool it came from, so it's never taken twice.
        status: ``"new"`` until someone deals with it.
    """

    id: int | None
    received_at: float
    channel: str
    sender: str
    restaurant: str | None
    subject: str | None
    text: str
    external_id: str
    status: str = "new"


@Entity
@dataclass
class CafeSale:
    """One line of a café order taken at the POS.

    Attributes:
        id: Primary key.
        sold_at: When it was rung up, as a Unix time.
        order_id: The POS order it's part of.
        sku: The product.
        product: Its name.
        quantity: How many.
        revenue: What they came to, in pounds.
    """

    id: int | None
    sold_at: float
    order_id: str
    sku: str
    product: str
    quantity: int
    revenue: float
