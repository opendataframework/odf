"""A business messenger: the chats restaurants send their order changes through.

Run with ``uvicorn tools.messenger:app --port 8002``. Its API follows the shape
business messaging platforms offer:

- Every message a restaurant sends is POSTed to ``MESSENGER_WEBHOOK_URL`` as
  ``{"object": "business_messaging", "entry": [{"changes": [{"field":
  "messages", "value": {"metadata", "contacts", "messages"}}]}]}``, signed in
  ``X-Signature-256: sha256=<hex HMAC-SHA256 of the body>`` with the app
  secret, and retried if the subscriber is down.
- ``POST /v1/{phone_number_id}/messages`` (bearer token) sends the bakery's
  reply: ``{"to": phone, "type": "text", "text": {"body": ...}}``.
- ``GET /v1/{phone_number_id}/messages`` (bearer token) returns the history,
  for an integration catching up.

Its page shows each restaurant's chat, and lets you write as the restaurant.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from tools.common import Outbox, connect, env, page, sign, sim_now
from tools.data import BAKERY_PHONE, BAKERY_PHONE_ID, BY_PHONE, RESTAURANTS

TOKEN = env("MESSENGER_TOKEN", "messenger-dev-token")
APP_SECRET = env("MESSENGER_APP_SECRET", "messenger-dev-secret")
WEBHOOK_URL = env("MESSENGER_WEBHOOK_URL", "http://bakery:4750/webhooks/messenger")

db, lock = connect("messenger")
with lock:
    db.execute(
        "CREATE TABLE IF NOT EXISTS messages (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " id TEXT UNIQUE NOT NULL, contact TEXT NOT NULL, direction TEXT NOT NULL,"
        " body TEXT NOT NULL, sent_at TEXT NOT NULL)"
    )
    db.commit()


def signature_headers(body: bytes) -> dict:
    """Return the ``X-Signature-256`` header for ``body``."""
    return {"X-Signature-256": f"sha256={sign(APP_SECRET, body)}"}


outbox = Outbox(db, lock, WEBHOOK_URL, signature_headers)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Deliver webhooks while the app runs."""
    outbox.start()
    yield
    outbox.stop()


app = FastAPI(title="Messenger", docs_url=None, redoc_url=None, lifespan=lifespan)


def _authorize(authorization: str | None) -> None:
    """Refuse a request without the API's bearer token."""
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="invalid token")


def _store(message_id: str, contact: str, direction: str, body: str, sent_at: str) -> None:
    """Save one message; one already stored is left as it is."""
    with lock:
        db.execute(
            "INSERT OR IGNORE INTO messages (id, contact, direction, body, sent_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (message_id, contact, direction, body, sent_at),
        )
        db.commit()


def _new_id() -> str:
    """Return a new message id."""
    with lock:
        seq = db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM messages").fetchone()[0]
    return f"msg_{seq:07d}"


def webhook_payload(message_id: str, phone: str, name: str, text: str, sent: float) -> dict:
    """Return the webhook body announcing one inbound text message."""
    return {
        "object": "business_messaging",
        "entry": [
            {
                "id": "bakery-account",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {
                                "phone_number_id": BAKERY_PHONE_ID,
                                "display_phone_number": BAKERY_PHONE,
                            },
                            "contacts": [{"profile": {"name": name}, "id": phone}],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": message_id,
                                    "timestamp": str(int(sent)),
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def receive(phone: str, text: str) -> str:
    """A restaurant sends ``text``: store it and queue its webhook. Returns the message id."""
    text = text.strip()
    if not text:
        raise ValueError("empty message")
    restaurant = BY_PHONE.get(phone)
    name = restaurant.name if restaurant else phone
    now = sim_now()
    message_id = _new_id()
    _store(message_id, phone, "in", text, now.isoformat(timespec="seconds"))
    outbox.add(message_id, webhook_payload(message_id, phone, name, text, now.timestamp()))
    return message_id


@app.post("/simulate/inbound")
async def simulate_inbound(request: Request) -> dict:
    """A restaurant writes to the bakery: ``{"from": phone, "text": ...}``."""
    body = await request.json()
    try:
        return {"id": receive(body["from"], body["text"])}
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/{phone_number_id}/messages")
async def send(
    phone_number_id: str, request: Request, authorization: str | None = Header(default=None)
) -> dict:
    """The bakery sends a text: ``{"to": phone, "type": "text", "text": {"body": ...}}``."""
    _authorize(authorization)
    if phone_number_id != BAKERY_PHONE_ID:
        raise HTTPException(status_code=404, detail="unknown phone number id")
    body = await request.json()
    try:
        to, text = body["to"], body["text"]["body"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="needs to and text.body") from exc
    message_id = _new_id()
    _store(message_id, to, "out", text, sim_now().isoformat(timespec="seconds"))
    return {"messages": [{"id": message_id}]}


@app.get("/v1/{phone_number_id}/messages")
def history(
    phone_number_id: str, since: str | None = None, authorization: str | None = Header(default=None)
) -> dict:
    """Return every message, oldest first, or those sent after ``since`` (ISO time)."""
    _authorize(authorization)
    if phone_number_id != BAKERY_PHONE_ID:
        raise HTTPException(status_code=404, detail="unknown phone number id")
    with lock:
        rows = db.execute(
            "SELECT id, contact, direction, body, sent_at FROM messages"
            " WHERE sent_at > ? ORDER BY seq",
            (since or "",),
        ).fetchall()
    return {
        "messages": [
            {
                "id": r[0],
                "contact": r[1],
                "name": BY_PHONE[r[1]].name if r[1] in BY_PHONE else r[1],
                "direction": r[2],
                "text": r[3],
                "sent_at": r[4],
            }
            for r in rows
        ]
    }


@app.post("/admin/import")
async def import_messages(
    request: Request, authorization: str | None = Header(default=None)
) -> dict:
    """Store past messages as they are, without webhooks: the simulation's history."""
    _authorize(authorization)
    messages = (await request.json())["messages"]
    for m in messages:
        _store(m["id"], m["contact"], m["direction"], m["text"], m["sent_at"])
    return {"imported": len(messages)}


@app.get("/ui/thread/{phone}")
def thread(phone: str) -> dict:
    """Return one chat, oldest first, and the latest webhook deliveries."""
    with lock:
        rows = db.execute(
            "SELECT direction, body, sent_at FROM messages WHERE contact = ? ORDER BY seq",
            (phone,),
        ).fetchall()
    return {
        "messages": [{"direction": d, "text": b, "sent_at": s} for d, b, s in rows],
        "deliveries": outbox.recent(5),
    }


@app.get("/", response_class=HTMLResponse)
def chats() -> str:
    """The chats: pick a restaurant and write to the bakery as it."""
    options = "".join(f"<option value='{r.phone}'>{r.name}</option>" for r in RESTAURANTS)
    body = f"""
<section class=panel><h2>Chat</h2>
<div class=row><label>Writing as <select id=who>{options}</select></label></div>
<div id=thread style="margin:12px 0;display:flex;flex-direction:column;gap:6px;
  max-height:50vh;overflow:auto"></div>
<form id=send class=row><input id=text style="flex:1" autocomplete=off
  placeholder="e.g. 2 extra baguettes tomorrow please">
<button class=primary>Send to the bakery</button></form></section>
<section class=panel><h2>Webhook deliveries</h2><table id=deliveries></table></section>
<script>
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
async function refresh() {{
  const who = document.getElementById('who').value;
  const r = await (await fetch('/ui/thread/' + encodeURIComponent(who))).json();
  const box = document.getElementById('thread');
  const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 4;
  box.innerHTML = r.messages.map(m => `<div style="align-self:${{
      m.direction === 'in' ? 'flex-end' : 'flex-start'}};max-width:70%;padding:6px 10px;
      border-radius:10px;border:1px solid var(--line);background:${{
      m.direction === 'in' ? 'var(--bg)' : 'var(--panel)'}}">${{esc(m.text)}}
      <div class=muted style="font-size:11px">${{
      m.direction === 'in' ? 'restaurant' : 'bakery'}} · ${{
      esc(m.sent_at.replace('T', ' '))}}</div></div>`).join('');
  if (atBottom) box.scrollTop = box.scrollHeight;
  document.getElementById('deliveries').innerHTML = r.deliveries.map(d =>
    `<tr><td>${{esc(d.id)}}</td><td>${{esc(d.status)}}</td><td>${{d.attempts}} attempt(s)</td>
      <td class=muted>${{esc(d.error || '')}}</td></tr>`).join('');
}}
document.getElementById('who').onchange = refresh;
document.getElementById('send').onsubmit = async e => {{
  e.preventDefault();
  const input = document.getElementById('text');
  if (!input.value.trim()) return;
  await fetch('/simulate/inbound', {{method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{from: document.getElementById('who').value, text: input.value}})}});
  input.value = ''; refresh();
}};
refresh(); setInterval(refresh, 2000);
</script>"""
    return page("Messenger", "the restaurants' chats with the bakery", body)
