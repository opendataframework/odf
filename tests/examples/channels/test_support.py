import typing

import pytest
from app.functions import send_reply
from app.repositories import Messages, Tickets
from opendataframework import Events, FunctionProtocol, Notifications, Publisher, Record

# Builds the components directly, as the other examples' tests do (see
# tests/examples/table_view/test_books.py). A bare Notifications hub stands in
# for the Context's, `Events().notify()` for the call the Context would make.

KEYS = {Tickets: "repository.tickets"}


def _send(tickets, messages, **kwargs):
    hub = Notifications(key_of=KEYS.__getitem__)
    seen = []
    hub.subscribe(seen.append)
    notifications = hub.bound_to("function.send-reply", Publisher.of(send_reply))
    with Events().notify("function.send-reply", FunctionProtocol, "__call__"):
        sent = send_reply(1, tickets, messages, notifications, **kwargs)
    return sent, seen


def test_messages_and_tickets_share_the_support_channel_one_thread_per_customer():
    messages, tickets = Messages().conversation(), Tickets().conversation()

    assert messages.channel == tickets.channel == "support"
    assert messages.thread == tickets.thread == "customer"
    assert messages.direction == "direction"
    assert tickets.direction is None  # tickets are cards


def test_send_reply_takes_a_ticket_and_starts_from_its_reply():
    hints = typing.get_type_hints(send_reply, include_extras=True)
    (record,) = [m for m in hints["ticket_id"].__metadata__ if isinstance(m, Record)]

    assert (record.repository, record.field) == (Tickets, "id")
    assert "reply" in {f for f in Tickets().all()[0].__dataclass_fields__}


def test_send_reply_sends_the_tickets_reply_and_saves_it_going_out():
    tickets, messages = Tickets(), Messages()

    sent, seen = _send(tickets, messages)

    assert sent == tickets.get(1).reply
    last = messages.all()[-1]
    assert (last.customer, last.direction, last.text) == ("Ada", "out", sent)
    assert tickets.get(1).status == "answered"
    (answered,) = seen
    assert (answered.topic, answered.subject, answered.record) == (
        "tickets.answered",
        "repository.tickets",
        1,
    )


def test_send_reply_sends_an_edited_reply_instead():
    tickets, messages = Tickets(), Messages()

    sent, _ = _send(tickets, messages, reply="  On us, Ada!  ")

    assert sent == tickets.get(1).reply == "On us, Ada!"
    assert messages.all()[-1].text == "On us, Ada!"


def test_a_ticket_is_answered_once():
    tickets, messages = Tickets(), Messages()
    _send(tickets, messages)

    with pytest.raises(ValueError, match="answered already"):
        _send(tickets, messages)
