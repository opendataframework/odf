"""Planning the bakery's day: the café's forecast, the bake sheet, the delivery run, leftovers.

All plain arithmetic, no model: these are the numbers a person checks a
draft against, so they have to be the same every time they're worked out.
Each is a ``@Function`` taking its day as ``"YYYY-MM-DD"``, or nothing for
the usual day on the demo clock, so the UI, MCP and the night run all call
them the same way.
"""

import math
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from opendataframework import Function

from app.clients import Clock, Weather
from app.entities import (
    BakeSheetLine,
    DeliveryStop,
    Forecast,
    Leftover,
    OrderChange,
    StandingOrder,
)
from app.repositories import (
    BakeSheets,
    CafeSales,
    DeliveryRuns,
    Forecasts,
    Leftovers,
    OrderChanges,
    Products,
    Restaurants,
    StandingOrders,
)

# Weeks of the same weekday the café's forecast averages over.
LOOKBACK_WEEKS = 6
# Extra baked for the café, as a share of its forecast, rounded up.
BUFFER = 0.1
# Products baked here, as opposed to the café's dishes and drinks.
BAKED = ("bread", "pastry")

# England and Wales bank holidays, when the café is busier. A real bakery
# would read them from gov.uk's bank-holidays.json; the demo keeps it offline.
BANK_HOLIDAYS = frozenset(
    date.fromisoformat(d)
    for d in (
        "2026-01-01", "2026-04-03", "2026-04-06", "2026-05-04", "2026-05-25", "2026-08-31",
        "2026-12-25", "2026-12-28", "2027-01-01", "2027-03-26", "2027-03-29", "2027-05-03",
        "2027-05-31", "2027-08-30", "2027-12-27", "2027-12-28",
    )
)  # fmt: skip
HOLIDAY_FACTOR = 1.25

# Where the van sets off from, and how it goes.
BAKERY = ("The Bakery", "1 Mill Yard", 51.4540, -2.5920)
DEPART = "05:30"
VAN_KMH = 20.0
MINUTES_PER_DROP = 5


def day_of(value: str, clock: Clock, days_ahead: int = 0) -> date:
    """Return ``value`` (``"YYYY-MM-DD"``) as a date, or the demo clock's today plus ``days_ahead``.

    Raises:
        ValueError: If ``value`` isn't a date.
    """
    if value:
        return date.fromisoformat(value)
    return clock.now().date() + timedelta(days=days_ahead)


def label(day: date) -> str:
    """Return ``day`` as a person writes it: ``"Tue 3 Nov"``."""
    return f"{day:%a} {day.day} {day:%b}"


def weather_factor(rain_mm: float, temp_max: float) -> float:
    """Return how the weather moves café sales: rain keeps people in, warmth brings them out."""
    if rain_mm >= 5:
        return 0.7
    if rain_mm >= 1:
        return 0.85
    if temp_max >= 22:
        return 1.1
    return 1.0


def wholesale_order(
    standing: Iterable[StandingOrder], changes: Iterable[OrderChange], day: date
) -> dict[str, dict[str, int]]:
    """Return what each restaurant takes on ``day``: its standing order with the changes applied.

    Args:
        standing: The standing orders for ``day``'s weekday.
        changes: The confirmed changes that apply on ``day`` (see
            ``OrderChanges.for_day``), in the order they were made.
        day: The day.

    Returns:
        ``{restaurant: {sku: quantity}}``, leaving out what comes to nothing.
    """
    orders: dict[str, dict[str, int]] = defaultdict(dict)
    for s in standing:
        orders[s.restaurant][s.sku] = orders[s.restaurant].get(s.sku, 0) + s.quantity
    usual = {(r, sku) for r, items in orders.items() for sku in items}
    # Lasting changes first, then that day's own, each in the order made.
    for c in sorted(changes, key=lambda c: (c.mode != "set-from", c.date, c.id or 0)):
        items = orders[c.restaurant]
        if c.mode == "set-from":
            if (c.restaurant, c.sku) in usual and c.date <= day.isoformat():
                items[c.sku] = c.quantity
        elif c.date == day.isoformat():
            base = items.get(c.sku, 0) if c.mode == "add" else 0
            items[c.sku] = base + c.quantity
    return {
        restaurant: {sku: q for sku, q in sorted(items.items()) if q > 0}
        for restaurant, items in sorted(orders.items())
        if any(q > 0 for q in items.values())
    }


def restaurant_orders(
    day: date, standing_orders: StandingOrders, order_changes: OrderChanges
) -> dict[str, dict[str, int]]:
    """Return what each restaurant takes on ``day``, from the repositories."""
    return wholesale_order(
        standing_orders.for_weekday(f"{day:%A}"), order_changes.for_day(day), day
    )


@Function
def forecast(
    clock: Clock,
    sales: CafeSales,
    products: Products,
    weather: Weather,
    forecasts: Forecasts,
    date: str = "",
) -> list[dict]:
    """Forecast what the café sells on a day: the weekday's recent average, times the weather.

    The average is over the same weekday in the last six weeks. Rain lowers
    it, a warm day raises it, and so does a bank holiday. The day's forecast
    replaces any earlier one.

    Args:
        clock: The demo clock, for "tomorrow", injected.
        sales: The café's past sales, injected.
        products: What the café sells, injected.
        weather: The weather forecast, injected.
        forecasts: Where the forecast is saved, injected.
        date: The day, ``"YYYY-MM-DD"``; tomorrow by default.

    Returns:
        Each product's forecast, as ``{"sku", "product", "baseline", "quantity"}``.
    """
    day = day_of(date, clock, days_ahead=1)
    weeks = [day - timedelta(weeks=n) for n in range(1, LOOKBACK_WEEKS + 1)]
    sold = sales.daily(min(weeks), max(weeks))
    trading = [d for d in weeks if any(key[0] == d.isoformat() for key in sold)]
    sky = weather.daily(day) or {"rain_mm": 0.0, "temp_max": 15.0}
    factor = weather_factor(sky["rain_mm"], sky["temp_max"])
    holiday = HOLIDAY_FACTOR if day in BANK_HOLIDAYS else 1.0
    rows = []
    for product in products.all():
        counts = [sold.get((d.isoformat(), product.sku), 0) for d in trading]
        baseline = sum(counts) / len(counts) if counts else 0.0
        rows.append(
            Forecast(
                id=None,
                date=day.isoformat(),
                sku=product.sku,
                product=product.name,
                baseline=round(baseline, 1),
                weather=factor,
                holiday=holiday,
                quantity=math.ceil(round(baseline * factor * holiday, 6)),
                rain_mm=sky["rain_mm"],
            )
        )
    forecasts.replace_where("date", day.isoformat(), rows)
    return [
        {"sku": r.sku, "product": r.product, "baseline": r.baseline, "quantity": r.quantity}
        for r in rows
    ]


@Function
def bake_sheet(
    clock: Clock,
    products: Products,
    standing_orders: StandingOrders,
    order_changes: OrderChanges,
    forecasts: Forecasts,
    sheets: BakeSheets,
    date: str = "",
) -> list[dict]:
    """Work out what to bake for a morning: the restaurants' orders plus the café's forecast.

    The restaurants' orders are their standing orders with every confirmed
    change applied. The café's share is its forecast for the day (run
    ``forecast`` first), plus a tenth in case it's busier. The day's sheet
    replaces any earlier one.

    Args:
        clock: The demo clock, for "tomorrow", injected.
        products: What the bakery bakes, injected.
        standing_orders: The restaurants' usual orders, injected.
        order_changes: The confirmed changes to them, injected.
        forecasts: The café's forecast, injected.
        sheets: Where the bake sheet is saved, injected.
        date: The morning, ``"YYYY-MM-DD"``; tomorrow by default.

    Returns:
        Each product to bake, as ``{"sku", "product", "wholesale", "cafe", "total"}``.
    """
    day = day_of(date, clock, days_ahead=1)
    wholesale: dict[str, int] = defaultdict(int)
    for items in restaurant_orders(day, standing_orders, order_changes).values():
        for sku, quantity in items.items():
            wholesale[sku] += quantity
    cafe = {f.sku: f.quantity for f in forecasts.where("date", day.isoformat())}
    lines = []
    for product in products.all():
        if product.kind not in BAKED:
            continue
        for_cafe = cafe.get(product.sku, 0)
        buffer = math.ceil(for_cafe * BUFFER)
        total = wholesale.get(product.sku, 0) + for_cafe + buffer
        if total:
            lines.append(
                BakeSheetLine(
                    id=None,
                    date=day.isoformat(),
                    sku=product.sku,
                    product=product.name,
                    wholesale=wholesale.get(product.sku, 0),
                    cafe=for_cafe,
                    buffer=buffer,
                    total=total,
                )
            )
    sheets.replace_where("date", day.isoformat(), lines)
    return [
        {
            "sku": line.sku,
            "product": line.product,
            "wholesale": line.wholesale,
            "cafe": line.cafe + line.buffer,
            "total": line.total,
        }
        for line in lines
    ]


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Return the distance between two ``(lat, lon)`` points, in kilometres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(h))


@Function
def plan_deliveries(
    clock: Clock,
    restaurants: Restaurants,
    products: Products,
    standing_orders: StandingOrders,
    order_changes: OrderChanges,
    runs: DeliveryRuns,
    date: str = "",
) -> list[dict]:
    """Plan a morning's delivery run: every restaurant with an order, earliest kitchen first.

    The van leaves at 05:30, drives at city speed and takes five minutes a
    drop. Stops go in the order the kitchens open, nearest first among those
    opening at the same time. The day's run replaces any earlier one.

    Args:
        clock: The demo clock, for "tomorrow", injected.
        restaurants: Where they are and when their kitchens open, injected.
        products: The products' names, injected.
        standing_orders: The restaurants' usual orders, injected.
        order_changes: The confirmed changes to them, injected.
        runs: Where the run is saved, injected.
        date: The morning, ``"YYYY-MM-DD"``; tomorrow by default.

    Returns:
        The stops, as ``{"stop", "restaurant", "eta", "arrive_by", "load"}``,
        with ``"late": True`` on any the van reaches after the kitchen opens.
    """
    day = day_of(date, clock, days_ahead=1)
    orders = restaurant_orders(day, standing_orders, order_changes)
    names = {p.sku: p.name for p in products.all()}
    name, address, lat, lon = BAKERY
    at = datetime.combine(day, datetime.strptime(DEPART, "%H:%M").time())
    stops = [DeliveryStop(None, day.isoformat(), 0, name, address, lat, lon, DEPART, DEPART, "", 0)]
    here = (lat, lon)
    todo = [r for r in restaurants.all() if r.name in orders]
    while todo:
        opens = min(r.kitchen_opens for r in todo)
        nearest = min(
            (r for r in todo if r.kitchen_opens == opens), key=lambda r: _km(here, (r.lat, r.lon))
        )
        todo.remove(nearest)
        at += timedelta(hours=_km(here, (nearest.lat, nearest.lon)) / VAN_KMH)
        here = (nearest.lat, nearest.lon)
        items = orders[nearest.name]
        stops.append(
            DeliveryStop(
                id=None,
                date=day.isoformat(),
                stop=len(stops),
                restaurant=nearest.name,
                address=nearest.address,
                lat=nearest.lat,
                lon=nearest.lon,
                arrive_by=nearest.kitchen_opens,
                eta=f"{at:%H:%M}",
                load=", ".join(f"{q} × {names.get(sku, sku)}" for sku, q in items.items()),
                items=sum(items.values()),
            )
        )
        at += timedelta(minutes=MINUTES_PER_DROP)
    runs.replace_where("date", day.isoformat(), stops)
    return [
        {
            "stop": s.stop,
            "restaurant": s.restaurant,
            "eta": s.eta,
            "arrive_by": s.arrive_by,
            "load": s.load,
            **({"late": True} if s.stop and s.eta > s.arrive_by else {}),
        }
        for s in stops[1:]
    ]


@Function
def count_leftovers(
    clock: Clock,
    sales: CafeSales,
    sheets: BakeSheets,
    leftovers: Leftovers,
    date: str = "",
) -> list[dict]:
    """Count what the café didn't sell of what was baked for it, once it has closed.

    Args:
        clock: The demo clock, for "today", injected.
        sales: The café's sales, injected.
        sheets: The day's bake sheet, for what was baked for the café, injected.
        leftovers: Where the count is saved, injected.
        date: The day, ``"YYYY-MM-DD"``; today by default.

    Returns:
        Each product baked for the café, as ``{"sku", "product", "baked",
        "sold", "unsold"}``. Empty if there was no bake sheet for the day.
    """
    day = day_of(date, clock)
    sold = sales.daily(day, day)
    rows = [
        Leftover(
            id=None,
            date=day.isoformat(),
            sku=line.sku,
            product=line.product,
            baked=line.cafe + line.buffer,
            sold=sold.get((day.isoformat(), line.sku), 0),
            unsold=max(0, line.cafe + line.buffer - sold.get((day.isoformat(), line.sku), 0)),
        )
        for line in sheets.where("date", day.isoformat())
        if line.cafe + line.buffer
    ]
    leftovers.replace_where("date", day.isoformat(), rows)
    return [
        {"sku": r.sku, "product": r.product, "baked": r.baked, "sold": r.sold, "unsold": r.unsold}
        for r in rows
    ]
