"""Background service for the flat-grid example."""

import time

from opendataframework import Service


@Service
class Tracker:
    """Polls the couriers' positions in the background, here just a tick."""

    def __init__(self) -> None:
        """Leave the service stopped."""
        self.count = 0
        self._running = False

    def setup(self) -> None:
        """Mark the service running, before ``run()`` starts ticking."""
        self._running = True

    def run(self) -> None:
        """Tick once a second until ``stop()`` is called."""
        while self._running:
            time.sleep(1.0)
            if self._running:
                self.count += 1

    def stop(self) -> None:
        """Stop ticking."""
        self._running = False
