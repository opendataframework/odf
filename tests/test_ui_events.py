import asyncio
import json
import threading

import pytest
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.function import Function
from opendataframework.namespace import Namespace
from opendataframework.pipeline import Pipeline
from opendataframework.task import Task

from odf.ui import events


def make_ns():
    class NS(Namespace): ...

    return NS


def _pipeline(NS):
    @NS
    @Task
    class Step:
        def execute(self) -> None: ...

    @NS
    @Pipeline
    class Flow:
        def __init__(self, step: Step) -> None:
            self.step = step

        def execute(self) -> None:
            self.step.execute()

    return Step, Flow


def _drain(queue: asyncio.Queue) -> list:
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def _collect(hub: events.EventHub, run) -> list:
    """Run ``run`` in a worker thread while one client is connected, then drain it."""

    async def main():
        async with hub.client() as queue:
            thread = threading.Thread(target=run)
            thread.start()
            await asyncio.to_thread(thread.join)
            await asyncio.sleep(0)  # let the loop run the queued call_soon_threadsafe callbacks
            return _drain(queue)

    return asyncio.run(main())


def test_serialize_names_the_protocol_and_keeps_the_call_fields():
    NS = make_ns()

    @NS
    @Task
    class Load:
        def execute(self) -> None: ...

    seen = []
    with Context(namespaces={NS}) as ctx:
        ctx.events.subscribe(seen.append)
        ctx.execute(ctx.key(Load))

    started, completed = (events.serialize(e) for e in seen)
    assert started == {
        "type": "call",
        "key": ctx.key(Load),
        "protocol": "TaskProtocol",
        "method": "execute",
        "state": "started",
        "call_id": started["call_id"],
        "parent": None,
        "cause": None,
        "ts": started["ts"],
        "elapsed_ms": None,
        "error": None,
    }
    assert completed["state"] == "completed"
    assert completed["call_id"] == started["call_id"]
    assert completed["elapsed_ms"] is not None


def test_serialize_carries_a_failed_calls_error():
    NS = make_ns()

    @NS
    @Function
    def boom() -> None:
        raise ValueError("bad input")

    seen = []
    with Context(namespaces={NS}) as ctx:
        ctx.events.subscribe(seen.append)
        with pytest.raises(ValueError):
            ctx.call(ctx.key(boom))

    failed = events.serialize(seen[-1])
    assert failed["protocol"] == "FunctionProtocol"
    assert failed["state"] == "failed"
    assert failed["error"] == "ValueError('bad input')"


def test_hub_delivers_a_pipelines_steps_with_the_pipeline_as_parent():
    NS = make_ns()
    Step, Flow = _pipeline(NS)

    with Context(namespaces={NS}) as ctx:
        hub = events.EventHub(ctx)
        hub.start()
        items = _collect(hub, lambda: ctx.execute(ctx.key(Flow)))
        hub.stop()

    assert [(i["key"], i["state"]) for i in items] == [
        (ctx.key(Flow), "started"),
        (ctx.key(Step), "started"),
        (ctx.key(Step), "completed"),
        (ctx.key(Flow), "completed"),
    ]
    assert items[1]["parent"] == items[0]["call_id"]


def test_hub_resets_a_client_that_falls_behind(monkeypatch):
    monkeypatch.setattr(events, "QUEUE_SIZE", 2)
    NS = make_ns()
    Step, Flow = _pipeline(NS)

    with Context(namespaces={NS}) as ctx:
        hub = events.EventHub(ctx)
        hub.start()
        items = _collect(hub, lambda: ctx.execute(ctx.key(Flow)))
        hub.stop()

    assert items[0] == events.RESET
    assert items[-1]["key"] == ctx.key(Flow)
    assert items[-1]["state"] == "completed"


def test_hub_stop_unsubscribes_and_ends_clients():
    NS = make_ns()

    @NS
    @Task
    class Load:
        def execute(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        hub = events.EventHub(ctx)
        hub.start()

        def run():
            hub.stop()
            ctx.execute(ctx.key(Load))

        items = _collect(hub, run)

    assert items == [None]


def test_sse_formats_events_and_ends_on_stop():
    NS = make_ns()

    @NS
    @Task
    class Load:
        def execute(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        hub = events.EventHub(ctx)
        hub.start()

        async def main():
            stream = events.sse(hub)
            chunks = [await anext(stream)]  # registers the client

            def run():
                ctx.execute(ctx.key(Load))
                hub.stop()

            await asyncio.to_thread(run)
            chunks.extend([chunk async for chunk in stream])
            return chunks

        chunks = asyncio.run(main())

    assert chunks[0] == ": connected\n\n"
    assert [c.startswith("data: {") and c.endswith("}\n\n") for c in chunks[1:]] == [True, True]
    assert '"state": "completed"' in chunks[2]


# --- notifications ----------------------------------------------------------------


class _Ticket:
    """A record id JSON can't hold as it is."""

    def __str__(self) -> str:
        return "ticket-7"


def _publisher(NS):
    from opendataframework.notifications import Notifications, Publisher

    @Publisher("orders.received")
    @NS
    @Task
    class TakeOrder:
        def __init__(self, notifications: Notifications) -> None:
            self.notifications = notifications

        def execute(self) -> None:
            self.notifications.publish(
                "orders.received",
                {"id": 7, "items": {"baguette": 2}, "tags": {"rush"}},
                summary="Le Petit: 2 baguettes",
                level="warning",
                subject="repository.orders",
                record=_Ticket(),
            )

    return TakeOrder


def test_serialize_notification_makes_payload_and_record_json_ready():
    NS = make_ns()
    TakeOrder = _publisher(NS)

    seen = []
    with Context(namespaces={NS}) as ctx:
        ctx.notifications.subscribe(seen.append)
        ctx.execute(ctx.key(TakeOrder))

    item = events.serialize_notification(seen[0])
    assert item == {
        "type": "notification",
        "id": seen[0].id,
        "key": ctx.key(TakeOrder),
        "topic": "orders.received",
        "summary": "Le Petit: 2 baguettes",
        "level": "warning",
        "subject": "repository.orders",
        "record": "ticket-7",
        "parent": item["parent"],
        "ts": item["ts"],
        "payload": {"id": 7, "items": {"baguette": 2}, "tags": ["rush"]},
    }
    assert item["parent"] is not None  # published inside execute()
    json.dumps(item)


def test_serialize_names_the_notification_a_reaction_was_caused_by():
    NS = make_ns()
    TakeOrder = _publisher(NS)

    from opendataframework.notifications import Notification, Subscriber

    @Subscriber("orders.received")
    @NS
    @Component
    class Kitchen:
        def on_notification(self, notification: Notification) -> None: ...

    seen, published = [], []
    with Context(namespaces={NS}) as ctx:
        ctx.notifications.subscribe(published.append)
        ctx.events.subscribe(seen.append)
        ctx.execute(ctx.key(TakeOrder))

    reaction = next(events.serialize(e) for e in seen if e.key == ctx.key(Kitchen))
    assert reaction["method"] == "on_notification"
    assert reaction["cause"] == published[0].id
    assert reaction["parent"] is None
    top = next(events.serialize(e) for e in seen if e.key == ctx.key(TakeOrder))
    assert top["cause"] is None


def test_notification_hub_delivers_only_what_is_published_while_connected():
    NS = make_ns()
    TakeOrder = _publisher(NS)

    with Context(namespaces={NS}) as ctx:
        hub = events.NotificationHub(ctx)
        hub.start()
        ctx.execute(ctx.key(TakeOrder))  # no client yet
        items = _collect(hub, lambda: ctx.execute(ctx.key(TakeOrder)))
        hub.stop()

    assert [i["topic"] for i in items] == ["orders.received"]


def test_event_and_notification_hubs_stay_apart():
    NS = make_ns()
    TakeOrder = _publisher(NS)

    with Context(namespaces={NS}) as ctx:
        calls, notes = events.EventHub(ctx), events.NotificationHub(ctx)
        calls.start()
        notes.start()

        async def main():
            async with calls.client() as call_queue, notes.client() as note_queue:
                await asyncio.to_thread(ctx.execute, ctx.key(TakeOrder))
                await asyncio.sleep(0)
                return _drain(call_queue), _drain(note_queue)

        call_items, note_items = asyncio.run(main())
        calls.stop()
        notes.stop()

    assert {i["type"] for i in call_items} == {"call"}
    assert [i["type"] for i in note_items] == ["notification"]


def test_notification_hub_stop_unsubscribes_and_ends_clients():
    NS = make_ns()
    TakeOrder = _publisher(NS)

    with Context(namespaces={NS}) as ctx:
        hub = events.NotificationHub(ctx)
        hub.start()

        def run():
            hub.stop()
            ctx.execute(ctx.key(TakeOrder))

        items = _collect(hub, run)

    assert items == [None]
