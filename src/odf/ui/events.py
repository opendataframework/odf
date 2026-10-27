"""Streams the ``Context``'s protocol-call events to the browser.

``opendataframework`` reports every protocol call it makes, a task's
``execute()``, a function call, a service's ``setup()``, as ``Event``s on
``context.events``, whoever made the call: the UI, an MCP client, chat, a
pipeline running its steps. ``EventHub`` subscribes once and fans each event
out to every open ``GET /api/events`` response, which the topology turns into
run state on its nodes and edges.

Listeners run in the thread that made the call, so ``EventHub`` only hands
each event to the clients' event loops and never blocks it. No HTTP concerns
live here beyond formatting server-sent events.
"""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator, Callable

from opendataframework.context import Context
from opendataframework.events import Event

# Events a client may fall behind by before its queue is reset.
QUEUE_SIZE = 1000

# Seconds without an event before a comment line keeps the connection open
# (and finds out a client has gone).
PING_INTERVAL = 15.0

# Sent instead of the events a lagging client missed: it drops its run state.
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


class EventHub:
    """Fans one ``Context``'s events out to every connected client.

    Args:
        context: The ``Context`` whose ``events`` are streamed.
    """

    def __init__(self, context: Context) -> None:
        """See class docstring for ``Args``."""
        self._context = context
        self._lock = threading.Lock()
        self._clients: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._unsubscribe: Callable[[], None] | None = None

    def start(self) -> None:
        """Subscribe to the context's events. A second call is a no-op."""
        if self._unsubscribe is None:
            self._unsubscribe = self._context.events.subscribe(self._publish)

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
        """Register a queue receiving every event from now on, until exit.

        The queue yields event dicts, ``RESET`` after it overflowed, and
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

    def _publish(self, event: Event) -> None:
        """Hand ``event`` to every client's loop; never raises or blocks."""
        payload = serialize(event)
        with self._lock:
            clients = list(self._clients)
        for loop, queue in clients:
            # The loop is closed once its server has stopped.
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(_offer, queue, payload)


def _offer(queue: asyncio.Queue, item: dict | None) -> None:
    """Queue ``item``, replacing a full queue's backlog with ``RESET``."""
    if queue.full():
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(RESET)
    queue.put_nowait(item)


async def sse(hub: EventHub) -> AsyncIterator[str]:
    """Server-sent events for one client: a ``data:`` line per event."""
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
