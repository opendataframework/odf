from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.layer import Storage
from opendataframework.namespace import Namespace
from opendataframework.pipeline import Pipeline
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.task import Task

from odf.ui.topology import build_topology


def make_ns():
    """Return a fresh isolated Namespace subclass to scope Context resolution.

    Classification in build_topology() still checks the real global
    Component/Repository/Service/Task/Pipeline/Layer namespaces — this NS
    only controls which classes a given Context resolves, mirroring the
    isolation pattern used across the rest of the test suite.
    """

    class NS(Namespace): ...

    return NS


# --- node classification -------------------------------------------------------


def test_classifies_node_types_and_config():
    NS = make_ns()

    @NS
    @Component
    class TopoComponent: ...

    class TopoEntity: ...

    @NS
    @Repository(TopoEntity)
    class TopoRepository: ...

    @NS
    @Service
    class TopoService:
        def setup(self) -> None: ...
        def run(self) -> None: ...
        def stop(self) -> None: ...

    @NS
    @Task
    class TopoTask:
        def execute(self) -> None: ...

    @NS
    @Pipeline
    class TopoPipeline:
        def execute(self) -> None: ...

    with Context(namespaces={NS}, config={"k": "v"}) as ctx:
        data = build_topology(ctx, "test-project")

    types = {n["label"]: n["type"] for n in data["nodes"]}
    assert types["TopoComponent"] == "component"
    assert types["TopoRepository"] == "repository"
    assert types["TopoService"] == "service"
    assert types["TopoTask"] == "task"
    assert types["TopoPipeline"] == "pipeline"
    assert types["Config"] == "config"


# --- service running state --------------------------------------------------


def test_service_node_reports_running_state():
    NS = make_ns()

    @NS
    @Service
    class TopoRunningService:
        def setup(self) -> None: ...
        def run(self) -> None: ...
        def stop(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")
        node = next(n for n in data["nodes"] if n["label"] == "TopoRunningService")
        assert node["running"] is True

        ctx.stop("TopoRunningService")
        data = build_topology(ctx, "proj")
        node = next(n for n in data["nodes"] if n["label"] == "TopoRunningService")
        assert node["running"] is False


def test_non_service_nodes_have_no_running_key():
    NS = make_ns()

    @NS
    @Component
    class TopoPlainComponent: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    node = next(n for n in data["nodes"] if n["label"] == "TopoPlainComponent")
    assert "running" not in node


# --- details capability -------------------------------------------------------


def test_node_reports_details_capability():
    NS = make_ns()

    @NS
    @Component
    class TopoDetailedComponent:
        def details(self) -> dict[str, str]:
            return {"UI": "http://localhost:1234"}

    @NS
    @Component
    class TopoPlainComponent: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    detailed = next(n for n in data["nodes"] if n["label"] == "TopoDetailedComponent")
    plain = next(n for n in data["nodes"] if n["label"] == "TopoPlainComponent")
    assert detailed["details"] is True
    assert plain["details"] is False


# --- chart capability --------------------------------------------------------


def test_node_reports_chart_capability():
    NS = make_ns()

    @NS
    @Component
    class TopoChartedComponent:
        def chart(self) -> str:
            return "<html></html>"

    @NS
    @Component
    class TopoPlainComponent: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    charted = next(n for n in data["nodes"] if n["label"] == "TopoChartedComponent")
    plain = next(n for n in data["nodes"] if n["label"] == "TopoPlainComponent")
    assert charted["chart"] is True
    assert plain["chart"] is False


# --- edges -----------------------------------------------------------------


def test_edges_reflect_constructor_dependencies():
    NS = make_ns()

    @NS
    @Component
    class TopoBase: ...

    @NS
    @Component
    class TopoDerived:
        def __init__(self, base: TopoBase) -> None:
            self.base = base

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    assert {"from": "topo-base", "to": "topo-derived"} in data["edges"]


def test_edges_exclude_dependencies_outside_the_resolved_set():
    NS = make_ns()

    class TopoExternalHelper:
        def __init__(self) -> None: ...

    @NS
    @Component
    class TopoLonely:
        # TopoExternalHelper is a real type but never registered under NS, so
        # it never enters this Context's instance set — the Resolver skips
        # it (default kicks in) and build_topology must not draw an edge to it.
        def __init__(self, helper: TopoExternalHelper = None) -> None: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    assert data["edges"] == []


# --- layout ------------------------------------------------------------------


def test_layout_orders_nodes_by_dependency_depth():
    NS = make_ns()

    @NS
    @Component
    class TopoA: ...

    @NS
    @Component
    class TopoB:
        def __init__(self, a: TopoA) -> None: ...

    @NS
    @Component
    class TopoC:
        def __init__(self, b: TopoB) -> None: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    by_label = {n["label"]: n for n in data["nodes"]}
    assert by_label["TopoA"]["col"] < by_label["TopoB"]["col"] < by_label["TopoC"]["col"]


# --- decorator label -----------------------------------------------------------


def test_decorator_label_excludes_layer_and_includes_repository_entity():
    NS = make_ns()

    class TopoUser: ...

    @NS
    @Storage
    @Repository(TopoUser)
    class TopoUsers: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    node = next(n for n in data["nodes"] if n["label"] == "TopoUsers")
    assert node["decorator"] == "@Repository(TopoUser)"
    assert node["layer"] == "storage"


# --- stats -----------------------------------------------------------------


def test_stats_counts_objects_links_and_types():
    NS = make_ns()

    @NS
    @Component
    class TopoAlpha: ...

    @NS
    @Task
    class TopoBeta:
        def __init__(self, a: TopoAlpha) -> None: ...
        def execute(self) -> None: ...

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    assert data["stats"]["objects"] == 2
    assert data["stats"]["links"] == 1
    assert data["stats"]["types"] == {"component": 1, "task": 1}


# --- project name --------------------------------------------------------------


def test_project_name_passthrough_and_empty_graph():
    with Context(namespaces=set()) as ctx:
        data = build_topology(ctx, "my-app")

    assert data["project"] == "my-app"
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["stats"] == {"objects": 0, "links": 0, "types": {}}
