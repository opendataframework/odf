"""Streams the ``Context``'s protocol-call events and notifications to the browser.

``opendataframework`` reports every protocol call it makes, a task's
``execute()``, a function call, a service's ``setup()``, as ``Event``s on
``context.events``, whoever made the call: the UI, an MCP client, chat, a
pipeline running its steps. ``EventHub`` subscribes once and fans each event
out to every open ``GET /api/events`` response, which the topology turns into
run state on its nodes and edges.

Components publish what happened in the business (a message arrived, a
threshold was crossed) as ``Notification``s on ``context.notifications``.
``NotificationHub`` fans those out to every open ``GET /api/notifications``
response, which the UI turns into toasts. The two streams stay separate, as
the two hubs upstream do.

Listeners run in the thread that made the call or published, so a hub only
hands each item to the clients' event loops and never blocks it. Only what
happens while a client is connected reaches it: there is no backlog. No HTTP
concerns live here beyond formatting server-sent events.
"""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator, Callable, Mapping

from opendataframework.context import Context
from opendataframework.events import Event
from opendataframework.notifications import Notification

# Items a client may fall behind by before its queue is reset.
QUEUE_SIZE = 1000

# Seconds without an item before a comment line keeps the connection open
# (and finds out a client has gone).
PING_INTERVAL = 15.0

# Sent instead of the items a lagging client missed: it drops its run state.
RESET = {"type": "reset"}


def serialize(event: Event) -> dict:
    """Return ``event`` as a JSON-ready dict, its protocol by name."""
    return {
        "type": "call",
        "key": event.key,
        "protocol": event.protocol.__name__,
        "method": event.method,
        "state": event.state,
        "call_id": event.call_id,
        "parent": event.parent,
        "ts": event.ts,
        "elapsed_ms": event.elapsed_ms,
        "error": event.error,
    }


def serialize_notification(notification: Notification) -> dict:
    """Return ``notification`` as a JSON-ready dict.

    Its ``payload`` is read-only and its ``record`` may be any object, so both
    are converted: a mapping becomes a dict, a set a list, and anything else
    JSON can't hold its ``str()``.
    """
    return {
        "type": "notification",
        "key": notification.key,
        "topic": notification.topic,
        "summary": notification.summary,
        "level": notification.level,
        "subject": notification.subject,
        "record": _json_ready(notification.record),
        "parent": notification.parent,
        "ts": notification.ts,
        "payload": _json_ready(notification.payload),
    }


def _json_ready(value: object) -> object:
    """Return ``value`` as plain JSON types."""
    return json.loads(json.dumps(value, default=_json_fallback))


def _json_fallback(value: object) -> object:
    """Convert what ``json`` can't serialize: mappings, sets, then anything as text."""
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (set, frozenset)):
        return list(value)
    return str(value)


class Hub:
    """Fans one ``Context`` source out to every connected client.

    A subclass names the source in ``_subscribe()``; this class owns the
    clients and their queues.

    Args:
        context: The ``Context`` whose items are streamed.
    """

    def __init__(self, context: Context) -> None:
        """See class docstring for ``Args``."""
        self._context = context
        self._lock = threading.Lock()
        self._clients: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._unsubscribe: Callable[[], None] | None = None

    def start(self) -> None:
        """Subscribe to the source. A second call is a no-op."""
        if self._unsubscribe is None:
            self._unsubscribe = self._subscribe()

    def stop(self) -> None:
        """Unsubscribe, and end every client's stream."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        with self._lock:
            clients = list(self._clients)
        for loop, queue in clients:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(_offer, queue, None)

    @contextlib.asynccontextmanager
    async def client(self) -> AsyncIterator[asyncio.Queue]:
        """Register a queue receiving every item from now on, until exit.

        The queue yields item dicts, ``RESET`` after it overflowed, and
        ``None`` once the hub has stopped.
        """
        entry = (asyncio.get_running_loop(), asyncio.Queue(maxsize=QUEUE_SIZE))
        with self._lock:
            self._clients.append(entry)
        try:
            yield entry[1]
        finally:
            with self._lock:
                self._clients.remove(entry)

    def _subscribe(self) -> Callable[[], None]:
        """Subscribe ``_publish`` to the source and return its unsubscribe."""
        raise NotImplementedError

    def _publish(self, payload: dict) -> None:
        """Hand ``payload`` to every client's loop; never raises or blocks."""
        with self._lock:
            clients = list(self._clients)
        for loop, queue in clients:
            # The loop is closed once its server has stopped.
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(_offer, queue, payload)


class EventHub(Hub):
    """Fans one ``Context``'s events out to every connected client."""

    def _subscribe(self) -> Callable[[], None]:
        """Subscribe to every event of the context."""
        return self._context.events.subscribe(lambda event: self._publish(serialize(event)))


class NotificationHub(Hub):
    """Fans one ``Context``'s notifications out to every connected client."""

    def _subscribe(self) -> Callable[[], None]:
        """Subscribe to every notification of the context, whatever its topic."""
        return self._context.notifications.subscribe(
            lambda notification: self._publish(serialize_notification(notification))
        )


def _offer(queue: asyncio.Queue, item: dict | None) -> None:
    """Queue ``item``, replacing a full queue's backlog with ``RESET``."""
    if queue.full():
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(RESET)
    queue.put_nowait(item)


async def sse(hub: Hub) -> AsyncIterator[str]:
    """Server-sent events for one client: a ``data:`` line per item."""
    async with hub.client() as queue:
        yield ": connected\n\n"
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), PING_INTERVAL)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if item is None:
                return
            yield f"data: {json.dumps(item)}\n\n"
