"""Phase 6: allergens a supplier declares, the labels they change, and the notices.

Uses ``test_purchasing``'s fixtures and helpers: a bakery with the sheets
imported, invoices from the world's suppliers, and a bare Notifications hub.
"""

# The fixtures imported from test_purchasing are used as parameters, which
# ruff takes for redefining them.
# ruff: noqa: F811

import json
import random

import pytest
from app.allergens import (
    AllergenOfficer,
    declared,
    labels,
    trace_ingredient,
)
from app.clients import Drive
from app.ingest import import_sheets, ingest_invoice
from app.pdf import pdf_rows
from app.purchasing import InvoiceClerk, read_invoice
from app.reactions import AllergenNotices, Labelling
from opendataframework import Config, Publisher, Subscriber
from tools import data, world
from tools.invoices import delivery, invoice_pdf

from .test_purchasing import (  # noqa: F401 (fixtures are used by name)
    TUESDAY,
    FakeClock,
    FakeSender,
    _clerk,
    _confirm,
    _deliver,
    _invoice,
    _repos,
    bakery,
    db,
    drive_path,
    hub,
    in_a_call,
)

SESAME = {"FLOUR": world.SESAME_NOTE}


def _labels(bakery):
    return {row["sku"]: row for row in labels(*_repos(bakery, "allergens", "recipes", "products"))}


def _trace(bakery, ingredient):
    return trace_ingredient(
        ingredient,
        *_repos(bakery, "ingredients", "allergens", "recipes", "products", "standing_orders"),
    )


def _labelling(bakery, hub):
    return Labelling(
        FakeClock(),
        *_repos(bakery, "ingredients", "allergens", "recipes", "products", "standing_orders"),
        hub.bound_to("component.labelling", Publisher.of(Labelling)),
    )


def _officer(bakery, hub):
    return AllergenOfficer(
        FakeClock(),
        *_repos(bakery, "ingredients", "allergens", "recipes", "products", "standing_orders"),
        *_repos(bakery, "restaurants", "drafts"),
        hub.bound_to("agent.allergen-officer", Publisher.of(AllergenOfficer)),
    )


def _substitution(bakery, hub, notes=SESAME, n=1):
    """Millers' invoice with ``notes`` under its lines, read by the clerk."""
    s = data.BY_SUPPLIER["Millers Ltd"]
    prices = {i.code: i.price for i in data.INGREDIENTS}
    lines = delivery(s, prices, random.Random(n), notes)
    invoice_id = ingest_invoice(
        f"<sub-{n}@millers.example>", s.email, s.name, f"Invoice MIL-{n}", f"MIL-{n}.pdf",
        invoice_pdf(s, f"MIL-{n}", TUESDAY, lines), 1793610000.0 + n, bakery["invoices"],
        hub.bound_to("function.ingest-invoice", Publisher.of(ingest_invoice)),
    )  # fmt: skip
    _clerk(bakery, hub).invoke(invoice_id)
    return invoice_id


def _published(hub, topic):
    return [n for n in hub.seen if n.topic == topic]


# --- reading what a supplier declares ---


@pytest.mark.parametrize(
    ("note", "found"),
    [
        ("Substituted: Hillside Mill strong white flour. May contain sesame.",
         [("sesame", "may contain")]),
        ("Contains milk and soya", [("milk", "contains"), ("soya", "contains")]),
        ("May contain tree nuts, peanut & sesame seeds",
         [("nuts", "may contain"), ("peanuts", "may contain"), ("sesame", "may contain")]),
        ("Contains wheat. May contain egg", [("gluten", "contains"), ("eggs", "may contain")]),
        ("Delivered late, sorry", []),
        ("Contains love", []),
    ],
)  # fmt: skip
def test_declared_reads_a_suppliers_allergen_statements(note, found):
    assert declared(note) == found


def test_read_invoice_keeps_a_note_under_its_line():
    s = data.BY_SUPPLIER["Millers Ltd"]
    prices = {i.code: i.price for i in data.INGREDIENTS}
    lines = delivery(s, prices, random.Random(1), SESAME)

    read = read_invoice(pdf_rows(invoice_pdf(s, "MIL-1", TUESDAY, lines)))

    assert read["lines"][0]["note"] == world.SESAME_NOTE
    assert all(line["note"] == "" for line in read["lines"][1:])


def test_the_clerk_records_the_prices_and_announces_the_substitution(bakery, hub):
    invoice_id = _substitution(bakery, hub)

    assert bakery["invoices"].get(invoice_id).status == "recorded"
    [changed] = _published(hub, "ingredients.changed")
    assert changed.summary == "Millers Ltd: strong white flour now may contain sesame"
    assert changed.level == "warning" and changed.record == invoice_id
    assert changed.payload["allergens"] == ({"allergen": "sesame", "kind": "may contain"},)
    assert [n.topic for n in hub.seen][-2:] == ["prices.changed", "ingredients.changed"]


def test_an_invoice_without_notes_changes_no_ingredient(bakery, hub):
    _substitution(bakery, hub, notes={})

    assert _published(hub, "ingredients.changed") == []
    assert "ingredients.changed" in Publisher.of(InvoiceClerk)


# --- labels and the trace ---


def test_labels_follow_the_recipes(bakery):
    found = _labels(bakery)

    assert found["BAG"]["label"] == "contains gluten"
    assert found["CRO"]["label"] == "contains eggs, gluten, milk"
    assert found["PAC"]["label"] == "contains eggs, gluten, milk, soya; may contain nuts"


def test_trace_ingredient_follows_flour_to_every_product_and_restaurant(bakery):
    found = _trace(bakery, "strong white flour")

    assert (found["ingredient"], found["supplier"]) == ("FLOUR", "Millers Ltd")
    assert found["allergens"] == {"gluten": "contains"}
    assert {p["sku"] for p in found["products"]} == {
        "SD-LOAF", "BAG", "RYE", "BRI", "FOC", "CRO", "PAC",
    }  # fmt: skip
    restaurants = {r.restaurant for r in bakery["standing_orders"].all()}
    assert {r["restaurant"] for r in found["restaurants"]} == restaurants
    with pytest.raises(KeyError):
        _trace(bakery, "saffron")


# --- reactions: labelling, then the notices ---


def test_labelling_records_the_allergen_and_names_the_labels_it_changes(bakery, hub):
    _substitution(bakery, hub)
    [changed] = _published(hub, "ingredients.changed")

    _deliver(_labelling(bakery, hub), "component.labelling", changed)

    assert _labels(bakery)["BAG"]["label"] == "contains gluten; may contain sesame"
    [added] = [a for a in bakery["allergens"].all() if a.source != "sheet"]
    assert (added.ingredient, added.allergen, added.kind) == ("FLOUR", "sesame", "may contain")
    [warned] = _published(hub, "allergens.changed")
    assert warned.level == "warning" and warned.subject == "repository.allergens"
    assert len(warned.payload["products"]) == 7
    assert warned.summary == (
        "7 labels now may contain sesame: baguette, brioche, croissant, focaccia, "
        "pain au chocolat, rye loaf, sourdough loaf. 8 restaurants to tell"
    )
    bag = next(p for p in warned.payload["products"] if p["sku"] == "BAG")
    assert (bag["before"], bag["after"]) == (
        "contains gluten",
        "contains gluten; may contain sesame",
    )


def test_labelling_says_nothing_for_what_was_declared_already(bakery, hub):
    _substitution(bakery, hub)
    [changed] = _published(hub, "ingredients.changed")
    labelling = _labelling(bakery, hub)
    _deliver(labelling, "component.labelling", changed)

    _deliver(labelling, "component.labelling", changed)  # the same invoice again

    assert len(_published(hub, "allergens.changed")) == 1
    assert len([a for a in bakery["allergens"].all() if a.source != "sheet"]) == 1


def test_a_sheet_reimported_keeps_what_an_invoice_declared(bakery, hub, drive_path):
    _substitution(bakery, hub)
    _deliver(
        _labelling(bakery, hub), "component.labelling", _published(hub, "ingredients.changed")[0]
    )

    import_sheets(
        Drive(Config({"component": {"drive": {"path": str(drive_path)}}})),
        *_repos(bakery, "products", "restaurants", "standing_orders", "contracts"),
        *_repos(bakery, "ingredients", "recipes", "allergens", "messages"),
        hub.bound_to("function.import-sheets", Publisher.of(import_sheets)),
        announce=False,
    )

    assert _labels(bakery)["BAG"]["label"] == "contains gluten; may contain sesame"
    assert len([a for a in bakery["allergens"].all() if a.source == "sheet"]) == 8


def test_the_officer_drafts_a_notice_per_restaurant_and_confirming_emails_them(bakery, hub):
    _substitution(bakery, hub)
    _deliver(
        _labelling(bakery, hub), "component.labelling", _published(hub, "ingredients.changed")[0]
    )
    [warned] = _published(hub, "allergens.changed")

    _deliver(AllergenNotices(_officer(bakery, hub)), "component.allergen-notices", warned)

    [created] = _published(hub, "drafts.created")
    draft = bakery["drafts"].get(created.record)
    assert (draft.kind, draft.status, draft.author) == ("allergen-notice", "pending", "rules")
    assert draft.title == "Allergen notice: strong white flour now may contain sesame"
    notices = json.loads(draft.changes)["notices"]
    assert sorted(n["restaurant"] for n in notices) == sorted(warned.payload["restaurants"])
    le_petit = next(n for n in notices if n["restaurant"] == "Le Petit")
    assert le_petit["email"] == "kitchen@lepetit.example"
    assert "may contain sesame" in le_petit["text"] and le_petit["subject"].startswith(
        "Allergen notice: "
    )
    assert "| Baguette | contains gluten; may contain sesame |" in draft.body
    assert _officer(bakery, hub).invoke("FLOUR")["draft"] == draft.id  # not drafted twice

    mail = FakeSender()
    _confirm(bakery, hub, draft.id, mail=mail)

    assert sorted(to for to, _, _ in mail.sent) == sorted(n["email"] for n in notices)
    assert hub.seen[-1].summary == f"{draft.title}: {len(notices)} notices emailed"


def test_the_officer_has_nothing_to_tell_for_the_sheets_own_allergens(bakery, hub):
    assert _officer(bakery, hub).invoke("Butter") == {
        "draft": None, "allergens": [], "restaurants": [],
    }  # fmt: skip


def test_the_reactions_subscribe_as_the_chain_needs():
    assert (Subscriber.of(Labelling).topics, Subscriber.of(Labelling).deliver) == (
        ("ingredients.changed",), "background",
    )  # fmt: skip
    assert Publisher.of(Labelling) == ("allergens.changed",)
    assert (Subscriber.of(AllergenNotices).topics, Subscriber.of(AllergenNotices).deliver) == (
        ("allergens.changed",), "background",
    )  # fmt: skip
