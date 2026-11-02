"""Phase 5: suppliers' invoices, ingredient prices, margins, and new prices for restaurants.

Built from the components directly, as in ``test_daily_loop.py``: a bare
Notifications hub, each test inside one protocol call, and either no model
or a fake one. The invoices are the PDFs the world's suppliers send.
"""

import json
import random
import zlib
from datetime import date, datetime
from email.message import EmailMessage

import pytest
from app import services
from app.clients import Drive, Mail
from app.drafts import confirm_draft, reject_draft
from app.ingest import import_sheets, ingest_invoice
from app.margins import AccountManager, margins, proposed_price, what_if
from app.pdf import pdf_rows, pdf_text
from app.purchasing import InvoiceClerk, read_invoice
from app.reactions import Costing, Purchasing, Renegotiating
from app.repositories import (
    Allergens,
    BakeSheets,
    Contracts,
    Drafts,
    IngredientPrices,
    Ingredients,
    Invoices,
    Messages,
    OrderChanges,
    Products,
    Recipes,
    Restaurants,
    StandingOrders,
)
from app.services import Mailbox, parse_email
from app.storages import SQLite
from opendataframework import (
    Config,
    Events,
    Notification,
    Publisher,
    Subscriber,
    SubscriberProtocol,
    TaskProtocol,
)
from opendataframework.logger import LogManager
from opendataframework.notifications import Notifications
from tools import data, world
from tools.invoices import Line, delivery, invoice_pdf, pdf

KEYS = {
    Invoices: "repository.invoices",
    IngredientPrices: "repository.ingredient-prices",
    Drafts: "repository.drafts",
    Contracts: "repository.contracts",
    Products: "repository.products",
    Allergens: "repository.allergens",
}
SHEET_PRICES = {i.code: i.price for i in data.INGREDIENTS}
TUESDAY = date(2026, 11, 3)


class FakeClock:
    def now(self):
        return datetime(2026, 11, 3, 9, 30)


class FakeModel:
    def __init__(self, answer=None, available=True):
        self.answer, self._available = answer, available
        self.asked = []
        self.author = "model:fake"

    def available(self):
        return self._available

    def ask(self, system, prompt, schema):
        self.asked.append(prompt)
        return self.answer


class FakeSender:
    def __init__(self):
        self.sent = []

    def send(self, *args):
        self.sent.append(args)
        return "id"


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
    """Run each test inside one protocol call, as the Context runs a publisher's."""
    with Events().notify("test.bakery", TaskProtocol, "execute"):
        yield


@pytest.fixture
def drive_path(tmp_path):
    data.write_sheets(tmp_path / "drive", 7, "2026-12-31")
    return tmp_path / "drive"


@pytest.fixture
def bakery(drive_path, db, hub):
    """A bakery with the sheets imported, and its repositories by name."""
    repos = {
        "products": Products(db),
        "restaurants": Restaurants(db),
        "standing_orders": StandingOrders(db),
        "contracts": Contracts(db),
        "ingredients": Ingredients(db),
        "recipes": Recipes(db),
        "allergens": Allergens(db),
        "messages": Messages(db),
        "invoices": Invoices(db),
        "prices": IngredientPrices(db),
        "drafts": Drafts(db),
        "order_changes": OrderChanges(db),
        "sheets": BakeSheets(db),
    }
    import_sheets(
        Drive(Config({"component": {"drive": {"path": str(drive_path)}}})),
        *(repos[k] for k in ("products", "restaurants", "standing_orders", "contracts")),
        repos["ingredients"],
        repos["recipes"],
        repos["allergens"],
        repos["messages"],
        hub.bound_to("function.import-sheets", Publisher.of(import_sheets)),
        announce=False,
    )
    return repos


def _invoice(bakery, hub, supplier="Vale Dairy", prices=None, n=1, announce=False):
    """Take in the world's invoice from ``supplier`` at ``prices`` (the sheet's by default)."""
    s = data.BY_SUPPLIER[supplier]
    lines = delivery(s, SHEET_PRICES | (prices or {}), random.Random(n))
    content = invoice_pdf(s, f"INV-{n}", TUESDAY, lines)
    return ingest_invoice(
        f"<{n}@{s.email.split('@')[1]}>",
        s.email,
        s.name,
        f"Invoice INV-{n}",
        f"INV-{n}.pdf",
        content,
        datetime(2026, 11, 3, 9, 0).timestamp() + n,
        bakery["invoices"],
        hub.bound_to("function.ingest-invoice", Publisher.of(ingest_invoice)),
        announce=announce,
    )


def _clerk(bakery, hub, model=None):
    return InvoiceClerk(
        FakeClock(),
        bakery["invoices"],
        bakery["ingredients"],
        bakery["prices"],
        bakery["drafts"],
        model or FakeModel(available=False),
        hub.bound_to("agent.invoice-clerk", Publisher.of(InvoiceClerk)),
    )


def _repos(bakery, *names):
    return [bakery[n] for n in names]


def _margins(bakery, restaurant=""):
    return margins(
        *_repos(bakery, "contracts", "standing_orders", "products", "recipes"),
        *_repos(bakery, "ingredients", "prices"),
        restaurant=restaurant,
    )


def _what_if(bakery, ingredient, price):
    return what_if(
        ingredient,
        price,
        *_repos(bakery, "contracts", "standing_orders", "products", "recipes"),
        *_repos(bakery, "ingredients", "prices"),
    )


def _costing(bakery, hub):
    return Costing(
        *_repos(bakery, "contracts", "standing_orders", "products", "recipes"),
        *_repos(bakery, "ingredients", "prices"),
        hub.bound_to("component.costing", Publisher.of(Costing)),
    )


def _account_manager(bakery, hub, model=None):
    return AccountManager(
        FakeClock(),
        *_repos(bakery, "contracts", "standing_orders", "products", "recipes"),
        *_repos(bakery, "ingredients", "prices", "drafts"),
        model or FakeModel(available=False),
        hub.bound_to("agent.account-manager", Publisher.of(AccountManager)),
    )


def _confirm(bakery, hub, draft_id, mail=None):
    return confirm_draft(
        draft_id,
        *_repos(bakery, "drafts", "messages", "order_changes", "sheets", "restaurants"),
        *_repos(bakery, "invoices", "ingredients", "prices"),
        FakeSender(),
        mail or FakeSender(),
        hub.bound_to("function.confirm-draft", Publisher.of(confirm_draft)),
        lambda date: [],
        lambda date: [],
    )


def _deliver(subscriber, key, notification):
    """Deliver ``notification`` the way the Context does: inside an ``on_notification()`` call."""
    with Events().notify(key, SubscriberProtocol, "on_notification"):
        subscriber.on_notification(notification)


def _spike(drive_path, monkeypatch):
    """The butter price the world's butter-spike scenario charges, for this drive."""
    monkeypatch.setattr(world, "SHARED_DRIVE", drive_path)
    monkeypatch.setattr(world, "price", lambda code: SHEET_PRICES[code])
    return world.spiked_butter()


# --- the PDFs ---


def test_an_invoice_pdf_reads_back_as_rows_of_cells():
    s = data.BY_SUPPLIER["Vale Dairy"]
    content = invoice_pdf(
        s, "VAL-2026-0001", TUESDAY, [Line("BUTTER", 40, 7.2), Line("MILK", 30, 0.95)]
    )

    rows = pdf_rows(content)

    assert content.startswith(b"%PDF-1.4") and content.rstrip().endswith(b"%%EOF")
    assert ["Invoice no.", "VAL-2026-0001"] in rows
    assert ["Unsalted butter", "40", "kg", "£7.20", "£288.00"] in rows
    assert ["Total", "£316.50"] in rows


def test_the_reader_inflates_compressed_streams_and_reads_escapes():
    plain = pdf([(50, 700, "F1", 10, r"Brioche (large) \ 2"), (300, 700, "F1", 10, "£3.00")])
    stream = plain.split(b"stream\n", 1)[1].split(b"endstream", 1)[0]
    packed = plain.replace(stream, zlib.compress(stream))

    assert pdf_rows(packed) == [[r"Brioche (large) \ 2", "£3.00"]]


def test_read_invoice_reads_a_typed_invoice_and_not_the_farms_note():
    s = data.BY_SUPPLIER["Millers Ltd"]
    lines = delivery(s, SHEET_PRICES, random.Random(3))
    read = read_invoice(pdf_rows(invoice_pdf(s, "MIL-2026-0007", TUESDAY, lines)))

    assert (read["number"], read["date"]) == ("MIL-2026-0007", "2026-11-03")
    assert [line["description"] for line in read["lines"]] == [
        "Strong white bread flour",
        "Dark rye flour",
        "Caster sugar",
        "Fresh yeast",
        "Fine sea salt",
    ]
    assert read["total"] == round(sum(line.amount for line in lines), 2)
    farm = data.BY_SUPPLIER["Hill Farm"]
    note = invoice_pdf(farm, "", TUESDAY, delivery(farm, SHEET_PRICES, random.Random(3)))
    assert read_invoice(pdf_rows(note)) is None
    assert "trays of 30 at £8.40 a tray" in pdf_text(note)


# --- taking invoices in ---


def test_ingest_invoice_takes_each_email_once_and_announces_it(bakery, hub):
    first = _invoice(bakery, hub, announce=True)

    assert _invoice(bakery, hub, announce=True) is None
    invoice = bakery["invoices"].get(first)
    assert (invoice.supplier, invoice.status, invoice.filename) == (
        "Vale Dairy",
        "new",
        "INV-1.pdf",
    )
    [received] = [n for n in hub.seen if n.topic == "invoices.received"]
    assert received.summary == "Vale Dairy: Invoice INV-1"
    assert (received.subject, received.record) == ("repository.invoices", first)


def test_parse_email_finds_the_attached_pdf():
    mail = EmailMessage()
    mail["From"] = "Vale Dairy <invoices@valedairy.example>"
    mail["Subject"] = "Invoice VAL-1"
    mail["Date"] = "Tue, 03 Nov 2026 09:00:00 +0000"
    mail.set_content("Please find attached.")
    mail.add_attachment(
        b"%PDF-1.4 ...", maintype="application", subtype="pdf", filename="VAL-1.pdf"
    )

    parsed = parse_email(mail.as_bytes())

    assert parsed["pdf"] == ("VAL-1.pdf", b"%PDF-1.4 ...")
    assert (parsed["name"], parsed["from"]) == ("Vale Dairy", "invoices@valedairy.example")


def test_the_mailbox_hands_an_email_with_a_pdf_to_ingest_invoice(db, monkeypatch):
    mail = EmailMessage()
    mail["From"] = "Vale Dairy <invoices@valedairy.example>"
    mail["Subject"] = "Invoice VAL-1"
    mail["Message-ID"] = "<val-1@valedairy.example>"
    mail.set_content("Attached.")
    mail.add_attachment(b"%PDF", maintype="application", subtype="pdf", filename="VAL-1.pdf")

    class POP3:
        def __init__(self, *args, **kwargs): ...
        def user(self, user): ...
        def pass_(self, password): ...
        def uidl(self):
            return b"+OK", [b"1 u1"], 0

        def retr(self, number):
            return b"+OK", mail.as_bytes().split(b"\n"), 0

        def quit(self): ...

    monkeypatch.setattr(services.poplib, "POP3", POP3)
    messages, invoices = [], []
    mailbox = Mailbox(
        Config({}),
        db,
        Mail(Config({})),
        lambda *args, **kwargs: messages.append(args),
        lambda *args, **kwargs: invoices.append((args, kwargs)),
        LogManager().logger_for("service.mailbox"),
    )

    assert mailbox.check() == 1
    [(args, kwargs)] = invoices
    assert args[:5] == (
        "<val-1@valedairy.example>", "invoices@valedairy.example", "Vale Dairy", "Invoice VAL-1",
        "VAL-1.pdf",
    )  # fmt: skip
    assert args[5] == b"%PDF" and kwargs == {"announce": False}
    assert messages == []


# --- the invoice-clerk ---


def test_the_clerk_records_a_typed_invoice_read_cleanly(bakery, hub):
    invoice_id = _invoice(bakery, hub)

    read = _clerk(bakery, hub).invoke(invoice_id)

    assert (read["status"], read["draft"]) == ("recorded", None)
    invoice = bakery["invoices"].get(invoice_id)
    assert (invoice.status, invoice.number, invoice.date) == ("recorded", "INV-1", "2026-11-03")
    assert bakery["prices"].latest() == {"BUTTER": 7.2, "MILK": 0.95}
    [changed] = [n for n in hub.seen if n.topic == "prices.changed"]
    assert changed.summary is None  # the same prices as the sheet's: not news
    assert bakery["drafts"].all() == []
    assert _clerk(bakery, hub).invoke(invoice_id)["status"] == "recorded"  # read once


def test_a_price_rise_is_a_warning_naming_it(bakery, hub):
    _clerk(bakery, hub).invoke(_invoice(bakery, hub, prices={"BUTTER": 11.15}))

    [changed] = [n for n in hub.seen if n.topic == "prices.changed"]
    assert changed.level == "warning"
    assert changed.summary == "Vale Dairy: butter up 55% (£7.20 to £11.15 a kg)"
    assert changed.subject == "repository.ingredient-prices"


def test_the_farms_note_waits_for_a_person_without_a_model(bakery, hub):
    invoice_id = _invoice(bakery, hub, supplier="Hill Farm")

    read = _clerk(bakery, hub).invoke(invoice_id)

    draft = bakery["drafts"].get(read["draft"])
    assert (draft.kind, draft.status, draft.author) == ("invoice", "needs-review", "nobody")
    assert "layout" in draft.note and "no model" in draft.note
    assert bakery["invoices"].get(invoice_id).status == "drafted"
    assert bakery["prices"].latest() == {}
    with pytest.raises(ValueError, match="needs-review"):
        _confirm(bakery, hub, draft.id)


def test_the_models_reading_of_the_farms_note_is_drafted_then_confirmed(bakery, hub):
    invoice_id = _invoice(bakery, hub, supplier="Hill Farm")
    eggs = delivery(data.BY_SUPPLIER["Hill Farm"], SHEET_PRICES, random.Random(1))[0]
    model = FakeModel(
        {"number": "", "date": "", "total": eggs.amount,
         "lines": [{"ingredient": "EGGS", "quantity": eggs.quantity, "unit_price": 0.28}]}
    )  # fmt: skip

    read = _clerk(bakery, hub, model).invoke(invoice_id)

    draft = bakery["drafts"].get(read["draft"])
    assert (draft.status, draft.author) == ("pending", "model:fake")
    assert "| Free-range eggs |" in draft.body and "EGGS: Free-range eggs" in model.asked[0]
    _confirm(bakery, hub, draft.id)
    assert bakery["prices"].latest() == {"EGGS": 0.28}
    assert bakery["invoices"].get(invoice_id).status == "recorded"
    assert [n.topic for n in hub.seen][-2:] == ["prices.changed", "drafts.confirmed"]
    assert hub.seen[-1].summary == "Invoice from Hill Farm: prices recorded"


@pytest.mark.parametrize(
    ("answer", "why"),
    [
        ({"total": 999.0, "lines": [{"ingredient": "EGGS", "quantity": 390, "unit_price": 0.28}]},
         "add up"),
        ({"total": 109.2, "lines": [{"ingredient": "BUTTER", "quantity": 390, "unit_price": 0.28}]},
         "supplier's ingredients"),
        ({"total": 3276.0, "lines": [{"ingredient": "EGGS", "quantity": 390, "unit_price": 8.4}]},
         "plausible"),
    ],
)  # fmt: skip
def test_a_model_reading_that_doesnt_check_out_is_for_review(bakery, hub, answer, why):
    read = _clerk(bakery, hub, FakeModel(answer)).invoke(
        _invoice(bakery, hub, supplier="Hill Farm")
    )

    draft = bakery["drafts"].get(read["draft"])
    assert draft.status == "needs-review"
    assert why in draft.note


def test_rejecting_an_invoices_reading_leaves_its_prices_out(bakery, hub):
    invoice_id = _invoice(bakery, hub, supplier="Hill Farm")
    draft_id = _clerk(bakery, hub).invoke(invoice_id)["draft"]

    reject_draft(
        draft_id,
        *_repos(bakery, "drafts", "messages", "invoices"),
        hub.bound_to("function.reject-draft", Publisher.of(reject_draft)),
        reason="Paid it by hand",
    )

    assert bakery["invoices"].get(invoice_id).status == "rejected"
    assert bakery["prices"].latest() == {}


# --- margins ---


def test_unit_costs_follow_the_latest_invoiced_price(bakery, hub):
    before = {r["sku"]: r["cost"] for r in _margins(bakery)["contracts"]}

    _clerk(bakery, hub).invoke(_invoice(bakery, hub, prices={"BUTTER": 8.2}))

    after = {r["sku"]: r["cost"] for r in _margins(bakery)["contracts"]}
    assert before["BRI"] == 2.45 and after["BRI"] == 2.53  # 80 g of butter at £1 more a kg
    assert after["CRO"] - before["CRO"] == pytest.approx(0.03, abs=0.005)
    assert after["BAG"] == before["BAG"]  # no butter in a baguette


def test_margins_count_only_what_a_restaurant_orders(bakery):
    found = _margins(bakery, restaurant="Kiln")

    ordered = {o.sku for o in bakery["standing_orders"].all() if o.restaurant == "Kiln"}
    assert {r["sku"] for r in found["contracts"]} == ordered
    assert found["below_cost"] == []
    assert found["weekly_margin"] == round(sum(r["weekly_margin"] for r in found["contracts"]), 2)


def test_the_world_spikes_butter_enough_for_exactly_two_contracts(bakery, drive_path, monkeypatch):
    spike = _spike(drive_path, monkeypatch)

    scenario = _what_if(bakery, "butter", spike)

    assert scenario["now"] == 7.2 and spike > 7.2
    assert len(scenario["below_cost"]) == 2
    assert scenario["weekly_margin"]["then"] < scenario["weekly_margin"]["now"]
    assert {r["sku"] for r in scenario["changed"]} <= {"BRI", "CRO", "PAC"}
    with pytest.raises(KeyError):
        _what_if(bakery, "saffron", 1.0)


def test_proposed_prices_are_cost_plus_the_target_rounded_up_to_5p():
    assert proposed_price(1.20) == pytest.approx(1.40)  # 1.38 up to 1.40
    assert proposed_price(2.0) == pytest.approx(2.30)


# --- reactions: costing, then new prices ---


def test_costing_names_the_contracts_an_invoice_puts_below_cost(
    bakery, hub, drive_path, monkeypatch
):
    spike = _spike(drive_path, monkeypatch)
    _clerk(bakery, hub).invoke(_invoice(bakery, hub, prices={"BUTTER": spike}))
    [changed] = [n for n in hub.seen if n.topic == "prices.changed"]

    _deliver(_costing(bakery, hub), "component.costing", changed)

    [below] = [n for n in hub.seen if n.topic == "margins.below-cost"]
    assert below.level == "warning" and below.summary.startswith("2 contracts now below cost: ")
    assert len(below.payload["contracts"]) == 2
    assert below.subject == "repository.contracts"
    thinnest = _costing(bakery, hub).details()["thinnest"]
    assert thinnest.endswith(" each") and ", -£0." in thinnest


def test_costing_says_nothing_when_no_contract_newly_falls_below_cost(bakery, hub):
    _clerk(bakery, hub).invoke(_invoice(bakery, hub, prices={"BUTTER": 7.5}))
    [changed] = [n for n in hub.seen if n.topic == "prices.changed"]

    _deliver(_costing(bakery, hub), "component.costing", changed)

    assert [n for n in hub.seen if n.topic == "margins.below-cost"] == []


def test_costing_charts_the_weekly_margin_by_restaurant(bakery, hub):
    costing = _costing(bakery, hub)

    chart = costing.chart()

    assert chart.startswith("<html>") and "<svg" in chart and "Kiln" in chart
    assert costing.details()["below cost"] == "none"


def test_the_account_manager_drafts_new_prices_and_confirming_emails_them(
    bakery, hub, drive_path, monkeypatch
):
    spike = _spike(drive_path, monkeypatch)
    _clerk(bakery, hub).invoke(_invoice(bakery, hub, prices={"BUTTER": spike}))
    [first, *_] = _margins(bakery)["below_cost"]

    drafted = _account_manager(bakery, hub).invoke(first["restaurant"])

    draft = bakery["drafts"].get(drafted["draft"])
    assert (draft.kind, draft.status, draft.restaurant) == (
        "renegotiation", "pending", first["restaurant"],
    )  # fmt: skip
    [change] = [c for c in drafted["changes"] if c["sku"] == first["sku"]]
    assert change["proposed"] == round(proposed_price(first["cost"]), 2) > change["price"]
    assert f"£{change['proposed']:.2f}" in draft.reply and draft.date == "2026-11-16"
    assert _account_manager(bakery, hub).invoke(first["restaurant"])["draft"] == draft.id
    mail = FakeSender()
    _confirm(bakery, hub, draft.id, mail=mail)
    [(to, subject, text)] = mail.sent
    restaurant = bakery["restaurants"].where("name", first["restaurant"])[0]
    assert (to, subject, text) == (restaurant.email, "Our prices from Mon 16 Nov", draft.reply)
    assert hub.seen[-1].summary == f"New prices for {first['restaurant']}: emailed"


def test_the_account_manager_has_nothing_to_draft_for_a_restaurant_that_pays(bakery, hub):
    assert _account_manager(bakery, hub).invoke("Kiln") == {"draft": None, "changes": []}


def test_the_model_only_writes_the_email_when_it_names_every_price(
    bakery, hub, drive_path, monkeypatch
):
    spike = _spike(drive_path, monkeypatch)
    _clerk(bakery, hub).invoke(_invoice(bakery, hub, prices={"BUTTER": spike}))
    restaurant = _margins(bakery)["below_cost"][0]["restaurant"]

    drafted = _account_manager(bakery, hub, FakeModel({"body": "Dear chef, prices are up."}))
    draft = bakery["drafts"].get(drafted.invoke(restaurant)["draft"])

    assert draft.author == "rules"  # the model's email left the prices out
    assert draft.reply.startswith(f"Hello {restaurant},")


def test_renegotiating_drafts_once_per_restaurant_named():
    invoked = []

    class Desk:
        def invoke(self, restaurant):
            invoked.append(restaurant)

    contracts = [{"restaurant": "Kiln"}, {"restaurant": "Kiln"}, {"restaurant": "Le Petit"}]
    Renegotiating(Desk()).on_notification(
        Notification(key="component.costing", topic="margins.below-cost",
                     payload={"contracts": contracts}, summary=None, level="warning",
                     subject=None, record=None, parent=None, ts=0.0)
    )  # fmt: skip

    assert invoked == ["Kiln", "Le Petit"]


def test_the_reactions_subscribe_as_the_chain_needs():
    assert (Subscriber.of(Purchasing).topics, Subscriber.of(Purchasing).deliver) == (
        ("invoices.received",), "background",
    )  # fmt: skip
    assert (Subscriber.of(Costing).topics, Subscriber.of(Costing).deliver) == (
        ("prices.changed",), "background",
    )  # fmt: skip
    assert Publisher.of(Costing) == ("margins.below-cost",)
    assert (Subscriber.of(Renegotiating).topics, Subscriber.of(Renegotiating).deliver) == (
        ("margins.below-cost",), "background",
    )  # fmt: skip
    assert set(Publisher.of(confirm_draft)) == {"drafts.confirmed", "prices.changed"}


def test_the_drafts_changes_are_json(bakery, hub):
    draft_id = _clerk(bakery, hub).invoke(_invoice(bakery, hub, supplier="Hill Farm"))["draft"]

    assert json.loads(bakery["drafts"].get(draft_id).changes)["lines"] == []


def test_the_drive_imports_quietly_at_start_a_sheet_never_imported(bakery, db, drive_path):
    # A bakery onboarded before the ingredients and recipes sheets existed.
    with db.lock:
        db.conn.execute("DELETE FROM ingredients")
        db.conn.execute("DELETE FROM recipes")
        db.conn.commit()
    calls = []
    watcher = services.SharedDrive(
        Config({"service": {"shared-drive": {"interval": 5}}}),
        Drive(Config({"component": {"drive": {"path": str(drive_path)}}})),
        db,
        lambda **kwargs: calls.append(kwargs),
        LogManager().logger_for("service.shared-drive"),
    )

    assert watcher.never_imported() == ["ingredients.csv", "recipes.csv"]  # allergens are there
    watcher.catch_up()
    assert calls == [{"announce": False}]

    bakery["ingredients"].save(bakery["ingredients"].entity("X", "X", "kg", "", "", 1.0))
    bakery["recipes"].save(bakery["recipes"].entity(None, "BAG", "X", 1.0))
    watcher.catch_up()
    assert calls == [{"announce": False}]  # nothing missing any more
