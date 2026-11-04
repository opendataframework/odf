import tomllib

import app  # noqa: F401  (registers every class and function)
from opendataframework.utils import normalize

from odf.ui import keys, views
from odf.ui.topology import TopologyView

from .conftest import DEMO_DIR

# Read at import, while the bakery's registrations are in place: the examples'
# isolation (tests/examples/_isolation.py) drops them once collection ends.
REGISTERED: dict[str, set[str]] = {}
for _, namespace in keys.EXEC_NAMESPACES:
    for name, obj in namespace.items():
        if obj.__module__.startswith("app."):
            REGISTERED.setdefault(keys.exec_type(obj), set()).add(normalize(name))

VIEWS, DEFAULT = views.from_config(tomllib.loads((DEMO_DIR / "config.toml").read_text())["ui"])


def test_the_manager_view_is_shown_first_and_the_system_view_beside_it():
    assert list(VIEWS) == ["manager", "system"]
    assert DEFAULT == "manager"


def test_every_name_a_view_lists_is_a_component_of_that_kind():
    unmatched = {
        (view.name, kind, name)
        for view in VIEWS.values()
        for kind, names in view.topology.show.items()
        for name in names - REGISTERED.get(kind, set())
    }
    assert not unmatched


def test_the_manager_view_shows_the_routines_not_their_steps():
    manager = VIEWS["manager"].topology
    assert manager == TopologyView(
        config=False,
        show={
            "component": frozenset(),
            "service": frozenset(),
            "task": frozenset(),
            "pipeline": frozenset({"close-cafe", "night-run"}),
            "function": frozenset(
                {
                    "confirm-draft",
                    "edit-draft",
                    "reject-draft",
                    "what-if",
                    "margins",
                    "trace-ingredient",
                    "labels",
                }
            ),
        },
    )
