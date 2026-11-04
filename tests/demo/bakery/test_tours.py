import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tools import tours, world

APP_DIR = Path(world.__file__).resolve().parents[1] / "app"

# The world console's tours: how a step matches the bakery's notifications,
# and the guide playing one, fed notifications by hand instead of a bakery.


def _note(topic: str, summary: str | None = None, **payload) -> dict:
    return {"type": "notification", "topic": topic, "summary": summary, "payload": payload}


@pytest.fixture
def guide(monkeypatch):
    """A guide that doesn't follow a bakery: the test hands it notifications."""
    guide = world.Guide(spawn=lambda gen: None)
    monkeypatch.setattr(world, "guide", guide)
    yield guide
    guide.stop()


def test_pick_follows_lists_and_keeps_each_value_once():
    payload = {"contracts": [{"restaurant": "Kiln"}, {"restaurant": "Kiln"}, {"restaurant": "Fig"}]}

    assert tours.pick(payload, "contracts.*.restaurant") == ["Kiln", "Fig"]
    assert tours.pick({"draft": 3}, "draft") == [3]
    assert tours.pick({"draft": 3}, "missing") == []


def test_a_step_matches_its_topic_and_fields_including_captured_values():
    step = tours.Step(say="", topic="drafts.confirmed", where={"draft": "{drafts}"})

    assert tours.matches(step, _note("drafts.confirmed", draft=4), {"drafts": [3, 4]})
    assert not tours.matches(step, _note("drafts.confirmed", draft=5), {"drafts": [3, 4]})
    assert not tours.matches(step, _note("drafts.created", draft=4), {"drafts": [3, 4]})
    assert not tours.matches(tours.Step(say=""), _note("drafts.confirmed", draft=4), {})


def test_a_step_counts_what_it_captured_and_fills_its_caption():
    created = tours.Step(say="To {restaurants}", topic="margins.below-cost",
                         capture={"restaurants": "contracts.*.restaurant"})  # fmt: skip
    drafts = tours.Step(say="", topic="drafts.created", count="restaurants")
    captured: dict[str, list] = {}

    assert tours.say(created, captured) == "To …"
    tours.capture(created, _note("x", contracts=[{"restaurant": "Kiln"}, {"restaurant": "Fig"}]),
                  captured)  # fmt: skip

    assert captured == {"restaurants": ["Kiln", "Fig"]}
    assert tours.needed(drafts, captured) == 2
    assert tours.say(created, captured) == "To Kiln, Fig"


def test_every_tour_starts_and_waits_for_topics_the_bakery_publishes():
    published = set()
    for path in APP_DIR.glob("*.py"):
        published |= set(re.findall(r'publish\(\s*"([^"]+)"', path.read_text()))

    assert set(world.TOUR_STARTS) == set(tours.TOURS)
    for tour in tours.TOURS.values():
        assert {s.topic for s in tour.steps if s.topic} <= published
        assert tour.steps[-1].topic is None  # the last waits for the presenter


def test_guide_plays_the_order_change_and_puts_the_clock_back(guide):
    world.clock.update(paused=False)
    guide.start("order-change")
    gen, who = guide.generation, tours.ORDER_RESTAURANT.name

    assert world.clock.state()[3]  # paused while it plays
    guide.notify(gen, _note("messages.received", "Kiln: hi", restaurant="Kiln"))
    assert guide.index == 0  # another restaurant's message
    guide.notify(gen, _note("messages.received", f"{who}: 2 extra", restaurant=who))
    guide.notify(gen, _note("drafts.created", "Order change", draft=9, kind="order-change"))
    guide.notify(gen - 1, _note("drafts.confirmed", draft=9))  # an earlier tour's follower
    assert guide.index == 2
    guide.notify(gen, _note("drafts.confirmed", "Confirmed", draft=9))

    state = guide.state()
    assert [s["status"] for s in state["steps"]] == ["done", "done", "done", "current"]
    assert state["steps"][1]["seen"] == ["Order change"]
    assert who in state["steps"][3]["say"]
    assert not state["done"]

    guide.next()

    assert guide.state()["done"]
    assert not world.clock.state()[3]


def test_guide_waits_for_a_draft_per_restaurant_below_cost(guide):
    guide.start("butter-spike")
    gen = guide.generation
    guide.notify(gen, _note("invoices.received", supplier="Vale Dairy"))
    guide.notify(gen, _note("prices.changed", supplier="Vale Dairy"))
    guide.notify(gen, _note("margins.below-cost",
                            contracts=[{"restaurant": "Kiln"}, {"restaurant": "Fig"}]))  # fmt: skip
    guide.notify(gen, _note("drafts.created", draft=1, kind="renegotiation"))

    assert guide.index == 3
    guide.notify(gen, _note("drafts.created", draft=2, kind="renegotiation"))
    assert guide.index == 4
    assert guide.captured["drafts"] == [1, 2]


def test_do_it_for_me_confirms_the_drafts_not_yet_confirmed(guide, monkeypatch):
    calls = []
    monkeypatch.setattr(
        world, "http_json", lambda method, url, body, **kw: calls.append((url, body))
    )
    guide.start("sesame-substitution")
    guide.index = 4  # waiting for the confirmation
    guide.captured.update(drafts=[7, 8], confirmed=[7])

    assert guide.act() == [8]
    assert calls == [(f"{world.BAKERY_URL}/api/functions/confirm-draft/call", {"draft_id": 8})]
    guide.index = 3
    assert guide.act() == []  # this step confirms nothing


def test_guide_acts_out_the_start_once_subscribed(guide, monkeypatch):
    started = []
    monkeypatch.setitem(world.TOUR_STARTS, "order-change", lambda: started.append(True))

    def stream(url):
        assert url == f"{world.BAKERY_URL}/api/notifications"
        assert not started  # not before the bakery listens
        yield None
        guide.stop()  # the presenter stops it: the follower returns
        yield _note("messages.received")

    monkeypatch.setattr(world, "notification_stream", stream)
    guide.start("order-change")
    guide.follow(guide.generation)

    assert started == [True]


def test_tour_routes(guide):
    client = TestClient(world.app)

    assert client.post("/tour/nothing").status_code == 404
    started = client.post("/tour/butter-spike").json()
    assert started["tour"] == "butter-spike"
    assert started["steps"][0]["status"] == "current"
    assert client.post("/tour/next").json()["steps"][1]["status"] == "current"
    assert client.post("/tour/act").json() == {"confirmed": []}
    assert client.post("/tour/stop").json() == {"tour": None}
    assert client.get("/tour").json() == {"tour": None}
