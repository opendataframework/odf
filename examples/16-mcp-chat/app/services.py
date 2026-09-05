"""Background service for the MCP + chat example."""

import time

from opendataframework import Config, Service


@Service
class Watchdog:
    """Ticks in the background like 03-service's Heartbeat — its only job
    here is to be a Service that MCP's start_component/stop_component tools
    (or a chat model calling them) can toggle."""

    def __init__(self, config: Config) -> None:
        """Read the configured tick interval; leave the service stopped.

        Args:
            config: Project config; reads ``watchdog.interval`` (default ``1.0`` seconds).
        """
        self.interval = config.get("watchdog").get("interval", 1.0)
        self.count = 0
        self._running = False

    def setup(self) -> None:
        """Mark the service running, before ``run()`` starts ticking."""
        print("Watchdog.setup    watching for stalled tickets")
        self._running = True

    def run(self) -> None:
        """Tick once every ``interval`` seconds until ``stop()`` is called."""
        while self._running:
            time.sleep(self.interval)
            if self._running:
                self.count += 1
                print(f"Watchdog.run      check {self.count}")

    def stop(self) -> None:
        """Stop ticking."""
        print(f"Watchdog.stop     stopping after {self.count} checks")
        self._running = False
