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
    """A message to the bakery, or one the bakery sent, by chat or email.

    Attributes:
        id: Primary key.
        received_at: When it was sent, as a Unix time.
        channel: ``"messenger"`` or ``"email"``.
        sender: The other side's phone number or email address: who sent it,
            or, for one the bakery sent, who it went to.
        restaurant: The restaurant on the other side, if it's one of them.
        subject: An email's subject; ``None`` for a chat message.
        text: What it says.
        external_id: Its id in the tool it came from, so it's never taken
            twice; ``"sent:draft-<id>:<n>"`` for one the bakery sent.
        status: ``"new"`` until someone deals with it, ``"drafted"`` while a
            draft answers it, ``"done"`` once that's confirmed; ``"sent"``
            for one the bakery sent.
        direction: ``"in"``, to the bakery, or ``"out"``, from it.
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
    direction: str = "in"


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


@Entity
@dataclass
class OrderChange:
    """A confirmed change to what a restaurant takes, on one day or from one day on.

    Attributes:
        id: Primary key.
        restaurant: The restaurant's name.
        sku: The product.
        date: The day it applies to, or the first day of a lasting one, ``"YYYY-MM-DD"``.
        mode: ``"add"`` (``quantity`` more, or fewer if negative, that day),
            ``"set"`` (exactly ``quantity`` that day) or ``"set-from"`` (exactly
            ``quantity`` on every day it's usually ordered, from ``date`` on).
        quantity: How many.
        message: The message that asked for it.
        draft: The draft it was confirmed from.
    """

    id: int | None
    restaurant: str
    sku: str
    date: str
    mode: str
    quantity: int
    message: int | None
    draft: int | None


@Entity
@dataclass
class Draft:
    """Something an agent prepared, waiting for a person to confirm or reject it.

    Attributes:
        id: Primary key.
        created_at: When it was drafted, as a Unix time.
        kind: ``"order-change"`` or ``"specials"``.
        status: ``"pending"`` (ready to confirm), ``"needs-review"`` (the
            agent couldn't read it, so a person has to), ``"confirmed"``,
            ``"rejected"`` or ``"outdated"`` (a newer message, or a person's
            instruction, replaced it with another draft).
        title: What it's about, such as ``"Order change for Le Petit"``.
        date: The day it's for, ``"YYYY-MM-DD"``.
        restaurant: The restaurant it's for, if any.
        message: The message it answers, if any.
        changes: What confirming it does, as JSON: order changes, or the
            specials.
        reply: The reply confirming it sends, if any.
        author: Who drafted it: ``"rules"`` or ``"model:<name>"``, or
            ``"nobody"`` when neither could; ``"edited"`` once a person
            changed it.
        note: Why it needs review, or why it was rejected.
        body: The draft as a person reads it, in Markdown.
    """

    id: int | None
    created_at: float
    kind: str
    status: str
    title: str
    date: str
    restaurant: str | None
    message: int | None
    changes: str
    reply: str
    author: str
    note: str
    body: str


@Entity
@dataclass
class Forecast:
    """How many of a product the café expects to sell on a day.

    Attributes:
        id: Primary key.
        date: The day, ``"YYYY-MM-DD"``.
        sku: The product.
        product: Its name.
        baseline: The average sold on the same weekday over recent weeks.
        weather: The weather's factor: below 1 for rain, above for warmth.
        holiday: The bank holiday factor, or 1.
        quantity: The forecast: the baseline times both factors, rounded up.
        rain_mm: The rain forecast for the day, in millimetres.
    """

    id: int | None
    date: str
    sku: str
    product: str
    baseline: float
    weather: float
    holiday: float
    quantity: int
    rain_mm: float


@Entity
@dataclass
class BakeSheetLine:
    """One product on a night's bake sheet.

    Attributes:
        id: Primary key.
        date: The morning it's baked for, ``"YYYY-MM-DD"``.
        sku: The product.
        product: Its name.
        wholesale: How many the restaurants take.
        cafe: How many the café is forecast to sell.
        buffer: Extra for the café, in case it's busier than forecast.
        total: What to bake.
    """

    id: int | None
    date: str
    sku: str
    product: str
    wholesale: int
    cafe: int
    buffer: int
    total: int


@Entity
@dataclass
class Leftover:
    """What the café didn't sell of a product baked for it.

    Attributes:
        id: Primary key.
        date: The day, ``"YYYY-MM-DD"``.
        sku: The product.
        product: Its name.
        baked: How many were baked for the café, buffer included.
        sold: How many the café sold.
        unsold: What's left.
    """

    id: int | None
    date: str
    sku: str
    product: str
    baked: int
    sold: int
    unsold: int


@Entity
@dataclass
class DeliveryStop:
    """One stop on a morning's delivery run; stop 0 is the bakery, where the van sets off.

    Attributes:
        id: Primary key.
        date: The morning, ``"YYYY-MM-DD"``.
        stop: Its place on the run, from 0.
        restaurant: Who it's for.
        address: Where.
        lat: Latitude, for the map.
        lon: Longitude, for the map.
        arrive_by: When the kitchen opens, ``"HH:MM"``.
        eta: When the van gets there, ``"HH:MM"``.
        load: What's dropped off, such as ``"12 × Baguette, 6 × Croissant"``.
        items: How many items that is.
    """

    id: int | None
    date: str
    stop: int
    restaurant: str
    address: str
    lat: float
    lon: float
    arrive_by: str
    eta: str
    load: str
    items: int


@Entity
@dataclass
class Ingredient:
    """Something the bakery buys and bakes with, from the ingredients sheet.

    Attributes:
        code: Its code, as the recipes sheet refers to it.
        name: Its name.
        unit: What it's priced by: ``"kg"``, ``"L"``, ``"each"`` or ``"minute"``.
        supplier: Who sells it; empty for bake time, which nobody invoices.
        invoice_name: What its supplier calls it on an invoice.
        price: What a unit cost when the sheet was written, in pounds: used
            until an invoice says otherwise.
    """

    code: str
    name: str
    unit: str
    supplier: str
    invoice_name: str
    price: float


@Entity
@dataclass
class RecipeLine:
    """How much of one ingredient one of a product takes, from the recipes sheet.

    Attributes:
        id: Primary key.
        sku: The product.
        ingredient: The ingredient's code.
        quantity: How much, in the ingredient's unit.
    """

    id: int | None
    sku: str
    ingredient: str
    quantity: float


@Entity
@dataclass
class Invoice:
    """A supplier's invoice, as the PDF it emailed.

    Attributes:
        id: Primary key.
        received_at: When it was emailed, as a Unix time.
        supplier: Who sent it, as its email names it.
        sender: The address it came from.
        subject: The email's subject.
        number: The invoice's own number, once read.
        date: The invoice's date, ``"YYYY-MM-DD"``, once read.
        total: What it comes to, in pounds, once read.
        status: ``"new"``, ``"recorded"`` (its prices are in IngredientPrices),
            ``"drafted"`` (its reading waits for a person) or ``"rejected"``.
        external_id: The email's ``Message-ID``, so it's never taken twice.
        filename: The attachment's name.
        pdf: The PDF itself.
    """

    id: int | None
    received_at: float
    supplier: str
    sender: str
    subject: str
    number: str | None
    date: str | None
    total: float | None
    status: str
    external_id: str
    filename: str
    pdf: bytes


@Entity
@dataclass
class IngredientPrice:
    """What a supplier charged for a unit of an ingredient, on one invoice.

    Attributes:
        id: Primary key.
        priced_at: When the invoice was emailed, as a Unix time.
        ingredient: The ingredient's code.
        name: Its name.
        unit: What it's priced by.
        unit_price: The price per unit, in pounds.
        supplier: Who charged it.
        invoice: The invoice it was on.
    """

    id: int | None
    priced_at: float
    ingredient: str
    name: str
    unit: str
    unit_price: float
    supplier: str
    invoice: int


@Entity
@dataclass
class IngredientAllergen:
    """An allergen an ingredient contains, or may contain.

    Attributes:
        id: Primary key.
        ingredient: The ingredient's code.
        allergen: One of the 14 a label must declare: ``"gluten"``, ``"sesame"``, ...
        kind: ``"contains"`` or ``"may contain"``.
        source: ``"sheet"`` (from the allergens sheet), or the invoice that
            declared it, such as ``"invoice 31"``.
        since: When it was recorded, as a Unix time.
    """

    id: int | None
    ingredient: str
    allergen: str
    kind: str
    source: str
    since: float
