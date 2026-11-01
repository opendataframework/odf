"""Phase 4a: the agents, their drafts, and the plain arithmetic they're checked against.

Built from the components directly, as in ``test_integrations.py``, with a
fixed demo clock (Monday 2 November 2026, 21:00), a fake messenger and mail,
and either no model or a fake one.
"""

import json
from datetime import date, datetime, timedelta

import pytest
from app.agents import OrderDesk, Specials
from app.clients import Drive
from app.drafts import confirm_draft, reject_draft
from app.entities import BakeSheetLine, CafeSale, Leftover, OrderChange, StandingOrder
from app.ingest import import_sheets, ingest_message
from app.planning import (
    bake_sheet,
    count_leftovers,
    forecast,
    plan_deliveries,
    weather_factor,
    wholesale_order,
)
from app.repositories import (
    BakeSheets,
    CafeSales,
    Contracts,
    DeliveryRuns,
    Drafts,
    Forecasts,
    Leftovers,
    Messages,
    OrderChanges,
    Products,
    Restaurants,
    StandingOrders,
)
from app.rules import (
    Change,
    aliases,
    check_changes,
    next_weekday,
    plural,
    read_order_change,
    specials_for,
)
from app.services import Scheduler
from app.storages import SQLite
from fastapi.testclient import TestClient
from opendataframework import Config
from opendataframework.notifications import Notifications
from tools import data, world

MONDAY = date(2026, 11, 2)
TUESDAY = MONDAY + timedelta(days=1)

KEYS = {
    Messages: "repository.messages",
    Products: "repository.products",
    Drafts: "repository.drafts",
    BakeSheets: "repository.bake-sheets",
}


class FakeClock:
    def __init__(self, at=datetime(2026, 11, 2, 21, 0)):
        self.at = at

    def now(self):
        return self.at


class FakeWeather:
    def __init__(self, sky=None):
        self.sky = sky

    def daily(self, day):
        return self.sky


class FakeModel:
    """Answers every question with ``answer``, or isn't there at all."""

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


@pytest.fixture
def bakery(tmp_path, db, hub):
    """A bakery with the sheets imported, and its repositories by name."""
    data.write_sheets(tmp_path / "drive", 7, "2026-12-31")
    drive = Drive(Config({"component": {"drive": {"path": str(tmp_path / "drive")}}}))
    repos = {
        "products": Products(db),
        "restaurants": Restaurants(db),
        "standing_orders": StandingOrders(db),
        "contracts": Contracts(db),
        "messages": Messages(db),
        "order_changes": OrderChanges(db),
        "drafts": Drafts(db),
        "sales": CafeSales(db),
        "forecasts": Forecasts(db),
        "sheets": BakeSheets(db),
        "leftovers": Leftovers(db),
        "runs": DeliveryRuns(db),
    }
    import_sheets(
        drive,
        repos["products"],
        repos["restaurants"],
        repos["standing_orders"],
        repos["contracts"],
        repos["messages"],
        hub.bound_to("function.import-sheets"),
        announce=False,
    )
    return repos


def _message(bakery, hub, text, sender="+447700900201", channel="messenger", n=1):
    return ingest_message(
        channel,
        f"m{n}",
        sender,
        text,
        datetime(2026, 11, 2, 20, 15).timestamp(),
        bakery["messages"],
        bakery["restaurants"],
        hub.bound_to("function.ingest-message"),
        subject="Order change" if channel == "email" else "",
        announce=False,
    )


def _desk(bakery, hub, model=None):
    return OrderDesk(
        FakeClock(),
        bakery["messages"],
        bakery["products"],
        bakery["standing_orders"],
        bakery["order_changes"],
        bakery["drafts"],
        model or FakeModel(available=False),
        hub.bound_to("agent.order-desk"),
    )


def _usual(bakery, restaurant, day):
    standing = bakery["standing_orders"].for_weekday(f"{day:%A}")
    return wholesale_order(standing, bakery["order_changes"].for_day(day), day).get(restaurant, {})


def _confirm(bakery, hub, draft_id, messenger=None, mail=None, rebaked=None):
    rebaked = [] if rebaked is None else rebaked
    return confirm_draft(
        draft_id,
        bakery["drafts"],
        bakery["messages"],
        bakery["order_changes"],
        bakery["sheets"],
        messenger or FakeSender(),
        mail or FakeSender(),
        hub.bound_to("function.confirm-draft"),
        lambda date: rebaked.append(("bake", date)),
        lambda date: rebaked.append(("plan", date)),
    )


# --- rules ---


def test_plural_names_products_as_restaurants_write_them():
    assert [plural(p.name) for p in data.WHOLESALE] == [data.PLURALS[p.sku] for p in data.WHOLESALE]


def test_aliases_know_every_plural_the_world_writes(bakery):
    names = aliases(bakery["products"].all())

    assert {names[data.PLURALS[sku]] for sku in data.PLURALS} == set(data.PLURALS)
    assert names["sourdough"] == "SD-LOAF"
    assert "flat white" not in names  # the café's drinks aren't ordered wholesale


def test_next_weekday_is_always_after_the_day():
    assert next_weekday(MONDAY, "tuesday") == TUESDAY
    assert next_weekday(MONDAY, "Monday") == MONDAY + timedelta(days=7)


@pytest.mark.parametrize(
    ("text", "change"),
    [
        ("4 extra baguettes tomorrow please", Change("BAG", "2026-11-03", "add", 4)),
        ("Could we get 8 croissants on Friday?", Change("CRO", "2026-11-06", "set", 8)),
        ("No rye loaves on Saturday this week, thanks", Change("RYE", "2026-11-07", "set", 0)),
        (
            "Please drop the pains au chocolat to 5 from tomorrow",
            Change("PAC", "2026-11-03", "set-from", 5),
        ),
    ],
)
def test_rules_read_every_templated_order_change(bakery, text, change):
    assert read_order_change(text, bakery["products"].all(), MONDAY) == [change]


@pytest.mark.parametrize("text", [*data.FREEFORM_MESSAGES, "3 extra cakes tomorrow please"])
def test_rules_leave_what_they_cant_read(bakery, text):
    assert read_order_change(text, bakery["products"].all(), MONDAY) is None


def test_check_changes_takes_only_well_formed_changes(bakery):
    products = bakery["products"].all()
    good = {"sku": "BRI", "date": "2026-11-06", "mode": "add", "quantity": 10}

    assert check_changes([good], products, MONDAY) == [Change("BRI", "2026-11-06", "add", 10)]
    for bad in (
        {**good, "sku": "FLW"},  # café only
        {**good, "mode": "swap"},
        {**good, "date": "2027-06-01"},  # too far ahead
        {**good, "mode": "set", "quantity": -2},
        {"sku": "BRI"},
    ):
        assert check_changes([bad], products, MONDAY) is None
    assert check_changes([], products, MONDAY) is None


# --- planning ---


def test_wholesale_order_applies_lasting_changes_then_the_days_own():
    standing = [StandingOrder(1, "Kiln", "Tuesday", "BAG", 10)]
    changes = [
        OrderChange(1, "Kiln", "BAG", "2026-11-03", "add", 2, None, None),
        OrderChange(2, "Kiln", "BAG", "2026-11-01", "set-from", 6, None, None),
        OrderChange(3, "Kiln", "CRO", "2026-11-03", "set", 4, None, None),
        OrderChange(4, "Kiln", "RYE", "2026-11-01", "set-from", 9, None, None),  # not usual
    ]

    assert wholesale_order(standing, changes, TUESDAY) == {"Kiln": {"BAG": 8, "CRO": 4}}


def test_wholesale_order_leaves_out_a_restaurant_taking_nothing():
    standing = [StandingOrder(1, "Kiln", "Tuesday", "BAG", 10)]
    changes = [OrderChange(1, "Kiln", "BAG", "2026-11-03", "set", 0, None, None)]

    assert wholesale_order(standing, changes, TUESDAY) == {}


def test_weather_factor_rain_lowers_and_warmth_raises():
    assert weather_factor(8.0, 15.0) == 0.7
    assert weather_factor(2.0, 25.0) == 0.85
    assert weather_factor(0.0, 25.0) == 1.1
    assert weather_factor(0.0, 15.0) == 1.0


def _sell(bakery, day, sku, quantity, order="o"):
    at = datetime.combine(day, datetime.min.time()).replace(hour=9).timestamp()
    bakery["sales"].save_many(
        [CafeSale(None, at, f"{order}-{day}-{sku}", sku, sku, quantity, quantity * 1.0)]
    )


def test_forecast_averages_the_weekday_then_applies_the_weather(bakery):
    for weeks, sold in ((1, 10), (2, 20), (3, 30)):
        _sell(bakery, TUESDAY - timedelta(weeks=weeks), "CRO", sold)
    _sell(bakery, TUESDAY - timedelta(days=1), "CRO", 99)  # a Monday: not counted

    rows = forecast(
        FakeClock(),
        bakery["sales"],
        bakery["products"],
        FakeWeather({"rain_mm": 6.0, "temp_max": 12.0}),
        bakery["forecasts"],
    )

    croissants = next(r for r in rows if r["sku"] == "CRO")
    assert croissants == {"sku": "CRO", "product": "Croissant", "baseline": 20.0, "quantity": 14}
    saved = bakery["forecasts"].where("date", "2026-11-03")
    assert {f.weather for f in saved} == {0.7} and {f.rain_mm for f in saved} == {6.0}


def test_forecast_raises_a_bank_holiday(bakery):
    christmas = date(2026, 12, 28)
    _sell(bakery, christmas - timedelta(weeks=1), "FLW", 40)

    rows = forecast(
        FakeClock(),
        bakery["sales"],
        bakery["products"],
        FakeWeather(),
        bakery["forecasts"],
        date=christmas.isoformat(),
    )

    assert next(r for r in rows if r["sku"] == "FLW")["quantity"] == 50


def test_bake_sheet_adds_the_cafes_forecast_and_a_buffer_to_the_restaurants(bakery):
    _sell(bakery, TUESDAY - timedelta(weeks=1), "CRO", 20)
    forecast(FakeClock(), bakery["sales"], bakery["products"], FakeWeather(), bakery["forecasts"])
    wholesale = sum(
        s.quantity for s in bakery["standing_orders"].for_weekday("Tuesday") if s.sku == "CRO"
    )

    lines = bake_sheet(
        FakeClock(),
        bakery["products"],
        bakery["standing_orders"],
        bakery["order_changes"],
        bakery["forecasts"],
        bakery["sheets"],
    )

    croissants = next(line for line in lines if line["sku"] == "CRO")
    assert croissants == {
        "sku": "CRO",
        "product": "Croissant",
        "wholesale": wholesale,
        "cafe": 22,
        "total": wholesale + 22,
    }
    assert {line["sku"] for line in lines} <= {p.sku for p in data.WHOLESALE}
    assert bakery["sheets"].dates() == ["2026-11-03"]


def test_plan_deliveries_goes_earliest_kitchen_first_from_the_bakery(bakery):
    stops = plan_deliveries(
        FakeClock(),
        bakery["restaurants"],
        bakery["products"],
        bakery["standing_orders"],
        bakery["order_changes"],
        bakery["runs"],
    )

    opens = [s["arrive_by"] for s in stops]
    assert opens == sorted(opens)
    assert stops[0]["restaurant"] == "North Street Diner"  # opens at 07:00
    assert all(s["eta"] >= "05:30" for s in stops)
    run = bakery["runs"].all()
    assert run[0].restaurant == "The Bakery" and run[0].stop == 0
    assert [s.restaurant for s in run[1:]] == [s["restaurant"] for s in stops]


def test_delivery_runs_show_only_the_latest_run(bakery):
    args = [
        FakeClock(),
        bakery["restaurants"],
        bakery["products"],
        bakery["standing_orders"],
        bakery["order_changes"],
        bakery["runs"],
    ]
    plan_deliveries(*args, date="2026-11-03")
    plan_deliveries(*args, date="2026-11-04")

    assert {s.date for s in bakery["runs"].all()} == {"2026-11-04"}


def test_count_leftovers_compares_the_cafes_bake_with_its_sales(bakery):
    bakery["sheets"].replace_where(
        "date",
        "2026-11-02",
        [BakeSheetLine(None, "2026-11-02", "CRO", "Croissant", 30, 20, 2, 52)],
    )
    _sell(bakery, MONDAY, "CRO", 15)

    rows = count_leftovers(FakeClock(), bakery["sales"], bakery["sheets"], bakery["leftovers"])

    assert rows == [{"sku": "CRO", "product": "Croissant", "baked": 22, "sold": 15, "unsold": 7}]


# --- order-desk ---


def test_order_desk_drafts_a_templated_change_with_rules(bakery, hub):
    message_id = _message(bakery, hub, "4 extra baguettes tomorrow please")
    before = _usual(bakery, "Le Petit", TUESDAY).get("BAG", 0)

    drafted = _desk(bakery, hub).invoke(message_id)

    assert drafted["status"] == "pending" and drafted["author"] == "rules"
    assert drafted["changes"] == [
        {"sku": "BAG", "date": "2026-11-03", "mode": "add", "quantity": 4}
    ]
    assert (
        drafted["reply"]
        == "Thanks, that's noted: 4 extra baguettes on Tue 3 Nov. See you in the morning!"
    )
    draft = bakery["drafts"].get(drafted["draft"])
    assert f"| Tue 3 Nov | Baguette | {before} | **{before + 4}** |" in draft.body
    assert bakery["messages"].where("id", message_id)[0].status == "drafted"
    [created] = [n for n in hub.seen if n.topic == "drafts.created"]
    assert created.summary == "Order change for Le Petit awaits confirmation"
    assert (created.subject, created.record) == ("repository.drafts", draft.id)
    assert _usual(bakery, "Le Petit", TUESDAY).get("BAG", 0) == before  # nothing applied yet


def test_order_desk_gives_back_the_draft_already_waiting(bakery, hub):
    message_id = _message(bakery, hub, "4 extra baguettes tomorrow please")
    desk = _desk(bakery, hub)

    first, second = desk.invoke(message_id), desk.invoke(message_id)

    assert first["draft"] == second["draft"]
    assert len(bakery["drafts"].all()) == 1


def test_order_desk_without_a_model_leaves_freeform_for_review(bakery, hub):
    message_id = _message(bakery, hub, data.FREEFORM_MESSAGES[0])

    drafted = _desk(bakery, hub).invoke(message_id)

    assert (drafted["status"], drafted["author"], drafted["changes"]) == (
        "needs-review",
        "nobody",
        [],
    )
    assert "no model" in bakery["drafts"].get(drafted["draft"]).note
    assert [n.level for n in hub.seen if n.topic == "drafts.created"] == ["warning"]


def test_order_desk_asks_the_model_only_what_rules_cant_read(bakery, hub):
    model = FakeModel(
        {
            "changes": [
                {"sku": "CRO", "date": "2026-11-06", "mode": "set", "quantity": 0},
                {"sku": "BRI", "date": "2026-11-06", "mode": "add", "quantity": 12},
            ],
            "reply": "Of course! Brioche instead of croissants on Friday.",
            "unclear": False,
            "note": "",
        }
    )
    desk = _desk(bakery, hub, model)

    templated = desk.invoke(_message(bakery, hub, "4 extra baguettes tomorrow please"))
    freeform = desk.invoke(_message(bakery, hub, data.FREEFORM_MESSAGES[0], n=2))

    assert templated["author"] == "rules" and len(model.asked) == 1
    assert (freeform["status"], freeform["author"]) == ("pending", "model:fake")
    assert freeform["reply"] == "Of course! Brioche instead of croissants on Friday."
    assert "Friday 2026-11-06" in model.asked[0]  # the week's orders, for "half the usual"


def test_order_desk_marks_an_unsure_or_bad_model_answer_for_review(bakery, hub):
    unsure = FakeModel({"changes": [], "reply": "", "unclear": True, "note": "How many people?"})
    bad = FakeModel(
        {"changes": [{"sku": "CAKE", "date": "x", "mode": "add", "quantity": 1}], "reply": "",
         "unclear": False, "note": ""}
    )  # fmt: skip

    first = _desk(bakery, hub, unsure).invoke(_message(bakery, hub, data.FREEFORM_MESSAGES[0]))
    second = _desk(bakery, hub, bad).invoke(_message(bakery, hub, data.FREEFORM_MESSAGES[1], n=2))

    assert first["status"] == second["status"] == "needs-review"
    assert "How many people?" in bakery["drafts"].get(first["draft"]).note
    assert "didn't check out" in bakery["drafts"].get(second["draft"]).note


def test_order_desk_leaves_a_message_from_a_stranger_for_review(bakery, hub):
    message_id = _message(bakery, hub, "4 extra baguettes tomorrow please", sender="+447700900999")

    drafted = _desk(bakery, hub).invoke(message_id)

    assert drafted["status"] == "needs-review"


# --- confirming and rejecting ---


def test_confirm_sends_the_reply_then_applies_the_change(bakery, hub):
    message_id = _message(bakery, hub, "4 extra baguettes tomorrow please")
    draft_id = _desk(bakery, hub).invoke(message_id)["draft"]
    before = _usual(bakery, "Le Petit", TUESDAY).get("BAG", 0)
    messenger, rebaked = FakeSender(), []

    confirmed = _confirm(bakery, hub, draft_id, messenger=messenger, rebaked=rebaked)

    assert confirmed["replied"] == "messenger"
    assert messenger.sent == [("+447700900201", bakery["drafts"].get(draft_id).reply)]
    assert _usual(bakery, "Le Petit", TUESDAY)["BAG"] == before + 4
    assert bakery["messages"].where("id", message_id)[0].status == "done"
    assert bakery["drafts"].get(draft_id).status == "confirmed"
    assert rebaked == []  # no bake sheet for Tuesday yet
    done = hub.seen[-1]
    assert (done.topic, done.level) == ("drafts.confirmed", "success")
    assert done.summary == "Order change for Le Petit: applied, reply sent by messenger"


def test_confirm_replies_to_an_email_by_email_and_rebakes_a_planned_day(bakery, hub):
    message_id = _message(
        bakery, hub, "Hi,\n\n4 extra baguettes tomorrow please\n\nThanks,\nLe Petit",
        sender="kitchen@lepetit.example", channel="email",
    )  # fmt: skip
    draft_id = _desk(bakery, hub).invoke(message_id)["draft"]
    for day in ("2026-11-03", "2026-11-04"):
        line = BakeSheetLine(None, day, "BAG", "Baguette", 1, 0, 0, 1)
        bakery["sheets"].replace_where("date", day, [line])
    mail, rebaked = FakeSender(), []

    _confirm(bakery, hub, draft_id, mail=mail, rebaked=rebaked)

    [(to, subject, _)] = mail.sent
    assert (to, subject) == ("kitchen@lepetit.example", "Re: Order change")
    assert rebaked == [("bake", "2026-11-03"), ("plan", "2026-11-03")]


def test_a_reply_that_cant_be_sent_leaves_the_draft_pending(bakery, hub):
    class Down:
        def send(self, *args):
            raise OSError("messenger down")

    draft_id = _desk(bakery, hub).invoke(
        _message(bakery, hub, "4 extra baguettes tomorrow please")
    )["draft"]

    with pytest.raises(OSError):
        _confirm(bakery, hub, draft_id, messenger=Down())

    assert bakery["drafts"].get(draft_id).status == "pending"
    assert bakery["order_changes"].all() == []


def test_a_draft_needing_review_cant_be_confirmed(bakery, hub):
    draft_id = _desk(bakery, hub).invoke(_message(bakery, hub, data.FREEFORM_MESSAGES[0]))["draft"]

    with pytest.raises(ValueError, match="needs-review"):
        _confirm(bakery, hub, draft_id)


def test_reject_keeps_the_reason_and_puts_the_message_back(bakery, hub):
    message_id = _message(bakery, hub, data.FREEFORM_MESSAGES[0])
    draft_id = _desk(bakery, hub).invoke(message_id)["draft"]

    reject_draft(
        draft_id,
        bakery["drafts"],
        bakery["messages"],
        hub.bound_to("function.reject-draft"),
        reason="Called them",
    )

    draft = bakery["drafts"].get(draft_id)
    assert (draft.status, draft.note) == ("rejected", "Called them")
    assert bakery["messages"].where("id", message_id)[0].status == "new"
    with pytest.raises(ValueError, match="rejected already"):
        reject_draft(draft_id, bakery["drafts"], bakery["messages"], hub)


# --- specials ---


def _specials(bakery, hub, model=None):
    return Specials(
        FakeClock(),
        bakery["leftovers"],
        bakery["drafts"],
        model or FakeModel(available=False),
        hub.bound_to("agent.specials"),
    )


def _leftovers(bakery, **unsold):
    bakery["leftovers"].replace_where(
        "date",
        "2026-11-02",
        [Leftover(None, "2026-11-02", sku, sku, 20, 20 - n, n) for sku, n in unsold.items()],
    )


def test_specials_for_picks_what_has_enough_left_most_first():
    found = specials_for(
        [
            Leftover(None, "d", "CRO", "Croissant", 20, 13, 7),
            Leftover(None, "d", "BAG", "Baguette", 10, 8, 2),  # too few
            Leftover(None, "d", "BRI", "Brioche", 10, 1, 9),
        ]
    )

    assert [s["dish"] for s in found] == ["Brioche French toast", "Almond croissant"]
    assert found[1]["uses"] == "7 × Croissant"


def test_specials_drafts_tomorrows_board_once(bakery, hub):
    _leftovers(bakery, CRO=7, BAG=1)
    agent = _specials(bakery, hub)

    first, second = agent.invoke(), agent.invoke()

    assert first["draft"] == second["draft"]
    draft = bakery["drafts"].get(first["draft"])
    assert (draft.kind, draft.date, draft.status, draft.author) == (
        "specials",
        "2026-11-03",
        "pending",
        "rules",
    )
    assert "| **Almond croissant** |" in draft.body
    assert [n.summary for n in hub.seen if n.topic == "drafts.created"] == [
        "Specials for Tue 3 Nov await confirmation"
    ]


def test_specials_lets_the_model_write_the_lines_but_not_pick_the_dishes(bakery, hub):
    _leftovers(bakery, CRO=7)
    model = FakeModel({"lines": [{"sku": "CRO", "line": "Golden, almondy, twice-baked."}]})

    drafted = _specials(bakery, hub, model).invoke()

    [special] = drafted["specials"]
    assert (special["dish"], special["description"]) == (
        "Almond croissant",
        "Golden, almondy, twice-baked.",
    )
    assert bakery["drafts"].get(drafted["draft"]).author == "model:fake"


def test_specials_drafts_nothing_when_little_is_left(bakery, hub):
    _leftovers(bakery, CRO=2)

    assert _specials(bakery, hub).invoke() == {"draft": None, "specials": []}


def test_confirming_specials_puts_them_on_the_board(bakery, hub):
    _leftovers(bakery, CRO=7)
    draft_id = _specials(bakery, hub).invoke()["draft"]

    confirmed = _confirm(bakery, hub, draft_id)

    assert confirmed["replied"] is None
    assert hub.seen[-1].summary == "Specials for Tue 3 Nov: on the board"


# --- scheduling ---


def test_scheduler_runs_each_days_runs_once_from_their_time():
    scheduler = Scheduler(*([None] * 7), logger=None)

    assert scheduler.due(datetime(2026, 11, 2, 14, 59)) == []
    assert scheduler.due(datetime(2026, 11, 2, 21, 5)) == ["close-cafe", "night-run"]
    scheduler._done.update({"close-cafe": "2026-11-02", "night-run": "2026-11-02"})
    assert scheduler.due(datetime(2026, 11, 2, 23, 45)) == ["pos-reconcile"]
    assert scheduler.due(datetime(2026, 11, 3, 15, 0)) == ["close-cafe"]


# --- the world's weather ---


def test_world_weather_is_the_same_each_time_and_shaped_like_open_meteo():
    client = TestClient(world.app)
    query = "latitude=51.45&longitude=-2.59&start_date=2026-11-03&end_date=2026-11-05"

    first = client.get(f"/v1/forecast?{query}").json()
    second = client.get(f"/v1/forecast?{query}").json()

    assert first == second
    assert first["daily"]["time"] == ["2026-11-03", "2026-11-04", "2026-11-05"]
    assert (
        len(first["daily"]["precipitation_sum"]) == len(first["daily"]["temperature_2m_max"]) == 3
    )


def test_a_rainy_week_pours_and_keeps_cafe_customers_away(monkeypatch):
    state = {"rain_from": "2026-11-02", "rain_until": "2026-11-08"}
    monkeypatch.setattr(world, "_get", state.get)

    assert world.weather(date(2026, 11, 4))["rain_mm"] >= 8
    assert world.footfall(date(2026, 11, 4)) == 0.6
    state.clear()
    assert all(world.footfall(date(2026, 11, d)) in (0.6, 0.85, 1.0) for d in range(1, 30))


def test_drafts_render_as_markdown(bakery, hub):
    draft_id = _desk(bakery, hub).invoke(
        _message(bakery, hub, "4 extra baguettes tomorrow please")
    )["draft"]
    meta = bakery["drafts"].content_metadata(bakery["drafts"].get(draft_id))

    assert (meta.filename, meta.content_type) == (f"draft-{draft_id}.md", "text/markdown")
    assert json.loads(bakery["drafts"].get(draft_id).changes)[0]["sku"] == "BAG"
