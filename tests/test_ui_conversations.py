from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi.testclient import TestClient
from opendataframework.agent import Agent
from opendataframework.context import Context
from opendataframework.entity import Entity
from opendataframework.function import Function
from opendataframework.namespace import Namespace
from opendataframework.repository import Record, Repository
from opendataframework.view import ContentMetadata, Conversation, DocumentView

from odf.ui import conversations
from odf.ui.server import UiServer


@Entity(name="conv-message")
@dataclass
class Message:
    id: int
    sent_at: float
    customer: str | None
    direction: str
    sender: str
    text: str


@Entity(name="conv-ticket")
@dataclass
class Ticket:
    id: int
    opened: str
    customer: str | None
    body: str
    reply: str
    status: str = "open"


def make_ns():
    class NS(Namespace): ...

    return NS


def support_ns(messages=None, tickets=None):
    """A channel of messages from customers, with tickets answering them as cards."""
    NS = make_ns()
    messages = list(messages or [])
    tickets = list(tickets or [])

    @NS
    @Repository(Message)
    class Messages:
        def all(self):
            return messages

        def conversation(self):
            return Conversation(
                channel="support",
                thread="customer",
                time="sent_at",
                text="text",
                direction="direction",
                sender="sender",
            )

    @NS
    @Repository(Ticket)
    class Tickets:
        def all(self):
            return tickets

        def get(self, ticket_id):
            return next(t for t in tickets if t.id == ticket_id)

        def conversation(self):
            return Conversation(channel="support", thread="customer", time="opened", text="body")

        def data_view(self):
            return DocumentView(field="body")

        def content_metadata(self, ticket):
            return ContentMetadata(filename=f"{ticket.id}.md", content_type="text/markdown")

    @NS
    @Function
    def close_ticket(
        ticket_id: Annotated[int, Record(Tickets)], tickets: Tickets, reply: str | None = None
    ) -> str:
        """Close a ticket, sending its reply."""
        ticket = tickets.get(ticket_id)
        ticket.status = "closed"
        if reply is not None:
            ticket.reply = reply
        return ticket.reply

    @NS
    @Function
    def unrelated(name: str) -> str:
        return name

    return NS, Messages, Tickets, close_ticket


def at(day: int, hour: int) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=UTC)


MESSAGES = [
    Message(1, at(2, 9).timestamp(), "ada", "in", "ada@example.com", "My order is late"),
    Message(2, at(2, 11).timestamp(), "ada", "out", "ada@example.com", "Sorry, it's on its way"),
    Message(3, at(3, 8).timestamp(), "bob", "in", "bob@example.com", "Wrong size"),
    Message(4, at(3, 9).timestamp(), None, "in", "spam@example.com", "Buy now"),
]
TICKETS = [Ticket(10, at(2, 10).isoformat(), "ada", "**Late order**", "On its way")]


def test_channels_group_repositories_by_channel():
    NS, *_ = support_ns()
    with Context(namespaces={NS}) as ctx:
        found = conversations.channels(ctx)

    (channel,) = found
    assert channel["name"] == "support"
    kinds = {r["id"].split(".")[1]: r["kind"] for r in channel["repositories"]}
    assert kinds == {"messages": "messages", "tickets": "cards"}


def test_threads_list_each_thread_latest_first_leaving_out_records_with_no_thread():
    NS, *_ = support_ns(MESSAGES, TICKETS)
    with Context(namespaces={NS}) as ctx:
        found = conversations.threads(ctx, "support")

    assert [t["thread"] for t in found] == ["bob", "ada"]
    ada = found[1]
    assert ada["count"] == 3
    assert ada["last"] == {"text": "Sorry, it's on its way", "kind": "message", "direction": "out"}


def test_thread_merges_messages_and_cards_by_time_whatever_their_time_type():
    NS, *_ = support_ns(MESSAGES, TICKETS)
    with Context(namespaces={NS}) as ctx:
        items = conversations.thread(ctx, "support", "ada")

    assert [(i["kind"], i["key"]) for i in items] == [("message", 1), ("card", 10), ("message", 2)]
    first, card, _ = items
    assert first["direction"] == "in"
    assert first["sender"] == "ada@example.com"
    assert card["markdown"] is True
    assert card["record"]["reply"] == "On its way"


def test_thread_keeps_only_the_latest_items_up_to_the_limit():
    NS, *_ = support_ns(MESSAGES, TICKETS)
    with Context(namespaces={NS}) as ctx:
        items = conversations.thread(ctx, "support", "ada", limit=1)

    assert [i["key"] for i in items] == [2]


def test_a_card_carries_the_functions_taking_its_record_with_their_prefill():
    NS, *_ = support_ns(MESSAGES, TICKETS)
    with Context(namespaces={NS}) as ctx:
        card = conversations.thread(ctx, "support", "ada")[1]
        key = ctx.key(next(f for f in ctx.functions if f.__name__ == "close_ticket"))

    (action,) = card["actions"]
    assert action["id"] == key
    assert action["href"].startswith("/api/functions/")
    assert action["verb"] == "call"
    assert action["label"] == "Close ticket"
    assert action["description"] == "Close a ticket, sending its reply."
    assert action["param"] == "ticket_id"
    assert action["value"] == 10
    assert action["prefill"] == {"reply": "On its way"}


def test_an_agent_taking_a_record_is_an_action_too():
    NS, _, Tickets, _ = support_ns(MESSAGES, TICKETS)

    @NS
    @Agent
    class Triage:
        def invoke(self, ticket_id: Annotated[int, Record(Tickets)]) -> str:
            return "triaged"

    with Context(namespaces={NS}) as ctx:
        found = conversations.actions(ctx, Tickets)

    assert [(a["label"], a["verb"]) for a in found] == [
        ("Close ticket", "call"),
        ("Triage", "invoke"),
    ]


def test_unknown_channel_reads_as_none():
    NS, *_ = support_ns()
    with Context(namespaces={NS}) as ctx:
        assert conversations.threads(ctx, "nope") is None
        assert conversations.thread(ctx, "nope", "ada") is None


def test_a_conversation_naming_a_missing_field_fails_validation():
    NS = make_ns()

    @NS
    @Repository(Message)
    class Messages:
        def all(self):
            return []

        def conversation(self):
            return Conversation(channel="support", thread="nope", time="sent_at", text="text")

    with Context(namespaces={NS}) as ctx, pytest.raises(ValueError, match="thread='nope'"):
        conversations.validate(ctx)


def test_a_conversation_on_a_repository_that_cant_be_read_fails_validation():
    NS = make_ns()

    @NS
    @Repository(Message)
    class Outbox:
        def conversation(self):
            return Conversation(channel="support", thread="customer", time="sent_at", text="text")

    with Context(namespaces={NS}) as ctx, pytest.raises(ValueError, match="isn't readable"):
        conversations.validate(ctx)


def test_a_record_naming_a_missing_field_fails_validation():
    NS, _, Tickets, _ = support_ns()

    @NS
    @Function
    def reopen(ref: Annotated[str, Record(Tickets, field="ref")]) -> None: ...

    with Context(namespaces={NS}) as ctx, pytest.raises(ValueError, match="field='ref'"):
        conversations.validate(ctx)


def test_a_record_naming_a_repository_that_isnt_resolved_fails_validation():
    _, _, Tickets, _ = support_ns()
    NS = make_ns()

    @NS
    @Function
    def reopen(ticket_id: Annotated[int, Record(Tickets)]) -> None: ...

    with Context(namespaces={NS}) as ctx, pytest.raises(ValueError, match="isn't resolved"):
        conversations.validate(ctx)


def test_the_ui_refuses_to_start_on_a_bad_declaration():
    NS = make_ns()

    @NS
    @Repository(Message)
    class Messages:
        def all(self):
            return []

        def conversation(self):
            return Conversation(channel="support", thread="customer", time="nope", text="text")

    with Context(namespaces={NS}) as ctx, pytest.raises(ValueError, match="time='nope'"):
        UiServer(ctx, "proj")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1793700000, 1793700000.0),
        (1793700000.5, 1793700000.5),
        (at(2, 9), at(2, 9).timestamp()),
        (at(2, 9).isoformat(), at(2, 9).timestamp()),
    ],
)
def test_sort_time_reads_numbers_datetimes_and_iso_strings(value, expected):
    assert conversations.sort_time(value) == expected


@pytest.mark.parametrize("value", [None, True, b"x"])
def test_sort_time_refuses_anything_else(value):
    with pytest.raises(ValueError):
        conversations.sort_time(value)


def test_channel_routes_list_channels_threads_and_items():
    NS, *_ = support_ns(MESSAGES, TICKETS)
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        channels = client.get("/api/channels")
        threads = client.get("/api/channels/support/threads")
        items = client.get("/api/channels/support/threads/ada", params={"limit": 2})

    assert channels.status_code == 200
    assert [c["name"] for c in channels.json()] == ["support"]
    assert [t["thread"] for t in threads.json()] == ["bob", "ada"]
    assert [i["key"] for i in items.json()] == [10, 2]


def test_channel_routes_answer_404_for_an_unknown_channel():
    NS, *_ = support_ns()
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        threads = client.get("/api/channels/nope/threads")
        items = client.get("/api/channels/nope/threads/ada")

    assert threads.status_code == 404
    assert items.status_code == 404


def test_a_thread_name_with_spaces_is_read_from_its_encoded_path():
    message = Message(1, 1.0, "Le Petit", "in", "+44", "2 more baguettes")
    NS, *_ = support_ns([message])
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        items = client.get("/api/channels/support/threads/Le%20Petit")

    assert [i["text"] for i in items.json()] == ["2 more baguettes"]


def test_a_card_action_runs_through_the_function_route_with_the_record_argument():
    tickets = [Ticket(10, at(2, 10).isoformat(), "ada", "**Late order**", "On its way")]
    NS, *_ = support_ns([], tickets)
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        (card,) = client.get("/api/channels/support/threads/ada").json()
        (action,) = card["actions"]
        schema = client.get(f"{action['href']}/parameters").json()
        r = client.post(
            f"{action['href']}/{action['verb']}",
            json={action["param"]: action["value"], "reply": "Edited"},
        )

    assert schema["properties"]["ticket_id"]["type"] == "integer"
    assert r.status_code == 200
    assert r.json()["result"] == "Edited"
    assert tickets[0].status == "closed"


def test_the_chat_drawer_lists_channels_and_shows_threads():
    from odf.ui import themes

    html = (themes.STATIC_DIR / "index.html").read_text()
    script = (themes.STATIC_DIR / "app.js").read_text()

    assert 'id="chat-nav"' in html
    assert 'id="chat-thread"' in html
    assert 'id="chat-back"' in html
    assert "fetch('/api/channels')" in script
    assert "onNotesLive(n);\n    onChannelNotification(n);" in script
    for theme in sorted((themes.STATIC_DIR / "themes").iterdir()):
        css = (theme / "theme.css").read_text()
        assert ".chat-card{" in css, theme.name
        assert "#chat-nav[hidden]" in css, theme.name


def test_a_card_runs_its_actions_through_the_shared_arguments_form():
    from odf.ui import themes

    script = (themes.STATIC_DIR / "app.js").read_text()

    assert "function buildArgumentsForm(schema, {" in script
    # The inspector's form and a card's form are the same form.
    assert script.count("buildArgumentsForm(schema, {") == 3
    assert "const hidden = { [action.param]: action.value };" in script
    assert "fetch(`${action.href}/${action.verb}`" in script
