"""The world around the bakery: the demo clock, and everyone who uses the other tools.

Run with ``uvicorn tools.world:app --port 8000``. It isn't one of the
bakery's tools. It's the simulation's stage manager:

- **The clock.** Simulated time, ``SPEED`` simulated seconds per real second
  (60 by default: a day in 24 minutes). Every tool asks ``GET /clock`` for
  "now", and the console can pause it, change its speed or move it on.
- **The actors.** Café customers ring up orders at the POS through the
  morning; in the evening, restaurants message (or email) order changes for
  tomorrow.
- **The history.** On first start it writes the shared drive's sheets and
  seeds the tools with what a bakery that's been trading a while has: 12
  weeks of café orders, two weeks of chats, a month of email.
- **The weather.** A forecast in Open-Meteo's JSON shape, made up from the
  seed and the date, offline. Rain keeps café customers away.
- **Scenarios.** Buttons on the console: a party order, a café rush, a
  missed webhook, a rainy week, and so on.
"""

import random
import smtplib
import threading
import time
from collections import deque
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
    BY_SKU,
    FREEFORM_MESSAGES,
    MESSAGE_TEMPLATES,
    PLURALS,
    RESTAURANTS,
    WEEKDAYS,
    WHOLESALE,
    Restaurant,
    write_sheets,
)

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
    sender_name: str, sender: str, subject: str, text: str, sent: datetime | None = None
) -> None:
    """Someone emails the bakery, at ``sent`` (the simulated time now by default)."""
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender))
    msg["To"] = formataddr(("The Bakery", BAKERY_EMAIL))
    msg["Subject"] = subject
    msg["Date"] = format_datetime((sent or clock.now()).astimezone())
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[1])
    msg.set_content(text)
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


def tick(previous: datetime, now: datetime) -> None:
    """Act out every simulated minute from ``previous`` to ``now`` (at most the last hour)."""
    minute = max(previous, now - timedelta(hours=1)).replace(second=0, microsecond=0)
    while minute < now:
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
        if 17 <= minute.hour < 23:
            for restaurant in RESTAURANTS:
                if rng.random() < EVENING_RATE:
                    text = _order_change(rng)
                    if rng.random() < 0.3:
                        restaurant_email(restaurant, text)
                    else:
                        message(restaurant, text)


def seed_history() -> None:
    """Write the sheets, and fill the tools with the history of a bakery that's been trading."""
    if _get("seeded") == "1":
        return
    start = clock.now()
    r = random.Random(SEED)
    written = write_sheets(SHARED_DRIVE, SEED, _quarter_end(start).isoformat())
    _log(f"Shared drive: wrote {', '.join(written) or 'nothing (sheets already there)'}")

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
    for day in sorted(r.sample(range(1, 31), 8), reverse=True):
        at = (start - timedelta(days=day)).replace(hour=r.randint(8, 20), minute=r.randint(0, 59))
        if r.random() < 0.6:
            restaurant_email(r.choice(RESTAURANTS), _order_change(r), sent=at)
        else:
            email(
                "Millers Ltd",
                "accounts@millers.example",
                "Delivery confirmed",
                "Hello,\n\nYour flour delivery is confirmed for tomorrow morning.\n\nMillers Ltd",
                sent=at,
            )
    _log("Mail: sent a month of past emails")
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
}


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
}}
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
