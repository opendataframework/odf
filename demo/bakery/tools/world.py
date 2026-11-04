"""The world around the bakery: the demo clock, and everyone who uses the other tools.

Run with ``uvicorn tools.world:app --port 8000``. It isn't one of the
bakery's tools. It's the simulation's stage manager:

- **The clock.** Simulated time, ``SPEED`` simulated seconds per real second
  (60 by default: a day in 24 minutes). Every tool asks ``GET /clock`` for
  "now", and the console can pause it, change its speed or move it on.
- **The actors.** Café customers ring up orders at the POS through the
  morning; in the evening, restaurants message (or email) order changes for
  tomorrow. Each supplier emails its weekly invoice, a PDF, at 09:00 on its
  day.
- **The history.** On first start it seeds the tools with what a bakery
  that's been trading a while has: 12 weeks of café orders, two weeks of
  chats, a month of email and invoices. Every start writes any of the shared
  drive's sheets that aren't there yet.
- **The weather.** A forecast in Open-Meteo's JSON shape, made up from the
  seed and the date, offline. Rain keeps café customers away.
- **Scenarios.** Buttons on the console: a party order, a café rush, a
  missed webhook, a rainy week, a butter price spike, and so on.
- **Tours.** A scenario played end to end (``tools/tours.py``): the world
  follows the bakery's notifications through each step, says what to look
  at, and can confirm the draft at the end for the presenter.
"""

import csv
import html
import json
import random
import smtplib
import threading
import time
import urllib.request
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from tools.common import connect, env, http_json, page, wait_for
from tools.data import (
    BAKERY_EMAIL,
    BY_INGREDIENT,
    BY_SKU,
    BY_SUPPLIER,
    FREEFORM_MESSAGES,
    MESSAGE_TEMPLATES,
    PLURALS,
    RESTAURANTS,
    SUPPLIERS,
    WEEKDAYS,
    WHOLESALE,
    Restaurant,
    Supplier,
    write_sheets,
)
from tools.invoices import delivery, invoice_pdf, total
from tools.tours import ORDER_MESSAGE, ORDER_RESTAURANT, TOURS, capture, matches, needed, say

SEED = int(env("SEED", "7"))
SPEED = float(env("SPEED", "60"))
HISTORY_WEEKS = int(env("HISTORY_WEEKS", "12"))
POS_URL = env("POS_URL", "http://pos:8001")
POS_TOKEN = env("POS_TOKEN", "pos-dev-token")
MESSENGER_URL = env("MESSENGER_URL", "http://messenger:8002")
MESSENGER_TOKEN = env("MESSENGER_TOKEN", "messenger-dev-token")
MAIL_HOST = env("MAIL_HOST", "mailpit")
MAIL_PORT = int(env("MAIL_PORT", "1025"))
SHARED_DRIVE = Path(env("SHARED_DRIVE", "shared-drive"))
# The bakery's odf UI, as the world reaches it: tours follow its notifications.
BAKERY_URL = env("BAKERY_URL", "http://bakery:4747")
LINKS = {
    "Bakery (odf)": env("ODF_PUBLIC_URL", "http://localhost:4747"),
    "POS": env("POS_PUBLIC_URL", "http://localhost:8001"),
    "Messenger": env("MESSENGER_PUBLIC_URL", "http://localhost:8002"),
    "Mail": env("MAIL_PUBLIC_URL", "http://localhost:8025"),
}

# Café orders per simulated minute, by hour: a breakfast rush, a lunch bump.
CAFE_RATE = {7: 0.35, 8: 0.6, 9: 0.55, 10: 0.4, 11: 0.35, 12: 0.5, 13: 0.45, 14: 0.25}
# Chance per restaurant per simulated minute, 17:00-23:00, of an order change.
EVENING_RATE = 0.0012
# How rain changes the café's footfall: (millimetres at least, factor).
RAIN_FOOTFALL = ((5.0, 0.6), (1.0, 0.85))
# A typical day's high by month, in °C.
MONTH_HIGH = (8, 9, 11, 14, 17, 20, 22, 22, 19, 15, 11, 8)
# What café customers pick, and how often.
CAFE_PICKS = (
    ("FLW", 6),
    ("CRO", 4),
    ("PAC", 2),
    ("AVT", 2),
    ("EGS", 2),
    ("FRT", 1),
    ("GRA", 1),
    ("SD-LOAF", 1),
    ("BAG", 1),
)

db, lock = connect("world")
with lock:
    db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.commit()


def _get(key: str) -> str | None:
    """Return a saved state value."""
    with lock:
        row = db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set(**values: object) -> None:
    """Save state values."""
    with lock:
        db.executemany(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            [(k, str(v)) for k, v in values.items()],
        )
        db.commit()


class Clock:
    """Simulated time: an anchor in simulated and in real time, a speed, and a pause.

    Kept in the world's database, so a restart carries on where it was.
    """

    def __init__(self) -> None:
        """Load the clock, or start it at 07:00 today (``SIM_START`` overrides)."""
        if _get("anchor_sim") is None:
            start = env("SIM_START", "")
            sim = (
                datetime.fromisoformat(start)
                if start
                else datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
            )
            _set(anchor_sim=sim.isoformat(), anchor_real=time.time(), speed=SPEED, paused=0)

    def state(self) -> tuple[datetime, float, float, bool]:
        """Return the anchors, the speed and whether it's paused."""
        return (
            datetime.fromisoformat(_get("anchor_sim")),
            float(_get("anchor_real")),
            float(_get("speed")),
            _get("paused") == "1",
        )

    def now(self) -> datetime:
        """Return the simulated time now."""
        sim, real, speed, paused = self.state()
        if paused:
            return sim
        return sim + timedelta(seconds=(time.time() - real) * speed)

    def hold(self) -> None:
        """Save the time now, so the world can carry on from it after it's been down."""
        _set(anchor_sim=self.now().isoformat(), anchor_real=time.time())

    def resume(self) -> None:
        """Carry on from the time saved by ``hold()``, not counting the time the world was down."""
        _set(anchor_real=time.time())

    def update(
        self,
        speed: float | None = None,
        paused: bool | None = None,
        advance_minutes: int = 0,
        to: str | None = None,
    ) -> None:
        """Change the speed, pause or resume, or move the clock on.

        Args:
            speed: Simulated seconds per real second.
            paused: Stop or restart the clock.
            advance_minutes: Move it on by this many simulated minutes.
            to: Move it on to the next ``"HH:MM"``.
        """
        now = self.now()
        _, _, current_speed, current_paused = self.state()
        if to:
            hour, minute = (int(x) for x in to.split(":"))
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            now = target
        now += timedelta(minutes=advance_minutes)
        _set(
            anchor_sim=now.isoformat(),
            anchor_real=time.time(),
            speed=current_speed if speed is None else max(0.0, float(speed)),
            paused=int(current_paused if paused is None else paused),
        )


clock = Clock()
feed: deque[tuple[str, str]] = deque(maxlen=60)
rng = random.Random(SEED)


def _log(text: str) -> None:
    """Add a line to the console's feed, stamped with the simulated time."""
    feed.appendleft((clock.now().strftime("%a %H:%M"), text))


def _basket(r: random.Random) -> list[dict]:
    """Return a café customer's order: one to three items."""
    skus, weights = zip(*CAFE_PICKS, strict=True)
    picks = r.choices(skus, weights=weights, k=r.choice((1, 1, 2, 2, 3)))
    basket: dict[str, int] = {}
    for sku in picks:
        basket[sku] = basket.get(sku, 0) + 1
    return [{"sku": sku, "quantity": q} for sku, q in basket.items()]


def weather(day: date) -> dict[str, float]:
    """Return ``day``'s weather: ``{"rain_mm", "temp_max"}``, the same every time it's asked.

    Made up from the seed and the date. Days in a rainy spell (the
    ``rainy-week`` scenario) pour.
    """
    r = random.Random(f"{SEED}-{day.isoformat()}")
    roll = r.random()
    if roll < 0.6:
        rain = 0.0
    elif roll < 0.85:
        rain = round(r.uniform(0.2, 4.0), 1)
    else:
        rain = round(r.uniform(5.0, 14.0), 1)
    spell = _get("rain_from"), _get("rain_until")
    if spell[0] and spell[0] <= day.isoformat() <= spell[1]:
        rain = round(r.uniform(8.0, 20.0), 1)
    high = MONTH_HIGH[day.month - 1] + r.uniform(-3, 3) - (2 if rain >= 5 else 0)
    return {"rain_mm": rain, "temp_max": round(high, 1)}


def footfall(day: date) -> float:
    """Return how the day's rain changes the number of café customers: 1 when it's dry."""
    rain = weather(day)["rain_mm"]
    return next((factor for at_least, factor in RAIN_FOOTFALL if rain >= at_least), 1.0)


def _order_change(r: random.Random) -> str:
    """Return a templated order change, as a restaurant would write it."""
    product = r.choice(WHOLESALE)
    return r.choice(MESSAGE_TEMPLATES).format(
        n=r.randint(2, 12), plural=PLURALS[product.sku], weekday=r.choice(WEEKDAYS[:6])
    )


def cafe_order(r: random.Random = rng) -> dict | None:
    """A café customer pays at the till. Returns the order, or ``None`` if the POS failed.

    Orders aren't logged one by one, which would bury everything else in the
    feed: ``tick()`` logs each hour's count.
    """
    try:
        return http_json(
            "POST",
            f"{POS_URL}/v1/orders",
            {"line_items": _basket(r), "tender": "card"},
            {"Authorization": f"Bearer {POS_TOKEN}"},
        )
    except OSError as exc:
        _log(f"Café order failed: {exc}")
        return None


def _items(order: dict | None) -> str:
    """Return an order's items as text, such as "2 × Flat white, 1 × Croissant"."""
    if order is None:
        return "nothing (the POS failed)"
    return ", ".join(f"{line['quantity']} × {line['name']}" for line in order["line_items"])


# Café orders taken in the current simulated hour, logged when it ends.
cafe_hour: dict[str, object] = {"hour": None, "orders": 0}


def message(restaurant: Restaurant, text: str) -> None:
    """A restaurant sends the bakery a chat message."""
    try:
        http_json(
            "POST", f"{MESSENGER_URL}/simulate/inbound", {"from": restaurant.phone, "text": text}
        )
        _log(f"{restaurant.name} (chat): {text}")
    except OSError as exc:
        _log(f"Message from {restaurant.name} failed: {exc}")


def email(
    sender_name: str,
    sender: str,
    subject: str,
    text: str,
    sent: datetime | None = None,
    pdf: tuple[str, bytes] | None = None,
) -> None:
    """Someone emails the bakery, at ``sent`` (the simulated time now by default).

    ``pdf``, if given, is a ``(filename, content)`` attached to it.
    """
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender))
    msg["To"] = formataddr(("The Bakery", BAKERY_EMAIL))
    msg["Subject"] = subject
    msg["Date"] = format_datetime((sent or clock.now()).astimezone())
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[1])
    msg.set_content(text)
    if pdf is not None:
        msg.add_attachment(pdf[1], maintype="application", subtype="pdf", filename=pdf[0])
    try:
        with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=5) as smtp:
            smtp.send_message(msg)
        if sent is None:
            _log(f"{sender_name} (email): {subject}")
    except OSError as exc:
        _log(f"Email from {sender_name} failed: {exc}")


def restaurant_email(restaurant: Restaurant, text: str, sent: datetime | None = None) -> None:
    """A restaurant emails an order change."""
    email(
        restaurant.name,
        restaurant.email,
        "Order change",
        f"Hi,\n\n{text}\n\nThanks,\n{restaurant.name}",
        sent,
    )


def price(code: str) -> float:
    """Return what an ingredient costs now: what its supplier last charged, or its sheet price."""
    saved = _get(f"price:{code}")
    return float(saved) if saved is not None else BY_INGREDIENT[code].price


def supplier_invoice(
    supplier: Supplier, sent: datetime | None = None, notes: dict[str, str] | None = None
) -> None:
    """``supplier`` emails its invoice for this week's delivery, a PDF, at ``sent`` (now).

    ``notes`` puts a note under an ingredient's line, by its code.
    """
    at = sent or clock.now()
    number = int(_get(f"invoice:{supplier.name}") or 0) + 1
    _set(**{f"invoice:{supplier.name}": number})
    reference = f"{supplier.name.split()[0][:3].upper()}-{at:%Y}-{number:04d}"
    prices = {i: price(i) for i in BY_INGREDIENT}
    lines = delivery(supplier, prices, random.Random(f"{SEED}-{supplier.name}-{number}"), notes)
    content = invoice_pdf(supplier, reference, at.date(), lines)
    note = supplier.layout == "note"
    email(
        supplier.name,
        supplier.email,
        "Eggs" if note else f"Invoice {reference}",
        (
            "Hi, note for this week's eggs attached. Tom"
            if note
            else f"Hello,\n\nPlease find attached invoice {reference} for this week's delivery, "
            f"£{total(lines):,.2f}.\n\nKind regards,\n{supplier.name}"
        ),
        sent,
        pdf=(f"{'eggs' if note else reference}.pdf", content),
    )


def spiked_butter() -> float:
    """Return a butter price that puts exactly two of the bakery's contracts below cost.

    Works out, for each contract a restaurant actually orders, the butter price
    at which it stops covering its cost, from the sheets on the shared drive
    as they are now, and picks one between the second and the third.
    """

    def rows(name: str) -> list[dict]:
        with (SHARED_DRIVE / name).open(newline="") as f:
            return list(csv.DictReader(f))

    recipes: dict[str, dict[str, float]] = {}
    for row in rows("recipes.csv"):
        recipes.setdefault(row["sku"], {})[row["ingredient"]] = float(row["quantity"])
    taken = {(row["restaurant"], row["sku"]) for row in rows("standing_orders.csv")}
    now = price("BUTTER")
    limits = []
    for row in rows("contracts.csv"):
        recipe = recipes.get(row["sku"], {})
        if (row["restaurant"], row["sku"]) not in taken or not recipe.get("BUTTER"):
            continue
        other = sum(q * price(code) for code, q in recipe.items() if code != "BUTTER")
        limit = (float(row["price"]) - other) / recipe["BUTTER"]
        if limit > now:
            limits.append(limit)
    limits.sort()
    if len(limits) >= 3:
        target = (limits[1] + limits[2]) / 2
    elif limits:
        target = limits[-1] + 0.5
    else:
        target = now * 1.5
    return round(-(-target // 0.05) * 0.05, 2)


def tick(previous: datetime, now: datetime) -> None:
    """Act out each simulated minute that began after ``previous``, up to ``now``, once.

    A minute is acted out once it has begun, never before, so the next tick
    (which starts from this one's ``now``) doesn't act it out again. At most
    the last hour is acted out.
    """
    minute = max(previous, now - timedelta(hours=1)).replace(second=0, microsecond=0)
    while minute + timedelta(minutes=1) <= now:
        minute += timedelta(minutes=1)
        hour = minute.replace(minute=0)
        if cafe_hour["hour"] != hour:
            if cafe_hour["orders"]:
                start = cafe_hour["hour"]
                _log(f"Café: {cafe_hour['orders']} orders, {start:%H:00}–{hour:%H:00}")
            cafe_hour.update(hour=hour, orders=0)
        weekend = 1.3 if minute.weekday() >= 5 else 1.0
        rate = CAFE_RATE.get(minute.hour, 0.0) * weekend * footfall(minute.date())
        if rng.random() < rate and cafe_order():
            cafe_hour["orders"] += 1
        if minute.hour == 9 and minute.minute == 0:
            for supplier in SUPPLIERS:
                if supplier.weekday == WEEKDAYS[minute.weekday()]:
                    supplier_invoice(supplier)
        if 17 <= minute.hour < 23:
            for restaurant in RESTAURANTS:
                if rng.random() < EVENING_RATE:
                    text = _order_change(rng)
                    if rng.random() < 0.3:
                        restaurant_email(restaurant, text)
                    else:
                        message(restaurant, text)


def seed_history() -> None:
    """Write any sheets missing, and fill the tools with the history of a bakery that's trading.

    The sheets are checked on every start, so a sheet added to the demo
    reaches a drive that was written before it; the history is seeded once.
    """
    start = clock.now()
    written = write_sheets(SHARED_DRIVE, SEED, _quarter_end(start).isoformat())
    _log(f"Shared drive: wrote {', '.join(written) or 'nothing (sheets already there)'}")
    if _get("seeded") == "1":
        return
    r = random.Random(SEED)

    wait_for(f"{POS_URL}/admin/state")
    orders, number = [], 0
    for day in range(HISTORY_WEEKS * 7, 0, -1):
        date = (start - timedelta(days=day)).replace(hour=7, minute=0, second=0, microsecond=0)
        weekend = 1.3 if date.weekday() >= 5 else 1.0
        rain = footfall(date.date())
        for offset in range(8 * 60):
            at = date + timedelta(minutes=offset, seconds=r.randint(0, 59))
            if r.random() < CAFE_RATE.get(at.hour, 0.0) * weekend * rain:
                number += 1
                orders.append(_history_order(r, at, number))
    for i in range(0, len(orders), 1000):
        http_json(
            "POST",
            f"{POS_URL}/admin/import",
            {"orders": orders[i : i + 1000]},
            {"Authorization": f"Bearer {POS_TOKEN}"},
            timeout=30,
        )
    _log(f"POS: imported {len(orders)} past café orders")

    wait_for(f"{MESSENGER_URL}/")
    chats, number = [], 0
    for day in range(14, 0, -1):
        for restaurant in RESTAURANTS:
            if r.random() < 0.35:
                at = (start - timedelta(days=day)).replace(
                    hour=r.randint(17, 22), minute=r.randint(0, 59), second=0, microsecond=0
                )
                number += 1
                chats.append(
                    {
                        "id": f"msg_h{number:06d}",
                        "contact": restaurant.phone,
                        "direction": "in",
                        "text": _order_change(r),
                        "sent_at": at.isoformat(),
                    }
                )
                number += 1
                chats.append(
                    {
                        "id": f"msg_h{number:06d}",
                        "contact": restaurant.phone,
                        "direction": "out",
                        "text": "Noted, thanks!",
                        "sent_at": (at + timedelta(minutes=r.randint(3, 40))).isoformat(),
                    }
                )
    http_json(
        "POST",
        f"{MESSENGER_URL}/admin/import",
        {"messages": chats},
        {"Authorization": f"Bearer {MESSENGER_TOKEN}"},
    )
    _log(f"Messenger: imported {len(chats)} past messages")

    for _ in range(60):  # wait for the mail server
        try:
            smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=2).quit()
            break
        except OSError:
            time.sleep(1)
    for day in sorted(r.sample(range(1, 31), 5), reverse=True):
        at = (start - timedelta(days=day)).replace(hour=r.randint(8, 20), minute=r.randint(0, 59))
        restaurant_email(r.choice(RESTAURANTS), _order_change(r), sent=at)
    for day in range(30, 0, -1):
        at = (start - timedelta(days=day)).replace(hour=9, minute=0, second=0, microsecond=0)
        for supplier in SUPPLIERS:
            if supplier.weekday == WEEKDAYS[at.weekday()]:
                supplier_invoice(supplier, sent=at)
    _log("Mail: sent a month of past emails and invoices")
    _set(seeded=1)


def _history_order(r: random.Random, at: datetime, number: int) -> dict:
    """Return a past café order, shaped as the POS stores it."""
    lines = [
        {
            "sku": item["sku"],
            "name": BY_SKU[item["sku"]].name,
            "quantity": item["quantity"],
            "unit_price": BY_SKU[item["sku"]].cafe_price,
        }
        for item in _basket(r)
    ]
    return {
        "id": f"ord_h{number:06d}",
        "created_at": at.isoformat(timespec="seconds"),
        "location": "cafe",
        "line_items": lines,
        "total": round(sum(line["quantity"] * line["unit_price"] for line in lines), 2),
        "tender": r.choice(("card", "card", "card", "cash")),
    }


def _quarter_end(day: datetime) -> datetime:
    """Return the last day of ``day``'s quarter: when this quarter's contracts end."""
    month = ((day.month - 1) // 3 + 1) * 3
    first_next = datetime(day.year + (month == 12), month % 12 + 1, 1)
    return first_next - timedelta(days=1)


SCENARIOS = {
    "restaurant-message": "A restaurant messages an order change",
    "party-order": "Le Petit asks for a party order, in its own words",
    "email-change": "A restaurant emails an order change",
    "cafe-rush": "Ten café customers at once",
    "missed-webhook": "The POS drops the next order's webhook",
    "rainy-week": "It pours from now on for a week, which nobody forecast for today",
    "butter-spike": "Vale Dairy's invoice comes early, with butter up sharply",
    "farm-invoice": "Hill Farm's handwritten-looking note for this week's eggs",
    "sesame-substitution": "Millers Ltd swaps in another mill's flour, which may contain sesame",
}

# What Millers Ltd prints under the flour on the sesame-substitution invoice.
SESAME_NOTE = "Substituted: Hillside Mill strong white flour. May contain sesame."


def run_scenario(name: str) -> None:
    """Act out one of ``SCENARIOS``."""
    r = random.Random()
    if name == "restaurant-message":
        message(r.choice(RESTAURANTS), _order_change(r))
    elif name == "party-order":
        message(RESTAURANTS[0], FREEFORM_MESSAGES[0])
    elif name == "email-change":
        restaurant_email(r.choice(RESTAURANTS), _order_change(r))
    elif name == "cafe-rush":
        taken = sum(1 for _ in range(10) if cafe_order(r))
        _log(f"Café rush: {taken} orders at once")
    elif name == "rainy-week":
        today = clock.now().date()
        _set(rain_from=today.isoformat(), rain_until=(today + timedelta(days=6)).isoformat())
        _log(f"Weather: rain from now until {today + timedelta(days=6):%A}, café footfall down")
    elif name == "butter-spike":
        was, now = price("BUTTER"), spiked_butter()
        _set(**{"price:BUTTER": now})
        supplier_invoice(BY_SUPPLIER["Vale Dairy"])
        _log(f"Vale Dairy: butter from £{was:.2f} to £{now:.2f} a kg, invoice sent")
    elif name == "farm-invoice":
        supplier_invoice(BY_SUPPLIER["Hill Farm"])
    elif name == "sesame-substitution":
        supplier_invoice(BY_SUPPLIER["Millers Ltd"], notes={"FLOUR": SESAME_NOTE})
        _log("Millers Ltd: flour from Hillside Mill this week, which may contain sesame")
    elif name == "missed-webhook":
        http_json(
            "POST",
            f"{POS_URL}/admin/drop-next-webhook",
            None,
            {"Authorization": f"Bearer {POS_TOKEN}"},
        )
        _log(f"POS: dropped the webhook of an order for {_items(cafe_order(r))}")
    else:
        raise KeyError(name)


# What each tour acts out once the world follows the bakery's notifications.
TOUR_STARTS: dict[str, Callable[[], None]] = {
    "order-change": lambda: message(ORDER_RESTAURANT, ORDER_MESSAGE),
    "butter-spike": lambda: run_scenario("butter-spike"),
    "sesame-substitution": lambda: run_scenario("sesame-substitution"),
}
# Real seconds a step waits before the console asks whether the bakery is up.
SLOW_STEP = 60


def notification_stream(url: str, timeout: float = 30) -> Iterator[dict | None]:
    """Yield ``None`` once subscribed to an odf UI's notification stream, then each notification.

    Reads its server-sent events: ``data:`` lines, one JSON item each. The UI
    writes ``: connected`` once it has subscribed this client, so nothing
    published after the ``None`` is missed, and pings every 15 seconds, so
    ``timeout`` only trips on a stream that's gone quiet.

    Raises:
        OSError: If the stream can't be opened, or breaks.
    """
    with urllib.request.urlopen(url, timeout=timeout) as response:
        for raw in response:
            line = raw.decode().rstrip("\r\n")
            if line.startswith(": connected"):
                yield None
            elif line.startswith("data: "):
                item = json.loads(line.removeprefix("data: "))
                if item.get("type") == "notification":
                    yield item


class Guide:
    """Plays one tour at a time: acts out its start, then follows the bakery through its steps.

    The clock is paused while a tour plays, so the café and the restaurants
    don't add notices of their own, and is put back as it was when the tour
    ends or stops.

    Args:
        spawn: Runs ``follow(generation)`` in the background; a thread by
            default.
    """

    def __init__(self, spawn: Callable[[int], None] | None = None) -> None:
        """See class docstring for args."""
        self.lock = threading.Lock()
        self.generation = 0
        self.spawn = spawn or (
            lambda gen: threading.Thread(target=self.follow, args=(gen,), daemon=True).start()
        )
        self._clear()

    def _clear(self) -> None:
        """Forget the tour."""
        self.name: str | None = None
        self.index = 0
        self.captured: dict[str, list] = {}
        self.seen: list[list[str]] = []
        # Every notification since the tour started that no step has taken yet.
        self.unused: deque[dict] = deque(maxlen=500)
        self.step_since = 0.0
        self.error: str | None = None
        self.paused_before: bool | None = None

    def _end(self) -> None:
        """Stop following the bakery, and put the clock back as it was. Called holding the lock."""
        self.generation += 1
        if self.paused_before is not None:
            clock.update(paused=self.paused_before)
            self.paused_before = None

    def start(self, name: str) -> None:
        """Play tour ``name``, instead of any playing.

        Raises:
            KeyError: If there's no tour ``name``.
        """
        tour = TOURS[name]
        with self.lock:
            self._end()
            self._clear()
            self.name = name
            self.captured = {k: [v] for k, v in tour.given.items()}
            self.seen = [[] for _ in tour.steps]
            self.step_since = time.time()
            self.paused_before = clock.state()[3]
            clock.update(paused=True)
            gen = self.generation
        _log(f"Tour: {tour.title}")
        self.spawn(gen)

    def follow(self, gen: int) -> None:
        """Follow the bakery's notifications for tour ``gen``, acting out its start once subscribed.

        Reconnects every two seconds while the bakery can't be reached, and
        acts out the start only the first time it's subscribed.
        """
        started = False
        while self.generation == gen:
            try:
                for item in notification_stream(f"{BAKERY_URL}/api/notifications"):
                    if self.generation != gen:
                        return
                    if item is not None:
                        try:
                            self.notify(gen, item)
                        except Exception as exc:  # noqa: BLE001 - shown, not lost with the thread
                            with self.lock:
                                self.error = f"Couldn't follow {item.get('topic')!r}: {exc!r}"
                        continue
                    with self.lock:
                        self.error = None
                        name = self.name
                    if not started and name is not None:
                        started = True
                        TOUR_STARTS[name]()
            except (OSError, ValueError) as exc:
                with self.lock:
                    if self.generation == gen:
                        self.error = f"Can't follow the bakery at {BAKERY_URL}: {exc}"
            if self.generation == gen:
                time.sleep(2)

    def notify(self, gen: int, notification: dict) -> None:
        """Take one of the bakery's notifications: it may complete the current step, or a later one.

        The stream doesn't promise the order things happened in: a reaction
        on a worker of its own can publish before the notification it reacted
        to reaches the stream. So a notification no step takes yet is kept,
        and each step that becomes current first looks through those.
        """
        with self.lock:
            if gen != self.generation or self.name is None or self._done():
                return
            self.unused.append(notification)
            completed = self._catch_up()
        for what in completed:
            _log(f"Tour: {what}")

    def _catch_up(self) -> list[str]:
        """Complete, in order, each step the kept notifications complete. Called holding the lock.

        Returns:
            What completed each step, as the feed says it.
        """
        completed = []
        while not self._done():
            step = TOURS[self.name].steps[self.index]
            for notification in list(self.unused):
                if len(self.seen[self.index]) >= needed(step, self.captured):
                    break
                if matches(step, notification, self.captured):
                    self.unused.remove(notification)
                    capture(step, notification, self.captured)
                    self.seen[self.index].append(
                        notification.get("summary") or notification["topic"]
                    )
            if step.topic is None or len(self.seen[self.index]) < needed(step, self.captured):
                break
            completed.append("; ".join(self.seen[self.index]))
            self._advance()
        return completed

    def _done(self) -> bool:
        """Return whether every step is done. Called holding the lock."""
        return self.name is not None and self.index >= len(TOURS[self.name].steps)

    def _advance(self) -> None:
        """Move on to the next step, ending the tour after the last. Called holding the lock."""
        self.index += 1
        self.step_since = time.time()
        if self._done():
            self._end()

    def next(self) -> None:
        """Move on to the next step, without waiting for its notification."""
        with self.lock:
            if self.name is None or self._done():
                return
            self._advance()
            completed = self._catch_up()
        for what in completed:
            _log(f"Tour: {what}")

    def stop(self) -> None:
        """Stop the tour, done or not."""
        with self.lock:
            self._end()
            self._clear()

    def act(self) -> list:
        """Confirm the drafts the current step waits for, as a person would from their cards.

        Returns:
            The ids of the drafts confirmed.
        """
        with self.lock:
            if self.name is None or self._done():
                return []
            step = TOURS[self.name].steps[self.index]
            if step.confirms is None:
                return []
            confirmed = self.captured.get("confirmed", [])
            ids = [i for i in self.captured.get(step.confirms, []) if i not in confirmed]
        done = []
        for draft_id in ids:
            try:
                http_json(
                    "POST",
                    f"{BAKERY_URL}/api/functions/confirm-draft/call",
                    {"draft_id": draft_id},
                    timeout=60,
                )
                done.append(draft_id)
            except OSError as exc:
                with self.lock:
                    self.error = f"Couldn't confirm draft {draft_id}: {exc}"
        return done

    def state(self) -> dict:
        """Return the tour for the console: its steps, each done, current or later."""
        with self.lock:
            if self.name is None:
                return {"tour": None}
            tour = TOURS[self.name]
            steps = []
            for i, step in enumerate(tour.steps):
                status = "done" if i < self.index else "current" if i == self.index else "later"
                current = status == "current"
                steps.append(
                    {
                        "say": say(step, self.captured),
                        "look": step.look,
                        "url": LINKS.get(step.look or ""),
                        "status": status,
                        "seen": self.seen[i],
                        "waits": current and step.topic is not None,
                        "slow": current
                        and step.topic is not None
                        and time.time() - self.step_since > SLOW_STEP,
                        "acts": current and step.confirms is not None,
                    }
                )
            return {
                "tour": self.name,
                "title": tour.title,
                "done": self._done(),
                "error": self.error,
                "steps": steps,
            }


guide = Guide()


def _actors() -> None:
    """Seed the history once, then act out each simulated minute as the clock moves.

    The clock is saved every second too, so a world that's killed rather than
    stopped carries on from within a second of where it was.
    """
    try:
        seed_history()
    except OSError as exc:
        _log(f"Seeding failed, will retry on restart: {exc}")
    previous = clock.now()
    while True:
        time.sleep(1)
        clock.hold()
        now = clock.now()
        if now > previous:
            tick(previous, now)
        previous = now


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the actors with the app, and keep the clock still while the app is down.

    Stopping the stack (``docker compose stop`` or ``down``) stops the world
    gracefully, which saves the time; starting it again carries on from
    there. The actors also save it every second, for a world that's killed.
    """
    clock.resume()
    threading.Thread(target=_actors, daemon=True).start()
    yield
    guide.stop()  # a tour's paused clock isn't left paused for the next start
    clock.hold()


app = FastAPI(title="World", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/clock")
def get_clock() -> dict:
    """Return the simulated time now, the speed, and whether it's paused."""
    _, _, speed, paused = clock.state()
    return {"now": clock.now().isoformat(timespec="seconds"), "speed": speed, "paused": paused}


@app.post("/clock")
async def set_clock(request: Request) -> dict:
    """Change the clock: ``{"speed", "paused", "advance_minutes", "to": "HH:MM"}``, all optional."""
    body = await request.json()
    clock.update(
        speed=body.get("speed"),
        paused=body.get("paused"),
        advance_minutes=int(body.get("advance_minutes", 0)),
        to=body.get("to"),
    )
    return get_clock()


@app.get("/v1/forecast")
def forecast(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    daily: str = "precipitation_sum,temperature_2m_max",
) -> dict:
    """Return the daily forecast in Open-Meteo's shape, for the days asked (at most 16)."""
    try:
        first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    days = [first + timedelta(days=n) for n in range(min((last - first).days + 1, 16))]
    found = [weather(d) for d in days]
    fields = {"precipitation_sum": "rain_mm", "temperature_2m_max": "temp_max"}
    wanted = [f for f in daily.split(",") if f in fields]
    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "Europe/London",
        "daily_units": {"time": "iso8601", "precipitation_sum": "mm", "temperature_2m_max": "°C"},
        "daily": {
            "time": [d.isoformat() for d in days],
            **{f: [w[fields[f]] for w in found] for f in wanted},
        },
    }


@app.get("/health")
def health() -> dict:
    """Answer 200 once the tools hold their history, 503 until then (compose's healthcheck)."""
    if _get("seeded") != "1":
        raise HTTPException(status_code=503, detail="seeding the tools' history")
    return {"seeded": True}


@app.post("/scenario/{name}")
def scenario(name: str) -> dict:
    """Act out a scenario now."""
    if name not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"no scenario {name!r}")
    run_scenario(name)
    return {"scenario": name}


@app.get("/tour")
def get_tour() -> dict:
    """Return the tour playing, if any, with each of its steps."""
    return guide.state()


@app.post("/tour/next")
def tour_next() -> dict:
    """Move the tour on to its next step."""
    guide.next()
    return guide.state()


@app.post("/tour/act")
def tour_act() -> dict:
    """Confirm the drafts the tour's current step waits for."""
    return {"confirmed": guide.act()}


@app.post("/tour/stop")
def tour_stop() -> dict:
    """Stop the tour."""
    guide.stop()
    return guide.state()


@app.post("/tour/{name}")
def tour_start(name: str) -> dict:
    """Play a tour, instead of any playing."""
    if name not in TOURS:
        raise HTTPException(status_code=404, detail=f"no tour {name!r}")
    guide.start(name)
    return guide.state()


@app.get("/feed")
def get_feed() -> dict:
    """Return the console's feed, newest first."""
    return {"feed": [{"at": at, "text": text} for at, text in feed]}


@app.get("/", response_class=HTMLResponse)
def console() -> str:
    """The console: the clock, scenarios, and what's happening."""
    links = " · ".join(f"<a href='{url}' target=_blank>{name}</a>" for name, url in LINKS.items())
    scenarios = "".join(
        f"<button data-scenario='{key}' title='{title}'>{title}</button>"
        for key, title in SCENARIOS.items()
    )
    tours = "".join(
        f'<button data-tour="{key}">{html.escape(tour.title)}</button>'
        for key, tour in TOURS.items()
    )
    body = f"""
<section class=panel><h2>Clock</h2>
<div class=row><strong id=now style="font-size:22px">…</strong>
<span id=speed class=muted></span></div>
<div class=row style="margin-top:8px">
<button id=pause>Pause</button>
<label>Speed <select id=rate><option value=1>real time</option><option value=10>10×</option>
<option value=60>60× (a day in 24 min)</option><option value=300>300×</option></select></label>
<button data-advance=60>+1 hour</button><button data-to="07:00">To 07:00</button>
<button data-to="17:00">To 17:00</button></div></section>
<section class=panel><h2>Tours</h2>
<p class=muted style="margin:0 0 8px">A flow played end to end: each step says what to look at,
and the tour moves on when the bakery gets there. The clock stops while it plays.</p>
<div class=row>{tours}</div><div id=tour></div></section>
<section class=panel><h2>Scenarios</h2><div class=row>{scenarios}</div></section>
<section class=panel><h2>Tools</h2><p>{links}</p></section>
<section class=panel><h2>What's happening</h2><table id=feed></table></section>
<script>
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
const post = (url, body) => fetch(url, {{method: 'POST',
  headers: {{'Content-Type': 'application/json'}},
  body: JSON.stringify(body || {{}})}});
let paused = false;
async function refresh() {{
  const c = await (await fetch('/clock')).json();
  paused = c.paused;
  const d = new Date(c.now);
  document.getElementById('now').textContent = d.toLocaleString([], {{weekday: 'long',
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}});
  document.getElementById('speed').textContent = c.paused ? 'paused' : `${{c.speed}}×`;
  document.getElementById('pause').textContent = c.paused ? 'Resume' : 'Pause';
  const rate = document.getElementById('rate');
  if (document.activeElement !== rate) rate.value = String(c.speed);
  const f = await (await fetch('/feed')).json();
  document.getElementById('feed').innerHTML = f.feed.map(e =>
    `<tr><td class=muted style="white-space:nowrap">${{esc(e.at)}}</td>
     <td>${{esc(e.text)}}</td></tr>`).join('');
  renderTour(await (await fetch('/tour')).json());
}}
const md = s => esc(s).replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
  .replace(/`(.+?)`/g, '<code>$1</code>');
function tourStep(s) {{
  const mark = s.status === 'done' ? '✓ ' : '';
  const style = s.status === 'current'
    ? 'border-left:3px solid var(--accent);padding-left:8px'
    : s.status === 'later' ? 'opacity:.5' : '';
  const seen = s.seen.length
    ? `<div class=muted>${{s.seen.map(esc).join('<br>')}}</div>` : '';
  const look = s.status === 'current' && s.url
    ? ` <a href="${{esc(s.url)}}" target=_blank>Open ${{esc(s.look)}}</a>` : '';
  const waits = s.waits
    ? `<div class=muted>${{s.slow ? 'Nothing yet after a minute. Is the bakery up? '
      + '<strong>Next</strong> skips this step.' : 'Waiting for the bakery…'}}</div>` : '';
  return `<li style="${{style}}">${{mark}}${{md(s.say)}}${{look}}${{seen}}${{waits}}</li>`;
}}
let tourHtml = '';
function renderTour(t) {{
  let html = '';
  if (t.tour) {{
    const acts = t.steps.some(s => s.acts);
    html = `<h3 style="margin:12px 0 6px;font-size:14px">${{esc(t.title)}}`
      + `${{t.done ? ' <span class=muted>(done)</span>' : ''}}</h3>`
      + `<ol style="margin:0 0 8px;padding-left:20px;display:grid;gap:8px">`
      + t.steps.map(tourStep).join('') + '</ol>'
      + (t.error ? `<p style="color:#c0392b;margin:0 0 8px">${{esc(t.error)}}</p>` : '')
      + '<div class=row>'
      + (t.done ? '' : '<button data-tour-do=next>Next</button>')
      + (acts ? '<button class=primary data-tour-do=act>Do it for me</button>' : '')
      + `<button data-tour-do=stop>${{t.done ? 'Close' : 'Stop'}}</button></div>`;
  }}
  if (html !== tourHtml) {{
    tourHtml = html;
    document.getElementById('tour').innerHTML = html;
  }}
}}
document.getElementById('tour').onclick = async e => {{
  const b = e.target.closest('[data-tour-do]');
  if (!b) return;
  b.disabled = true; await post('/tour/' + b.dataset.tourDo); refresh();
}};
document.querySelectorAll('[data-tour]').forEach(b => b.onclick = async () => {{
  b.disabled = true; await post('/tour/' + b.dataset.tour); b.disabled = false; refresh();
}});
document.getElementById('pause').onclick = async () => {{
  await post('/clock', {{paused: !paused}}); refresh();
}};
document.getElementById('rate').onchange = async e => {{
  await post('/clock', {{speed: Number(e.target.value)}}); refresh();
}};
document.querySelectorAll('[data-advance]').forEach(b => b.onclick = async () => {{
  await post('/clock', {{advance_minutes: Number(b.dataset.advance)}}); refresh();
}});
document.querySelectorAll('[data-to]').forEach(b => b.onclick = async () => {{
  await post('/clock', {{to: b.dataset.to}}); refresh();
}});
document.querySelectorAll('[data-scenario]').forEach(b => b.onclick = async () => {{
  b.disabled = true; await post('/scenario/' + b.dataset.scenario); b.disabled = false; refresh();
}});
refresh(); setInterval(refresh, 1000);
</script>"""
    return page("World", "the demo clock, scenarios, and what everyone's doing", body)
