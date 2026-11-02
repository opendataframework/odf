import json
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

import pytest
from app import services
from app.clients import Drive, Mail, Messenger, Pos
from app.ingest import gist, import_sheets, ingest_message, ingest_sale
from app.repositories import (
    CafeSales,
    Contracts,
    Ingredients,
    Messages,
    Products,
    Recipes,
    Restaurants,
    StandingOrders,
)
from app.services import Mailbox, WebhookReceiver, parse_email
from app.storages import SQLite
from app.tasks import ImportPosHistory, ReconcilePos
from opendataframework import Config, Events, Publisher, TaskProtocol
from opendataframework.logger import LogManager
from opendataframework.notifications import Notifications
from tools import data

# Deliberately builds the components directly rather than going through
# Project/Context — opening a Context starts the services, which would bind
# ports and reach for the tools. A bare Notifications hub stands in for the
# Context's: `key_of` resolves the repositories given as `subject`, and
# `bound_to(key, Publisher.of(...))` gives each publisher the view the Context
# would inject.

KEYS = {
    Messages: "repository.messages",
    CafeSales: "repository.cafe-sales",
    Products: "repository.products",
}


@pytest.fixture
def db(tmp_path):
    sqlite = SQLite(Config({"component": {"sqlite": {"path": str(tmp_path / "bakery.db")}}}))
    yield sqlite
    sqlite.on_stop()


@pytest.fixture
def hub():
    notifications = Notifications(key_of=KEYS.__getitem__)
    seen = []
    notifications.subscribe(seen.append)
    notifications.seen = seen
    return notifications


@pytest.fixture(autouse=True)
def in_a_call():
    """Run each test inside one protocol call, as the Context runs a publisher's.

    An injected ``Notifications`` publishes only while a call is in progress,
    so the notification records it as its ``parent``.
    """
    with Events().notify("test.bakery", TaskProtocol, "execute"):
        yield


@pytest.fixture
def drive(tmp_path):
    data.write_sheets(tmp_path / "drive", 7, "2026-12-31")
    return Drive(Config({"component": {"drive": {"path": str(tmp_path / "drive")}}}))


def _sheets(drive, db, hub, announce=False):
    return import_sheets(
        drive,
        Products(db),
        Restaurants(db),
        StandingOrders(db),
        Contracts(db),
        Ingredients(db),
        Recipes(db),
        Messages(db),
        hub.bound_to("function.import-sheets", Publisher.of(import_sheets)),
        announce=announce,
    )


def _order(order_id="ord_1"):
    return {
        "id": order_id,
        "created_at": "2026-11-02T08:15:00",
        "location": "cafe",
        "line_items": [
            {"sku": "FLW", "name": "Flat white", "quantity": 2, "unit_price": 3.4},
            {"sku": "CRO", "name": "Croissant", "quantity": 1, "unit_price": 2.4},
        ],
        "total": 9.2,
        "tender": "card",
    }


def test_import_sheets_fills_the_repositories_and_announces_it(drive, db, hub):
    counts = _sheets(drive, db, hub, announce=True)

    assert counts["products"] == len(data.PRODUCTS)
    assert counts["restaurants"] == len(data.RESTAURANTS)
    assert counts["standing orders"] == len(data.standing_orders(7))
    [changed] = hub.seen
    assert changed.topic == "sheets.changed"
    assert changed.summary.startswith("Sheets updated: 12 products, 8 restaurants")


def test_import_sheets_replaces_what_was_there(drive, db, hub):
    _sheets(drive, db, hub)
    rows = (drive.path / "restaurants.csv").read_text().splitlines()
    (drive.path / "restaurants.csv").write_text("\n".join(rows[:3]) + "\n")

    counts = _sheets(drive, db, hub)

    assert counts["restaurants"] == 2
    assert [r.name for r in Restaurants(db).all()] == ["Le Petit", "Harbour Kitchen"]


def test_ingest_message_matches_the_restaurant_and_announces_it_once(drive, db, hub):
    _sheets(drive, db, hub)
    messages, restaurants = Messages(db), Restaurants(db)
    notifications = hub.bound_to("function.ingest-message", Publisher.of(ingest_message))

    def take(external_id, sender):
        return ingest_message(
            "messenger",
            external_id,
            sender,
            "2 extra baguettes tomorrow please",
            1.0,
            messages,
            restaurants,
            notifications,
        )

    first, again = take("msg_1", "+447700900201"), take("msg_1", "+447700900201")
    stranger = take("msg_2", "+447700900999")

    assert again is None
    [mine, theirs] = sorted(messages.all(), key=lambda m: m.id)
    assert (mine.id, mine.restaurant) == (first, "Le Petit")
    assert (theirs.id, theirs.restaurant) == (stranger, None)
    assert [(n.topic, n.summary, n.subject, n.record) for n in hub.seen] == [
        (
            "messages.received",
            "Le Petit: 2 extra baguettes tomorrow please",
            "repository.messages",
            first,
        ),
        (
            "messages.received",
            "+447700900999: 2 extra baguettes tomorrow please",
            "repository.messages",
            stranger,
        ),
    ]


def test_ingest_message_matches_an_email_address_in_any_case(drive, db, hub):
    _sheets(drive, db, hub)

    ingest_message(
        "email",
        "<a@kiln.example>",
        "Kitchen@Kiln.example",
        "Hi,\n\nNo rye on Friday\n",
        1.0,
        Messages(db),
        Restaurants(db),
        hub.bound_to("function.ingest-message", Publisher.of(ingest_message)),
        subject="Order change",
    )

    [message] = Messages(db).all()
    assert message.restaurant == "Kiln"
    assert message.subject == "Order change"
    assert hub.seen[-1].summary == "Kiln: No rye on Friday"


def test_ingest_message_while_catching_up_announces_nothing(db, hub):
    ingest_message(
        "messenger",
        "msg_1",
        "+447700900201",
        "old news",
        1.0,
        Messages(db),
        Restaurants(db),
        hub.bound_to("function.ingest-message", Publisher.of(ingest_message)),
        announce=False,
    )

    assert len(Messages(db).all()) == 1
    assert hub.seen == []


def test_gist_skips_greetings():
    assert gist("Hi,\n\nNo croissants on Friday\n\nThanks") == "No croissants on Friday"
    assert gist("Dear Sam\nTwo extra loaves") == "Two extra loaves"
    assert (
        gist("Morning! Chef's off sick, keep it light") == "Morning! Chef's off sick, keep it light"
    )
    assert gist("Hello!") == "Hello!"


def test_ingest_sale_takes_an_order_once_without_a_summary(db, hub):
    sales = CafeSales(db)
    notifications = hub.bound_to("function.ingest-sale", Publisher.of(ingest_sale))

    assert ingest_sale(_order(), sales, notifications) is True
    assert ingest_sale(_order(), sales, notifications) is False

    assert [(s.sku, s.quantity, s.revenue) for s in sales.all()] == [
        ("FLW", 2, 6.8),
        ("CRO", 1, 2.4),
    ]
    [sale] = hub.seen
    assert (sale.topic, sale.summary) == ("pos.sale", None)
    assert dict(sale.payload) == {"order": "ord_1", "total": 9.2, "items": {"FLW": 2, "CRO": 1}}


def _receiver():
    taken = {"sales": [], "messages": []}
    receiver = WebhookReceiver(
        Config({}),
        Pos(Config({})),
        Messenger(Config({})),
        lambda order: taken["sales"].append(order) or True,
        lambda *args, **kwargs: taken["messages"].append(args) or 1,
        LogManager().logger_for("service.webhook-receiver"),
    )
    return receiver, taken


def test_webhook_receiver_takes_a_signed_pos_order():
    from tools import pos

    receiver, taken = _receiver()
    body = json.dumps(
        {"id": "evt_1", "type": "order.created", "data": {"object": _order()}}
    ).encode()

    status, answer = receiver.handle("/webhooks/pos", pos.signature_headers(body), body)

    assert (status, answer) == (200, {"received": "evt_1", "new": True})
    assert taken["sales"] == [_order()]


def test_webhook_receiver_refuses_a_bad_signature_before_reading_the_body():
    receiver, taken = _receiver()

    status, _ = receiver.handle("/webhooks/pos", {"X-Pos-Signature": "t=1,v1=00"}, b"not json")
    status_m, _ = receiver.handle("/webhooks/messenger", {"X-Signature-256": "sha256=0"}, b"{}")

    assert (status, status_m) == (401, 401)
    assert taken == {"sales": [], "messages": []}


def test_webhook_receiver_takes_each_message_in_a_messenger_webhook():
    from tools import messenger

    receiver, taken = _receiver()
    payload = messenger.webhook_payload(
        "msg_9", "+447700900203", "The Fig Tree", "No focaccia", 5.0
    )
    body = json.dumps(payload).encode()

    status, answer = receiver.handle("/webhooks/messenger", messenger.signature_headers(body), body)

    assert (status, answer) == (200, {"received": 1})
    assert taken["messages"] == [("messenger", "msg_9", "+447700900203", "No focaccia", 5.0)]


def test_webhook_receiver_answers_404_elsewhere():
    receiver, _ = _receiver()

    assert receiver.handle("/webhooks/nope", {}, b"")[0] == 404


def _email(sender: str, subject: str, text: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = f"Le Petit <{sender}>"
    msg["To"] = "orders@bakery.example"
    msg["Subject"] = subject
    msg["Date"] = format_datetime(data_datetime())
    msg["Message-ID"] = make_msgid(domain="lepetit.example")
    msg.set_content(text)
    return bytes(msg)


def data_datetime():
    from datetime import UTC, datetime

    return datetime(2026, 11, 2, 18, 30, tzinfo=UTC)


def test_parse_email_reads_sender_subject_text_and_date():
    mail = parse_email(_email("kitchen@lepetit.example", "Order change", "Hi,\n\n2 extra loaves"))

    assert mail["from"] == "kitchen@lepetit.example"
    assert mail["name"] == "Le Petit"
    assert mail["subject"] == "Order change"
    assert mail["text"] == "Hi,\n\n2 extra loaves"
    assert mail["sent"] == data_datetime().timestamp()
    assert mail["id"].endswith("@lepetit.example>")


def test_parse_email_reads_crlf_lines_as_plain_newlines():
    # POP3 hands each line over separately; joined with CRLF as on the wire.
    raw = b"\r\n".join(_email("kitchen@lepetit.example", "Order change", "Hi,\n\nTwo").split(b"\n"))

    assert parse_email(raw)["text"] == "Hi,\n\nTwo"


def test_import_sheets_matches_messages_that_came_before_their_restaurant(drive, db, hub):
    # The mailbox can take in mail before onboarding has imported the restaurants.
    ingest_message(
        "email",
        "<early@kiln.example>",
        "kitchen@kiln.example",
        "No rye on Friday",
        1.0,
        Messages(db),
        Restaurants(db),
        hub.bound_to("function.ingest-message", Publisher.of(ingest_message)),
        announce=False,
    )
    assert Messages(db).all()[0].restaurant is None

    _sheets(drive, db, hub)

    assert Messages(db).all()[0].restaurant == "Kiln"


class _FakePOP3:
    """A POP3 mailbox holding ``messages`` (uidl -> raw bytes)."""

    messages: dict[str, bytes] = {}

    def __init__(self, host, port, timeout):
        self.uids = list(self.messages)

    def user(self, user):
        pass

    def pass_(self, password):
        pass

    def uidl(self):
        return b"+OK", [f"{i + 1} {uid}".encode() for i, uid in enumerate(self.uids)], 0

    def retr(self, number):
        return b"+OK", self.messages[self.uids[number - 1]].split(b"\n"), 0

    def quit(self):
        pass


def test_mailbox_catches_up_quietly_then_announces_new_mail(db, monkeypatch):
    monkeypatch.setattr(services.poplib, "POP3", _FakePOP3)
    _FakePOP3.messages = {"u1": _email("kitchen@lepetit.example", "Old", "Hi,\n\nlast week's")}
    taken = []
    mailbox = Mailbox(
        Config({}),
        db,
        Mail(Config({})),
        lambda *args, **kwargs: taken.append((args, kwargs)) or 1,
        lambda *args, **kwargs: None,
        LogManager().logger_for("service.mailbox"),
    )

    first = mailbox.check()
    _FakePOP3.messages["u2"] = _email("kitchen@lepetit.example", "New", "Hi,\n\n3 baguettes")
    second = mailbox.check()
    third = mailbox.check()

    assert (first, second, third) == (1, 1, 0)
    assert [kwargs["announce"] for _, kwargs in taken] == [False, True]
    assert [kwargs["subject"] for _, kwargs in taken] == ["Old", "New"]


def test_mailbox_skips_the_bakerys_own_replies(db, monkeypatch):
    # The demo's mail server holds the replies the bakery sends, too.
    monkeypatch.setattr(services.poplib, "POP3", _FakePOP3)
    _FakePOP3.messages = {
        "u1": _email("kitchen@lepetit.example", "Order change", "Hi,\n\n3 baguettes"),
        "u2": _email("orders@bakery.example", "Re: Order change", "Thanks, noted"),
    }
    taken = []
    mailbox = Mailbox(
        Config({}),
        db,
        Mail(Config({})),
        lambda *args, **kwargs: taken.append(args) or 1,
        lambda *args, **kwargs: None,
        LogManager().logger_for("service.mailbox"),
    )

    assert mailbox.check() == 1
    assert [args[2] for args in taken] == ["kitchen@lepetit.example"]
    assert mailbox.check() == 0


class _FakePos:
    def __init__(self, orders):
        self._orders = orders
        self.asked = []

    def orders(self, created_after=None):
        self.asked.append(created_after)
        return iter(self._orders)


class _FakeClock:
    def now(self):
        from datetime import datetime

        return datetime(2026, 11, 2, 23, 30)


def test_import_pos_history_takes_every_order_once(db):
    sales = CafeSales(db)
    task = ImportPosHistory(
        _FakePos([_order("ord_1"), _order("ord_2")]), sales, LogManager().logger_for("t")
    )

    assert task.execute() == 2
    assert task.execute() == 2
    assert len(sales.all()) == 4


def test_reconcile_pos_takes_in_missed_orders_and_warns(db, hub):
    sales = CafeSales(db)
    notifications = hub.bound_to("function.ingest-sale", Publisher.of(ingest_sale))

    def take(order):
        return ingest_sale(order, sales, notifications)

    take(_order("ord_1"))
    pos = _FakePos([_order("ord_1"), _order("ord_2")])

    recovered = ReconcilePos(
        pos, _FakeClock(), take, hub.bound_to("task.reconcile-pos", Publisher.of(ReconcilePos))
    ).execute()

    assert recovered == 1
    assert pos.asked == ["2026-10-31T23:30:00"]
    warning = hub.seen[-1]
    assert (warning.topic, warning.level, warning.subject) == (
        "pos.reconciled",
        "warning",
        "repository.cafe-sales",
    )


def test_config_hides_only_the_sqlite_connection():
    import tomllib
    from pathlib import Path

    config = tomllib.loads((Path(data.__file__).parents[1] / "config.toml").read_text())

    assert config["ui"]["topology"]["components"] == [
        "clock",
        "pos",
        "messenger",
        "drive",
        "weather",
        "mail",
        "model",
        "drafting",
        "purchasing",
        "costing",
        "renegotiating",
    ]
    assert config["service"]["webhook-receiver"]["port"] == 4750
