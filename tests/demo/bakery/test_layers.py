import app  # noqa: F401  (registers every class and function)
from opendataframework import Storage

from odf.ui.keys import EXEC_NAMESPACES
from odf.ui.topology import _layer_name

AREAS = {"integrations", "wholesale", "cafe", "production", "purchasing", "allergens", "drafts"}

# Read at import, while the bakery's registrations are in place: the examples'
# isolation (tests/examples/_isolation.py) drops them once collection ends.
NODES = [
    obj
    for _, namespace in EXEC_NAMESPACES
    for obj in dict(namespace.items()).values()
    if obj.__module__.startswith("app.")
]
LAYERS = {node.__qualname__: _layer_name(node) for node in NODES}
STORAGE = set(dict(Storage.items()).values())


def test_every_node_is_in_an_area():
    assert NODES
    # SQLite is the database every area shares, so it stays in Storage.
    sqlite = next(node for node in NODES if node.__qualname__ == "SQLite")
    assert sqlite in STORAGE
    areas = {name: layer for name, layer in LAYERS.items() if name != "SQLite"}
    outside = {name: layer for name, layer in areas.items() if layer not in AREAS}
    assert not outside
    assert set(areas.values()) == AREAS
