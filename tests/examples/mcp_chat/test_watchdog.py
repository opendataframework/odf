import threading
import time

import pytest
from app.services import Watchdog
from opendataframework.config import Config

# Deliberately drives setup()/run()/stop() by hand rather than through
# Project/Context — same reason as the other examples' tests (see
# tests/examples/entity_repository/test_books.py): @Service registration is
# global for the whole pytest process. run() blocks by design, so it's driven
# in a thread here the same way the Context would background it.


@pytest.fixture
def watchdog() -> Watchdog:
    return Watchdog(Config({"watchdog": {"interval": 0.01}}))


def test_watchdog_reads_interval_from_config(watchdog):
    assert watchdog.interval == 0.01


def test_watchdog_falls_back_to_default_interval():
    watchdog = Watchdog(Config({}))
    assert watchdog.interval == 1.0


def test_watchdog_ticks_while_running_then_stops_cleanly(watchdog):
    watchdog.setup()
    thread = threading.Thread(target=watchdog.run)
    thread.start()

    time.sleep(0.05)
    watchdog.stop()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert watchdog.count > 0
