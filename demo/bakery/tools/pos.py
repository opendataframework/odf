"""The café's point of sale: a till, a REST API, and signed ``order.created`` webhooks.

Run with ``uvicorn tools.pos:app --port 8001``. Its API is what a POS vendor
offers an integration:

- ``GET /v1/orders`` (bearer token): orders, oldest first, paged by ``cursor``
  and filtered by ``created_after``.
- ``POST /v1/orders`` (bearer token): ring up an order.
- Every order taken is POSTed to ``POS_WEBHOOK_URL`` as an ``order.created``
  event, signed in ``X-Pos-Signature: t=<unix time>,v1=<hex HMAC-SHA256 of
  "<t>.<body>">``, and retried with backoff if the subscriber is down.

``/admin/...`` is the simulation's back door: importing history, and dropping
the next webhook for the "missed webhook" scenario.
"""

import json
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from tools.common import Outbox, connect, env, page, sign, sim_now
from tools.data import BY_SKU, PRODUCTS

TOKEN = env("POS_TOKEN", "pos-dev-token")
WEBHOOK_SECRET = env("POS_WEBHOOK_SECRET", "pos-dev-secret")
WEBHOOK_URL = env("POS_WEBHOOK_URL", "http://bakery:4750/webhooks/pos")

db, lock = connect("pos")
with lock:
    db.execute(
        "CREATE TABLE IF NOT EXISTS orders (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " id TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL)"
    )
    db.execute("CREATE TABLE IF NOT EXISTS flags (name TEXT PRIMARY KEY, value TEXT)")
    db.commit()


def signature_headers(body: bytes) -> dict:
    """Return the ``X-Pos-Signature`` header for ``body``, signed now."""
    t = str(int(time.time()))
    return {"X-Pos-Signature": f"t={t},v1={sign(WEBHOOK_SECRET, f'{t}.'.encode() + body)}"}


outbox = Outbox(db, lock, WEBHOOK_URL, signature_headers)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Deliver webhooks while the app runs."""
    outbox.start()
    yield
    outbox.stop()


app = FastAPI(title="POS", docs_url=None, redoc_url=None, lifespan=lifespan)


def _authorize(authorization: str | None) -> None:
    """Refuse a request without the API's bearer token."""
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="invalid token")


def _next_id(prefix: str) -> str:
    """Return a new id, ``<prefix>_<number>``, unique within this POS."""
    with lock:
        seq = db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM orders").fetchone()[0]
    return f"{prefix}_{seq:07d}"


def build_order(items: list[dict], tender: str, created_at: datetime, order_id: str) -> dict:
    """Return an order, priced from the catalogue.

    Args:
        items: ``{"sku", "quantity"}`` dicts.
        tender: ``"card"`` or ``"cash"``.
        created_at: When it was rung up, on the demo clock.
        order_id: Its id.

    Raises:
        ValueError: If an item isn't on the catalogue or its quantity isn't positive.
    """
    lines = []
    for item in items:
        product = BY_SKU.get(item.get("sku"))
        quantity = int(item.get("quantity", 1))
        if product is None or quantity < 1:
            raise ValueError(f"unknown item or quantity: {item!r}")
        lines.append(
            {
                "sku": product.sku,
                "name": product.name,
                "quantity": quantity,
                "unit_price": product.cafe_price,
            }
        )
    if not lines:
        raise ValueError("an order needs at least one item")
    total = round(sum(line["quantity"] * line["unit_price"] for line in lines), 2)
    return {
        "id": order_id,
        "created_at": created_at.isoformat(timespec="seconds"),
        "location": "cafe",
        "line_items": lines,
        "total": total,
        "tender": tender,
    }


def _store(order: dict) -> None:
    """Save ``order``; an order already stored is left as it is."""
    with lock:
        db.execute(
            "INSERT OR IGNORE INTO orders (id, created_at, body) VALUES (?, ?, ?)",
            (order["id"], order["created_at"], json.dumps(order)),
        )
        db.commit()


def take_order(items: list[dict], tender: str = "card") -> dict:
    """Ring up an order now, store it, and queue its ``order.created`` webhook."""
    order = build_order(items, tender, sim_now(), _next_id("ord"))
    _store(order)
    with lock:
        drop = db.execute("SELECT value FROM flags WHERE name = 'drop-next'").fetchone()
        if drop:
            db.execute("DELETE FROM flags WHERE name = 'drop-next'")
            db.commit()
    event = {
        "id": "evt_" + order["id"].removeprefix("ord_"),
        "type": "order.created",
        "created_at": order["created_at"],
        "data": {"object": order},
    }
    outbox.add(event["id"], event, drop=bool(drop))
    return order


@app.get("/v1/orders")
def list_orders(
    created_after: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    authorization: str | None = Header(default=None),
) -> dict:
    """Return orders oldest first: ``{"orders": [...], "next_cursor": id or None}``."""
    _authorize(authorization)
    limit = max(1, min(limit, 500))
    query, args = "SELECT seq, body FROM orders WHERE 1 = 1", []
    if created_after:
        query += " AND created_at > ?"
        args.append(created_after)
    if cursor:
        query += " AND seq > (SELECT seq FROM orders WHERE id = ?)"
        args.append(cursor)
    query += " ORDER BY seq LIMIT ?"
    args.append(limit + 1)
    with lock:
        rows = db.execute(query, args).fetchall()
    orders = [json.loads(body) for _, body in rows[:limit]]
    more = len(rows) > limit
    return {"orders": orders, "next_cursor": orders[-1]["id"] if more and orders else None}


@app.post("/v1/orders", status_code=201)
async def create_order(request: Request, authorization: str | None = Header(default=None)) -> dict:
    """Ring up ``{"line_items": [{"sku", "quantity"}], "tender"}``."""
    _authorize(authorization)
    body = await request.json()
    try:
        return take_order(body.get("line_items", []), body.get("tender", "card"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/admin/import")
async def import_orders(request: Request, authorization: str | None = Header(default=None)) -> dict:
    """Store past orders as they are, without webhooks: the simulation's history."""
    _authorize(authorization)
    orders = (await request.json())["orders"]
    with lock:
        db.executemany(
            "INSERT OR IGNORE INTO orders (id, created_at, body) VALUES (?, ?, ?)",
            [(o["id"], o["created_at"], json.dumps(o)) for o in orders],
        )
        db.commit()
    return {"imported": len(orders)}


@app.post("/admin/drop-next-webhook")
def drop_next_webhook(authorization: str | None = Header(default=None)) -> dict:
    """Don't deliver the next order's webhook: a missed webhook, for reconciliation to find."""
    _authorize(authorization)
    with lock:
        db.execute("INSERT OR REPLACE INTO flags (name, value) VALUES ('drop-next', '1')")
        db.commit()
    return {"drop_next": True}


@app.get("/admin/state")
def state() -> dict:
    """Return how many orders there are, and the latest webhook deliveries."""
    with lock:
        count = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    return {"orders": count, "deliveries": outbox.recent()}


@app.post("/till/charge")
async def till_charge(request: Request) -> dict:
    """The till's own Charge button: ring up the cart, as staff at the counter would."""
    body = await request.json()
    try:
        return take_order(body.get("line_items", []), body.get("tender", "card"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/till/recent")
def till_recent() -> dict:
    """Return the latest orders and webhook deliveries, for the till page."""
    with lock:
        rows = db.execute("SELECT body FROM orders ORDER BY seq DESC LIMIT 12").fetchall()
    return {"orders": [json.loads(body) for (body,) in rows], "deliveries": outbox.recent(8)}


@app.get("/", response_class=HTMLResponse)
def till() -> str:
    """The till: tap items into a cart and charge it."""
    buttons = "".join(
        f"<button data-sku='{p.sku}'>{p.name}<br><span class=muted>£{p.cafe_price:.2f}</span>"
        "</button>"
        for p in PRODUCTS
    )
    body = f"""
<section class=panel><h2>Till</h2><div class=row id=items>{buttons}</div>
<p id=cart class=muted>Cart is empty</p>
<div class=row><button class=primary id=charge>Charge card</button>
<button id=clear>Clear</button></div></section>
<section class=panel><h2>Recent orders</h2><table id=orders></table></section>
<section class=panel><h2>Webhook deliveries</h2><table id=deliveries></table></section>
<script>
const cart = {{}};
const names = {json.dumps({p.sku: p.name for p in PRODUCTS})};
function drawCart() {{
  const parts = Object.entries(cart).map(([s, q]) => `${{q}} × ${{names[s]}}`);
  document.getElementById('cart').textContent = parts.length ? parts.join(', ') : 'Cart is empty';
}}
document.getElementById('items').addEventListener('click', e => {{
  const b = e.target.closest('button'); if (!b) return;
  cart[b.dataset.sku] = (cart[b.dataset.sku] || 0) + 1; drawCart();
}});
document.getElementById('clear').onclick = () => {{
  for (const k in cart) delete cart[k]; drawCart();
}};
document.getElementById('charge').onclick = async () => {{
  const line_items = Object.entries(cart).map(([sku, quantity]) => ({{sku, quantity}}));
  if (!line_items.length) return;
  await fetch('/till/charge', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{line_items, tender: 'card'}})}});
  for (const k in cart) delete cart[k]; drawCart(); refresh();
}};
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
async function refresh() {{
  const r = await (await fetch('/till/recent')).json();
  document.getElementById('orders').innerHTML = r.orders.map(o =>
    `<tr><td>${{esc(o.id)}}</td><td>${{esc(o.created_at.replace('T', ' '))}}</td><td>${{
      esc(o.line_items.map(l => l.quantity + ' × ' + l.name).join(', '))}}</td>
      <td>£${{o.total.toFixed(2)}}</td></tr>`).join('');
  document.getElementById('deliveries').innerHTML = r.deliveries.map(d =>
    `<tr><td>${{esc(d.id)}}</td><td>${{esc(d.status)}}</td><td>${{d.attempts}} attempt(s)</td>
      <td class=muted>${{esc(d.error || '')}}</td></tr>`).join('');
}}
refresh(); setInterval(refresh, 2000);
</script>"""
    return page("Café POS", "the till, its orders, and the webhooks it sends", body)
