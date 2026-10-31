import tomllib
from pathlib import Path

from app.components import Kitchen
from app.functions import take_order
from app.repositories import Orders, Pantry
from app.services import ORDERS, Counter
from app.tasks import Restock
from opendataframework.notifications import Notifications

# Deliberately builds the components directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/table_view/test_books.py. A bare Notifications hub stands in
# for the Context's: `key_of` resolves the repositories given as `subject`,
# and `bound_to` gives each publisher the view the Context would inject.

EXAMPLE_DIR = Path(__file__).resolve().parents[3] / "examples" / "26-notifications"
KEYS = {Orders: "repository.orders", Pantry: "repository.pantry"}


def _hub():
    hub = Notifications(key_of=KEYS.__getitem__)
    seen = []
    hub.subscribe(seen.append)
    return hub, seen


def _order(hub, orders, pantry):
    notifications = hub.bound_to("function.take-order")
    return lambda table, item: take_order(table, item, orders, pantry, notifications)


def test_take_order_saves_the_order_and_publishes_it():
    hub, seen = _hub()
    orders, pantry = Orders(), Pantry()

    order_id = _order(hub, orders, pantry)(4, "flat white")

    assert [(o.id, o.table, o.item) for o in orders.all()] == [(order_id, 4, "flat white")]
    assert pantry.get("milk").stock == 5
    received, ticket = seen
    assert (received.key, received.topic, received.summary) == (
        "function.take-order",
        "orders.received",
        "Table 4: flat white",
    )
    assert (received.subject, received.record) == ("repository.orders", order_id)
    assert (ticket.topic, ticket.summary) == ("kitchen.ticket", None)
    assert dict(ticket.payload) == {"order": order_id, "table": 4, "item": "flat white"}


def test_take_order_warns_when_stock_runs_low_and_refuses_when_out():
    hub, seen = _hub()
    orders, pantry = Orders(), Pantry()
    order = _order(hub, orders, pantry)

    first, second, third = (order(7, "oat flat white") for _ in range(3))

    assert first is not None and second is not None and third is None
    low = [n for n in seen if n.topic == "pantry.low"]
    assert [(n.level, n.summary) for n in low] == [
        ("warning", "Oat milk running low: 1 left"),
        ("warning", "Oat milk running low: the last used"),
    ]
    out = seen[-1]
    assert (out.topic, out.level, out.subject) == ("pantry.out", "error", "repository.pantry")
    assert out.summary == "Out of oat milk: table 7's oat flat white not taken"
    assert len(orders.all()) == 2


def test_kitchen_keeps_the_tickets_only():
    hub, _ = _hub()
    kitchen = Kitchen(hub.bound_to("component.kitchen"))

    _order(hub, Orders(), Pantry())(2, "croissant")
    hub.bound_to("function.take-order").publish("orders.received", {}, summary="not a ticket")

    assert kitchen.tickets == [{"order": 1, "table": 2, "item": "croissant"}]
    assert kitchen.details() == {"tickets": "1", "latest": "table 2: croissant"}
    kitchen.on_stop()


def test_counter_takes_the_orders_in_turn():
    taken = []
    counter = Counter({"service": {"counter": {"interval": 0.01}}}, lambda *o: taken.append(o))

    for _ in range(len(ORDERS) + 1):
        counter.tick()

    assert taken == [*ORDERS, ORDERS[0]]
    assert counter.interval == 0.01


def test_restock_refills_the_pantry_and_publishes_a_success():
    hub, seen = _hub()
    pantry = Pantry()
    _order(hub, Orders(), pantry)(1, "oat flat white")

    Restock(pantry, hub.bound_to("task.restock")).execute()

    assert pantry.get("oat milk").stock == 2
    restocked = seen[-1]
    assert (restocked.topic, restocked.level, restocked.summary) == (
        "pantry.restocked",
        "success",
        "Pantry restocked",
    )
    assert dict(restocked.payload) == {"milk": 6, "oat milk": 2, "croissants": 4}


def test_config_sets_the_counter_interval():
    config = tomllib.loads((EXAMPLE_DIR / "config.toml").read_text())

    assert config["service"]["counter"]["interval"] == 4.0
