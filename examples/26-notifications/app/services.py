"""The counter taking orders in the background."""

import time
from collections.abc import Callable
from itertools import cycle
from typing import Annotated

from opendataframework import Config, Service

from app.functions import take_order

# The orders the counter takes, in turn: (table, item). Oat flat whites come
# up often enough to run the oat milk out.
ORDERS: tuple[tuple[int, str], ...] = (
    (4, "flat white"),
    (2, "croissant"),
    (7, "oat flat white"),
    (1, "flat white"),
    (5, "oat flat white"),
    (3, "croissant"),
    (6, "oat flat white"),
)


@Service
class Counter:
    """Takes the next order every ``[service.counter] interval`` seconds.

    Each order goes through ``take_order``, injected with its own
    dependencies filled in, rather than being handled inside ``run()``. So
    every order is a call of its own: it shows on the topology, it's logged,
    and the notifications it publishes carry that call as their ``parent``.
    """

    def __init__(
        self,
        config: Config,
        order: Annotated[Callable[..., int | None], take_order],
    ) -> None:
        """Read the interval and leave the service stopped.

        Args:
            config: Project config; reads ``service.counter.interval``
                (default ``4.0`` seconds).
            order: ``take_order``, taking only the table and the item.
        """
        self.interval = float(config.get("service").get("counter").get("interval", 4.0))
        self.order = order
        self._next = cycle(ORDERS)
        self._running = False

    def setup(self) -> None:
        """Mark the service running, before ``run()`` starts taking orders."""
        self._running = True

    def run(self) -> None:
        """Take an order every ``interval`` seconds until ``stop()`` is called."""
        while self._running:
            time.sleep(self.interval)
            if self._running:
                self.tick()

    def tick(self) -> int | None:
        """Take the next order in ``ORDERS``, and return its id."""
        table, item = next(self._next)
        return self.order(table, item)

    def stop(self) -> None:
        """Stop taking orders."""
        self._running = False
