import json

from app.clients import Messenger, Pos
from fastapi.testclient import TestClient
from opendataframework import Config
from tools import data, messenger, pos, world

# The simulated tools against the bakery's clients: what a tool signs and
# sends, the bakery's integration accepts and reads. Tools and clients use the
# same development secrets by default.

POS_AUTH = {"Authorization": f"Bearer {pos.TOKEN}"}
MESSENGER_AUTH = {"Authorization": f"Bearer {messenger.TOKEN}"}


def _outbox_body(outbox, event_id: str) -> bytes:
    with outbox.lock:
        return outbox.db.execute("SELECT body FROM outbox WHERE id = ?", (event_id,)).fetchone()[0]


def test_standing_orders_are_the_same_for_a_seed():
    assert data.standing_orders(7) == data.standing_orders(7)
    assert data.standing_orders(7) != data.standing_orders(8)


def test_write_sheets_writes_each_sheet_once(tmp_path):
    written = data.write_sheets(tmp_path, 7, "2026-12-31")
    (tmp_path / "products.csv").write_text("edited by the owner\n")

    again = data.write_sheets(tmp_path, 7, "2026-12-31")

    assert sorted(written) == [
        "contracts.csv",
        "products.csv",
        "restaurants.csv",
        "standing_orders.csv",
    ]
    assert again == []
    assert (tmp_path / "products.csv").read_text() == "edited by the owner\n"


def test_pos_api_needs_its_token():
    client = TestClient(pos.app)

    assert client.get("/v1/orders").status_code == 401
    assert client.get("/v1/orders", headers=POS_AUTH).status_code == 200


def test_pos_prices_an_order_and_queues_a_webhook_the_bakery_accepts():
    client = TestClient(pos.app)

    order = client.post(
        "/v1/orders",
        json={"line_items": [{"sku": "FLW", "quantity": 2}, {"sku": "CRO", "quantity": 1}]},
        headers=POS_AUTH,
    ).json()

    assert order["total"] == 2 * 3.40 + 2.40
    assert [line["name"] for line in order["line_items"]] == ["Flat white", "Croissant"]
    body = _outbox_body(pos.outbox, "evt_" + order["id"].removeprefix("ord_"))
    event = json.loads(body)
    assert event["type"] == "order.created"
    assert event["data"]["object"]["id"] == order["id"]
    bakery = Pos(Config({}))
    assert bakery.verify(pos.signature_headers(body)["X-Pos-Signature"], body)
    assert not bakery.verify(pos.signature_headers(body)["X-Pos-Signature"], body + b" ")


def test_pos_refuses_unknown_items():
    client = TestClient(pos.app)

    r = client.post("/v1/orders", json={"line_items": [{"sku": "NOPE"}]}, headers=POS_AUTH)

    assert r.status_code == 422


def test_pos_drops_the_next_webhook_when_told_to():
    client = TestClient(pos.app)
    client.post("/admin/drop-next-webhook", headers=POS_AUTH)

    dropped = pos.take_order([{"sku": "BAG", "quantity": 1}])
    kept = pos.take_order([{"sku": "BAG", "quantity": 1}])

    statuses = {d["id"]: d["status"] for d in pos.outbox.recent(50)}
    assert statuses["evt_" + dropped["id"].removeprefix("ord_")] == "dropped"
    assert statuses["evt_" + kept["id"].removeprefix("ord_")] == "pending"


def test_pos_pages_its_orders():
    client = TestClient(pos.app)
    for _ in range(3):
        pos.take_order([{"sku": "RYE", "quantity": 1}])

    first = client.get("/v1/orders?limit=2", headers=POS_AUTH).json()
    rest = client.get(
        f"/v1/orders?limit=500&cursor={first['next_cursor']}", headers=POS_AUTH
    ).json()

    ids = [o["id"] for o in first["orders"] + rest["orders"]]
    assert len(first["orders"]) == 2
    assert len(ids) == len(set(ids))
    assert rest["next_cursor"] is None


def test_messenger_sends_a_signed_webhook_the_bakery_reads():
    message_id = messenger.receive("+447700900201", "2 extra baguettes tomorrow please")

    body = _outbox_body(messenger.outbox, message_id)
    bakery = Messenger(Config({}))
    assert bakery.verify(messenger.signature_headers(body)["X-Signature-256"], body)
    assert not bakery.verify("sha256=0", body)
    [inbound] = Messenger.inbound(json.loads(body))
    assert inbound["id"] == message_id
    assert (inbound["from"], inbound["name"]) == ("+447700900201", "Le Petit")
    assert inbound["text"] == "2 extra baguettes tomorrow please"


def test_messenger_send_and_history_need_its_token():
    client = TestClient(messenger.app)
    path = f"/v1/{data.BAKERY_PHONE_ID}/messages"
    reply = {"to": "+447700900201", "type": "text", "text": {"body": "Noted, thanks!"}}

    assert client.post(path, json=reply).status_code == 401
    sent = client.post(path, json=reply, headers=MESSENGER_AUTH).json()
    history = client.get(path, headers=MESSENGER_AUTH).json()["messages"]

    assert history[-1]["id"] == sent["messages"][0]["id"]
    assert history[-1]["direction"] == "out"


def test_world_clock_pauses_and_moves_on():
    clock = world.clock
    clock.update(paused=True)
    paused_at = clock.now()

    clock.update(to="17:00")

    assert clock.now().strftime("%H:%M") == "17:00"
    assert clock.now() > paused_at
    clock.update(paused=False)


def test_world_clock_carries_on_from_where_it_was_held(monkeypatch):
    clock = world.clock
    now = world.time.time()
    monkeypatch.setattr(world.time, "time", lambda: now)
    clock.hold()
    held = clock.now()
    monkeypatch.setattr(world.time, "time", lambda: now + 3600)  # an hour with the world down

    clock.resume()

    assert clock.now() == held


def test_quarter_end_is_the_last_day_of_the_quarter():
    assert world._quarter_end(world.datetime(2026, 11, 3)).date().isoformat() == "2026-12-31"
    assert world._quarter_end(world.datetime(2026, 2, 3)).date().isoformat() == "2026-03-31"
