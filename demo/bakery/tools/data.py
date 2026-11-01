"""The bakery's world: its products, the restaurants it supplies, and their orders.

Everything here is fictional. Phone numbers are in the 07700 900xxx range set
aside for drama, email domains are ``.example``, and the coordinates are
streets in a city centre, not real businesses.

Only the simulated tools read this module. The ``odf`` project learns the same
facts the way a real integration would: from the sheets on the shared drive,
and from what the POS, the messenger and the mailbox send it.
"""

import csv
import random
from dataclasses import dataclass
from pathlib import Path

BAKERY_NAME = "The Bakery"
BAKERY_EMAIL = "orders@bakery.example"
BAKERY_PHONE = "+447700900100"
# The bakery's number's id on the messenger, as its API addresses it.
BAKERY_PHONE_ID = "100200300"


@dataclass(frozen=True)
class Product:
    """Something the bakery makes or serves."""

    sku: str
    name: str
    kind: str  # "bread", "pastry" or "cafe"
    cafe_price: float
    wholesale_price: float | None  # None: café only


PRODUCTS: tuple[Product, ...] = (
    Product("SD-LOAF", "Sourdough loaf", "bread", 4.80, 3.10),
    Product("BAG", "Baguette", "bread", 2.20, 1.20),
    Product("RYE", "Rye loaf", "bread", 4.20, 2.80),
    Product("BRI", "Brioche", "bread", 4.50, 3.00),
    Product("FOC", "Focaccia", "bread", 3.80, 2.40),
    Product("CRO", "Croissant", "pastry", 2.40, 1.30),
    Product("PAC", "Pain au chocolat", "pastry", 2.70, 1.50),
    Product("AVT", "Avocado toast", "cafe", 8.50, None),
    Product("FRT", "French toast", "cafe", 7.50, None),
    Product("EGS", "Eggs on sourdough", "cafe", 7.90, None),
    Product("GRA", "Granola bowl", "cafe", 6.50, None),
    Product("FLW", "Flat white", "cafe", 3.40, None),
)

BY_SKU = {p.sku: p for p in PRODUCTS}
WHOLESALE = tuple(p for p in PRODUCTS if p.wholesale_price is not None)


@dataclass(frozen=True)
class Restaurant:
    """A restaurant the bakery delivers to each morning."""

    name: str
    phone: str
    email: str
    address: str
    lat: float
    lon: float
    kitchen_opens: str  # "HH:MM"


RESTAURANTS: tuple[Restaurant, ...] = (
    Restaurant(
        "Le Petit",
        "+447700900201",
        "kitchen@lepetit.example",
        "4 Quay Row",
        51.4527,
        -2.5946,
        "07:30",
    ),
    Restaurant(
        "Harbour Kitchen",
        "+447700900202",
        "chef@harbourkitchen.example",
        "12 Dock Lane",
        51.4489,
        -2.5981,
        "08:00",
    ),
    Restaurant(
        "The Fig Tree",
        "+447700900203",
        "hello@figtree.example",
        "27 Orchard Street",
        51.4561,
        -2.6003,
        "08:30",
    ),
    Restaurant(
        "Olive & Ash",
        "+447700900204",
        "orders@oliveandash.example",
        "9 Kiln Yard",
        51.4598,
        -2.5871,
        "09:00",
    ),
    Restaurant(
        "North Street Diner",
        "+447700900205",
        "diner@northstreet.example",
        "61 North Street",
        51.4433,
        -2.6044,
        "07:00",
    ),
    Restaurant(
        "Kiln",
        "+447700900206",
        "kitchen@kiln.example",
        "3 Pottery Lane",
        51.4612,
        -2.5925,
        "10:00",
    ),
    Restaurant(
        "Marlowe's",
        "+447700900207",
        "bookings@marlowes.example",
        "18 Chapel Walk",
        51.4545,
        -2.5832,
        "08:00",
    ),
    Restaurant(
        "Saffron House",
        "+447700900208",
        "kitchen@saffronhouse.example",
        "40 Mill Road",
        51.4502,
        -2.5890,
        "11:00",
    ),
)

BY_PHONE = {r.phone: r for r in RESTAURANTS}

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# The plural a restaurant writes for a product.
PLURALS = {
    "SD-LOAF": "sourdough loaves",
    "BAG": "baguettes",
    "RYE": "rye loaves",
    "BRI": "brioche",
    "FOC": "focaccia",
    "CRO": "croissants",
    "PAC": "pains au chocolat",
}

# Templated order changes: easy for rules to read.
MESSAGE_TEMPLATES = (
    "{n} extra {plural} tomorrow please",
    "Could we get {n} {plural} on {weekday}?",
    "No {plural} on {weekday} this week, thanks",
    "Please drop the {plural} to {n} from tomorrow",
)

# Freeform ones: only a model reads these reliably.
FREEFORM_MESSAGES = (
    "could we swap Friday's croissants for brioche? big party, maybe 40 people",
    "Morning! Chef's off sick so keep it light tomorrow, half of the usual is plenty",
    "the focaccia was amazing yesterday, can we double it for the weekend? and 10 more baguettes",
    "Is there any chance of rye instead of sourdough on Thursday? Menu change",
)


def standing_orders(seed: int) -> list[tuple[str, str, str, int]]:
    """Return ``(restaurant, weekday, sku, quantity)`` rows: each restaurant's usual order."""
    rng = random.Random(seed)
    rows = []
    for restaurant in RESTAURANTS:
        usual = rng.sample(WHOLESALE, k=rng.randint(2, 4))
        for weekday in WEEKDAYS:
            if weekday == "Sunday" and rng.random() < 0.5:
                continue
            for product in usual:
                base = rng.randint(4, 20)
                weekend = 1.4 if weekday in ("Friday", "Saturday") else 1.0
                rows.append((restaurant.name, weekday, product.sku, round(base * weekend)))
    return rows


def contract_prices(seed: int) -> list[tuple[str, str, float]]:
    """Return ``(restaurant, sku, price)`` rows: the prices agreed for the quarter."""
    rng = random.Random(seed + 1)
    rows = []
    for restaurant in RESTAURANTS:
        discount = rng.choice((0.0, 0.05, 0.08, 0.1))
        for product in WHOLESALE:
            rows.append(
                (restaurant.name, product.sku, round(product.wholesale_price * (1 - discount), 2))
            )
    return rows


def write_sheets(folder: Path, seed: int, contracts_until: str) -> list[str]:
    """Write the bakery's spreadsheets, as CSV exports, into ``folder``.

    Only sheets that aren't there yet are written, so edits the owner made
    survive a restart.

    Returns:
        The names of the sheets written.
    """
    folder.mkdir(parents=True, exist_ok=True)
    sheets = {
        "products.csv": (
            ("sku", "name", "kind", "cafe_price", "wholesale_price"),
            [
                (
                    p.sku,
                    p.name,
                    p.kind,
                    f"{p.cafe_price:.2f}",
                    "" if p.wholesale_price is None else f"{p.wholesale_price:.2f}",
                )
                for p in PRODUCTS
            ],
        ),
        "restaurants.csv": (
            ("name", "phone", "email", "address", "lat", "lon", "kitchen_opens"),
            [
                (r.name, r.phone, r.email, r.address, r.lat, r.lon, r.kitchen_opens)
                for r in RESTAURANTS
            ],
        ),
        "standing_orders.csv": (
            ("restaurant", "weekday", "sku", "quantity"),
            standing_orders(seed),
        ),
        "contracts.csv": (
            ("restaurant", "sku", "price", "valid_until"),
            [(r, sku, f"{price:.2f}", contracts_until) for r, sku, price in contract_prices(seed)],
        ),
    }
    written = []
    for name, (header, rows) in sheets.items():
        path = folder / name
        if path.exists():
            continue
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        written.append(name)
    return written
