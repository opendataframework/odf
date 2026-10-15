from collections.abc import Callable
from typing import Annotated

import pytest
from opendataframework.agent import Agent
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.entity import Entity
from opendataframework.function import Function
from opendataframework.layer import Storage
from opendataframework.namespace import Namespace
from opendataframework.pipeline import Pipeline
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.task import Task

from odf.ui.topology import TopologyView, build_topology


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

    @Entity
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

    @NS
    @Agent
    class TopoAgent:
        def invoke(self, question: str) -> str: ...

    with Context(namespaces={NS}, config={"k": "v"}) as ctx:
        data = build_topology(ctx, "test-project")

    types = {n["label"]: n["type"] for n in data["nodes"]}
    assert types["TopoComponent"] == "component"
    assert types["TopoRepository"] == "repository"
    assert types["TopoService"] == "service"
    assert types["TopoTask"] == "task"
    assert types["TopoPipeline"] == "pipeline"
    assert types["TopoAgent"] == "agent"
    assert types["Config"] == "config"
    decorators = {n["label"]: n["decorator"] for n in data["nodes"]}
    assert decorators["TopoAgent"] == "@Agent"


# --- ids and routes ------------------------------------------------------------


def test_node_id_is_the_key_and_href_follows_the_execution_type():
    NS = make_ns()

    @NS("loader")
    @Task
    class TopoLoadJob:
        def execute(self) -> None: ...

    with Context(namespaces={NS}, config={"k": "v"}) as ctx:
        data = build_topology(ctx, "proj")

    by_label = {n["label"]: n for n in data["nodes"]}
    assert by_label["TopoLoadJob"]["id"] == "n-s.loader"
    assert by_label["TopoLoadJob"]["name"] == "loader"
    assert by_label["TopoLoadJob"]["href"] == "/api/tasks/loader"
    assert by_label["Config"]["id"] == "config"
    assert by_label["Config"]["href"] is None


def test_same_class_name_in_two_namespaces_gets_two_nodes():
    class TaskNS(Namespace): ...

    class ComponentNS(Namespace): ...

    task = TaskNS(Task(type("Loader", (), {"execute": lambda self: None})))
    component = ComponentNS(Component(type("Loader", (), {})))

    with Context(namespaces={TaskNS, ComponentNS}) as ctx:
        data = build_topology(ctx, "proj")
        keys = {ctx.key(task), ctx.key(component)}

    assert len(keys) == 2
    assert ids(data) == keys
    assert {n["href"] for n in data["nodes"]} == {"/api/tasks/loader", "/api/components/loader"}


# --- functions ----------------------------------------------------------------


def make_functions():
    """Return ``(NS, Db, load, Refresh)``: Db -> load -> Refresh, and load -> sync."""
    NS = make_ns()

    @NS
    @Component
    class FnDb: ...

    @NS("loader")
    @Storage
    @Function
    def load(path: str, db: FnDb) -> int:
        """Load rows from a file into the database.

        Longer details.
        """
        return 1

    @NS
    @Function
    def sync(run: Annotated[Callable[..., int], load]) -> int:
        return run("data.csv")

    @NS
    @Task
    class FnRefresh:
        def __init__(self, load: Annotated[Callable[..., int], load]) -> None:
            self.load = load

        def execute(self) -> None: ...

    return NS, FnDb, load, FnRefresh


def test_function_is_a_node_addressed_by_its_key():
    NS, *_ = make_functions()

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    node = next(n for n in data["nodes"] if n["label"] == "load")
    assert node["id"] == "n-s.loader"
    assert node["name"] == "loader"
    assert node["type"] == "function"
    assert node["decorator"] == "@Function"
    assert node["layer"] == "storage"
    assert node["href"] == "/api/functions/loader"
    assert node["file"] == "tests/test_ui_topology.py"
    assert node["desc"] == "Load rows from a file into the database."
    assert node["details"] is False
    assert node["chart"] is False
    assert data["stats"]["types"]["function"] == 2


def test_function_edges_run_both_ways():
    NS, *_ = make_functions()

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj")

    assert edge_pairs(data) == {
        ("n-s.fn-db", "n-s.loader"),
        ("n-s.loader", "n-s.fn-refresh"),
        ("n-s.loader", "n-s.sync"),
    }
    cols = {n["id"]: n["col"] for n in data["nodes"]}
    assert cols["n-s.fn-db"] < cols["n-s.loader"] < cols["n-s.sync"]


def test_functions_list_filters_functions_and_bridges_a_hidden_one():
    NS, *_ = make_functions()

    view = TopologyView.from_config({"functions": ["sync", "missing"]})
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "proj", view)
        unmatched = view.unmatched(ctx)

    assert "n-s.loader" not in ids(data)
    assert {("n-s.fn-db", "n-s.sync"), ("n-s.fn-db", "n-s.fn-refresh")} <= edge_pairs(data)
    assert unmatched == [("functions", "missing")]


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

        ctx.stop(ctx.key(TopoRunningService))
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

    assert {"from": "n-s.topo-base", "to": "n-s.topo-derived"} in data["edges"]


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

    @Entity
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


# --- topology view: connections and component visibility ---------------------


def make_chain():
    """Return ``(NS, Store, Mid, Job)``: a Job task -> Mid component -> Store component chain."""
    NS = make_ns()

    @NS
    @Component
    class ViewStore: ...

    @NS
    @Component
    class ViewMid:
        def __init__(self, store: ViewStore) -> None:
            self.store = store

    @NS
    @Task
    class ViewJob:
        def __init__(self, mid: ViewMid) -> None:
            self.mid = mid

        def execute(self) -> None: ...

    return NS, ViewStore, ViewMid, ViewJob


def ids(data):
    return {n["id"] for n in data["nodes"]}


def edge_pairs(data):
    return {(e["from"], e["to"]) for e in data["edges"]}


def test_default_view_matches_no_view():
    NS, *_ = make_chain()

    with Context(namespaces={NS}) as ctx:
        assert build_topology(ctx, "p", TopologyView()) == build_topology(ctx, "p")


def test_connections_off_draws_no_edges_but_keeps_nodes_and_layout():
    NS, *_ = make_chain()

    with Context(namespaces={NS}) as ctx:
        full = build_topology(ctx, "p")
        data = build_topology(ctx, "p", TopologyView(connections=False))

    assert data["edges"] == []
    assert data["stats"]["links"] == 0
    assert data["nodes"] == full["nodes"]


def test_list_shows_only_listed_components_of_that_kind():
    NS = make_ns()

    @NS
    @Task
    class ViewKept:
        def execute(self) -> None: ...

    @NS
    @Task
    class ViewDropped:
        def execute(self) -> None: ...

    view = TopologyView.from_config({"tasks": ["ViewKept"]})
    with Context(namespaces={NS}) as ctx:
        assert ids(build_topology(ctx, "p", view)) >= {"n-s.view-kept"}
        assert "n-s.view-dropped" not in ids(build_topology(ctx, "p", view))


def test_agents_list_filters_agents():
    NS = make_ns()

    @NS
    @Agent
    class ViewAsker:
        def invoke(self) -> None: ...

    @NS
    @Agent
    class ViewHidden:
        def invoke(self) -> None: ...

    view = TopologyView.from_config({"agents": ["view-asker", "view-missing"]})
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", view)
        unmatched = view.unmatched(ctx)

    assert "n-s.view-asker" in ids(data)
    assert "n-s.view-hidden" not in ids(data)
    assert unmatched == [("agents", "view-missing")]


def test_kind_without_a_list_shows_every_component_of_that_kind():
    NS, *_ = make_chain()

    view = TopologyView.from_config({"tasks": []})
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", view)

    assert "n-s.view-job" not in ids(data)
    assert {"n-s.view-store", "n-s.view-mid"} <= ids(data)


def test_names_match_class_name_kebab_id_and_snake_case():
    NS, *_ = make_chain()

    for name in ("ViewStore", "view-store", "view_store"):
        view = TopologyView.from_config({"components": [name]})
        with Context(namespaces={NS}) as ctx:
            data = build_topology(ctx, "p", view)
        assert "n-s.view-store" in ids(data)
        assert "n-s.view-mid" not in ids(data)


def test_config_false_hides_the_config_node():
    NS, *_ = make_chain()

    with Context(namespaces={NS}, config={"k": "v"}) as ctx:
        shown = build_topology(ctx, "p")
        hidden = build_topology(ctx, "p", TopologyView.from_config({"config": False}))

    assert any(n["type"] == "config" for n in shown["nodes"])
    assert not any(n["type"] == "config" for n in hidden["nodes"])


def test_hidden_component_is_bridged_and_layout_has_no_gap():
    NS, *_ = make_chain()

    view = TopologyView.from_config({"components": ["ViewStore"]})
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", view)

    assert ids(data) == {"n-s.view-store", "n-s.view-job"}
    assert edge_pairs(data) == {("n-s.view-store", "n-s.view-job")}
    cells = {n["id"]: (n["col"], n["row"]) for n in data["nodes"]}
    assert cells == {"n-s.view-store": (0, 0), "n-s.view-job": (1, 0)}


def test_bridged_edges_are_not_duplicated():
    NS = make_ns()

    @NS
    @Component
    class ViewLeaf: ...

    @NS
    @Component
    class ViewLeft:
        def __init__(self, leaf: ViewLeaf) -> None: ...

    @NS
    @Component
    class ViewRight:
        def __init__(self, leaf: ViewLeaf) -> None: ...

    @NS
    @Task
    class ViewTop:
        def __init__(self, left: ViewLeft, right: ViewRight) -> None: ...

        def execute(self) -> None: ...

    view = TopologyView.from_config({"components": ["ViewLeaf"]})
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", view)

    assert data["edges"] == [{"from": "n-s.view-leaf", "to": "n-s.view-top"}]


def test_stats_describe_the_visible_graph():
    NS, *_ = make_chain()

    view = TopologyView.from_config({"components": []})
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", view)

    assert data["stats"] == {"objects": 1, "links": 0, "types": {"task": 1}}


def test_view_config_rejects_unknown_keys_and_wrong_types():
    with pytest.raises(ValueError, match="Unknown"):
        TopologyView.from_config({"task": []})
    with pytest.raises(ValueError, match="connections"):
        TopologyView.from_config({"connections": "no"})
    with pytest.raises(ValueError, match="tasks"):
        TopologyView.from_config({"tasks": "seed"})
    with pytest.raises(ValueError, match="components"):
        TopologyView.from_config({"components": [1]})


def test_unmatched_reports_names_that_match_no_component_of_that_kind():
    NS, *_ = make_chain()

    view = TopologyView.from_config({"components": ["ViewStore", "Nope"], "tasks": ["ViewStore"]})
    with Context(namespaces={NS}) as ctx:
        assert view.unmatched(ctx) == [("components", "nope"), ("tasks", "view-store")]


# --- saved layout: cells never overlap -----------------------------------------


def cells_of(data):
    return {n["id"]: (n["col"], n["row"]) for n in data["nodes"]}


def test_saved_cell_is_kept():
    NS, *_ = make_chain()

    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", layout={"n-s.view-job": {"col": 5, "row": 3}})

    assert cells_of(data)["n-s.view-job"] == (5, 3)


def test_auto_node_on_a_saved_cell_moves_to_the_nearest_free_row_in_its_column():
    NS = make_ns()

    @NS
    @Component
    class ViewA: ...

    @NS
    @Component
    class ViewB: ...

    with Context(namespaces={NS}) as ctx:
        auto = cells_of(build_topology(ctx, "p"))
        assert auto == {"n-s.view-a": (0, 0), "n-s.view-b": (0, 1)}
        # Pin B onto A's automatic cell: A must yield, staying in column 0.
        data = build_topology(ctx, "p", layout={"n-s.view-b": {"col": 0, "row": 0}})

    assert cells_of(data) == {"n-s.view-b": (0, 0), "n-s.view-a": (0, 1)}


def test_two_saved_cells_on_the_same_slot_keep_the_first_id():
    NS = make_ns()

    @NS
    @Component
    class ViewA: ...

    @NS
    @Component
    class ViewB: ...

    layout = {"n-s.view-a": {"col": 4, "row": 4}, "n-s.view-b": {"col": 4, "row": 4}}
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", layout=layout)

    cells = cells_of(data)
    assert cells["n-s.view-a"] == (4, 4)
    assert cells["n-s.view-b"] != (4, 4)
    assert len(set(cells.values())) == 2


def test_saved_cell_of_a_hidden_node_reserves_nothing_and_returns_when_shown():
    NS = make_ns()

    @NS
    @Component
    class ViewA: ...

    @NS
    @Component
    class ViewB: ...

    layout = {"n-s.view-a": {"col": 0, "row": 0}}
    with Context(namespaces={NS}) as ctx:
        hidden = build_topology(
            ctx, "p", TopologyView.from_config({"components": ["ViewB"]}), layout
        )
        shown = build_topology(ctx, "p", layout=layout)

    assert cells_of(hidden) == {"n-s.view-b": (0, 0)}
    assert cells_of(shown) == {"n-s.view-a": (0, 0), "n-s.view-b": (0, 1)}


def test_non_node_and_malformed_layout_entries_are_ignored():
    NS, *_ = make_chain()

    layout = {
        "_grid": {"nw": 1, "ne": 0, "se": 0, "sw": 0},
        "_layers": {"x": "#fff"},
        "n-s.view-job": {"col": True, "row": 1},
        "n-s.view-mid": {"col": "2", "row": 1},
        "n-s.view-store": "nope",
    }
    with Context(namespaces={NS}) as ctx:
        assert build_topology(ctx, "p", layout=layout) == build_topology(ctx, "p")


def test_resolved_cells_are_unique():
    NS = make_ns()

    for name in "ABCDE":
        NS(Component(type(f"View{name}", (), {})))

    layout = {"n-s.view-c": {"col": 0, "row": 0}, "n-s.view-e": {"col": 0, "row": 1}}
    with Context(namespaces={NS}) as ctx:
        data = build_topology(ctx, "p", layout=layout)

    assert len(set(cells_of(data).values())) == 5
