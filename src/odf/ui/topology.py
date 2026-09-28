"""Builds a JSON-serializable topology graph from a resolved ``Context``.

Pure introspection: reads ``Context.instances`` (populated after
``Context.open()`` / ``Project.start()``) and the class-level registration
metadata already tracked by ``Namespace`` subclasses (``Component``,
``Repository``, ``Service``, ``Task``, ``Pipeline``, ``Layer``). Nothing here
touches the DI container or drives lifecycle — it only describes what has
already been resolved.
"""

import inspect
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from opendataframework.component import ChartProtocol, Component, DetailsProtocol
from opendataframework.config import Config
from opendataframework.context import Context, Resolver
from opendataframework.layer import Layer
from opendataframework.namespace import Namespace
from opendataframework.pipeline import Pipeline
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.task import Task
from opendataframework.utils import kebab, normalize

# Order matters only in that a class is expected to be registered under
# exactly one of these — first match wins if that assumption is ever broken.
_EXEC_NAMESPACES: list[tuple[str, type[Namespace]]] = [
    ("repository", Repository),
    ("service", Service),
    ("task", Task),
    ("pipeline", Pipeline),
    ("component", Component),
]


# ``[ui.topology]`` list key -> the ``_exec_type`` label it filters.
_KIND_KEYS = {
    "repositories": "repository",
    "services": "service",
    "tasks": "task",
    "pipelines": "pipeline",
    "components": "component",
}


@dataclass(frozen=True)
class TopologyView:
    """Which components and connections the topology shows.

    The default shows everything. Built from the ``[ui.topology]`` config
    table by ``from_config``.

    Attributes:
        connections: Whether edges between components are drawn.
        show: Per kind (an ``_exec_type`` label such as ``"task"``), the
            normalized names to show. A kind that is absent from the mapping
            shows every component of that kind; a kind mapped to an empty set
            shows none.
        config: Whether the ``Config`` node is shown.
    """

    connections: bool = True
    show: Mapping[str, frozenset[str]] = field(default_factory=dict)
    config: bool = True

    @classmethod
    def from_config(cls, cfg: Mapping) -> TopologyView:
        """Build a view from the ``[ui.topology]`` table.

        Args:
            cfg: The parsed table: ``connections`` and ``config`` booleans plus
                any of ``repositories``/``services``/``tasks``/``pipelines``/
                ``components`` as lists of class names or kebab ids.

        Raises:
            ValueError: On an unknown key or a value of the wrong type.
        """
        unknown = set(cfg) - {"connections", "config", *_KIND_KEYS}
        if unknown:
            raise ValueError(f"Unknown [ui.topology] key(s): {', '.join(sorted(unknown))}")
        flags = {}
        for key in ("connections", "config"):
            value = cfg.get(key, True)
            if not isinstance(value, bool):
                raise ValueError(f"[ui.topology] {key} must be true or false, got {value!r}")
            flags[key] = value
        show = {}
        for key, kind in _KIND_KEYS.items():
            if key not in cfg:
                continue
            names = cfg[key]
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                raise ValueError(f"[ui.topology] {key} must be a list of names, got {names!r}")
            show[kind] = frozenset(normalize(n) for n in names)
        return cls(connections=flags["connections"], show=show, config=flags["config"])

    def is_visible(self, cls: type, instance: object) -> bool:
        """Return whether ``cls`` (resolved to ``instance``) is shown."""
        if isinstance(instance, Config):
            return self.config
        names = self.show.get(_exec_type(cls))
        return names is None or _id(cls) in names

    def unmatched(self, context: Context) -> list[tuple[str, str]]:
        """Return ``(list key, name)`` pairs naming no component of that kind."""
        found: dict[str, set[str]] = {}
        for cls in context.instances:
            found.setdefault(_exec_type(cls) or "", set()).add(_id(cls))
        keys = {kind: key for key, kind in _KIND_KEYS.items()}
        return [
            (keys[kind], name)
            for kind, names in sorted(self.show.items())
            for name in sorted(names - found.get(kind, set()))
        ]


def build_topology(
    context: Context,
    project: str = "ODF Project",
    view: TopologyView | None = None,
    layout: Mapping[str, object] | None = None,
) -> dict:
    """Build a JSON-serializable topology graph for the given ``Context``.

    Args:
        context: A ``Context`` that has already been opened (i.e.
            ``Context.instances`` is populated).
        project: Display name for the project, shown in the UI header.
        view: Which components and connections to include. ``None`` shows
            everything. A hidden component's connections are bridged: its
            visible dependents are linked to its visible dependencies.
        layout: Saved layout overrides (node id to ``{"col", "row", ...}``, as
            read from the layout file). A node with a saved cell keeps it;
            any other node whose cell is taken moves to the nearest free
            cell in its column. Entries without an integer ``col`` and ``row``
            (such as ``_grid``) are ignored.

    Returns:
        A dict with ``project``, ``nodes``, ``edges``, and ``stats`` keys,
        suitable for ``json`` serialization.
    """
    view = view or TopologyView()
    instances = context.instances
    all_set = set(instances)
    node_set = {cls for cls in all_set if view.is_visible(cls, instances[cls])}

    deps = {cls: _visible_dependencies(cls, node_set, all_set) for cls in node_set}
    depths = _compute_depths(deps)
    by_depth: dict[int, list[type]] = {}
    for cls in node_set:
        by_depth.setdefault(depths[cls], []).append(cls)

    auto: dict[type, tuple[int, int]] = {}
    for depth in sorted(by_depth):
        for row, cls in enumerate(sorted(by_depth[depth], key=lambda c: c.__name__)):
            auto[cls] = (depth, row)
    cells = _resolve_cells(auto, _pinned_cells(layout))

    nodes = []
    for cls in sorted(node_set, key=lambda c: (cells[c], c.__name__)):
        col, row = cells[cls]
        node = _describe_node(cls, instances[cls], col=col, row=row)
        if node["type"] == "service":
            node["running"] = context.is_running(cls.__name__)
        nodes.append(node)

    edges = (
        [
            {"from": _id(dep), "to": _id(cls)}
            for cls in sorted(node_set, key=lambda c: c.__name__)
            for dep in sorted(deps[cls], key=lambda c: c.__name__)
        ]
        if view.connections
        else []
    )

    return {
        "project": project,
        "nodes": nodes,
        "edges": edges,
        "stats": _stats(nodes, edges),
    }


def _visible_dependencies(cls: type, visible: set[type], all_set: set[type]) -> set[type]:
    """Return the nearest visible dependencies of ``cls``, looking through hidden ones."""
    found: set[type] = set()
    seen: set[type] = set()
    stack = [cls]
    while stack:
        current = stack.pop()
        for dep in Resolver.dependencies(current).values():
            if dep not in all_set or dep is cls or dep in seen:
                continue
            seen.add(dep)
            if dep in visible:
                found.add(dep)
            else:
                stack.append(dep)
    return found


def _compute_depths(deps: Mapping[type, set[type]]) -> dict[type, int]:
    """Return each class's longest-path depth given its dependencies among the same classes."""
    depths: dict[type, int] = {}

    def depth(cls: type, trail: frozenset[type]) -> int:
        if cls in depths:
            return depths[cls]
        if cls in trail:
            return 0  # circular deps can't happen post-resolve; guard defensively anyway
        result = 0 if not deps[cls] else 1 + max(depth(d, trail | {cls}) for d in deps[cls])
        depths[cls] = result
        return result

    for cls in deps:
        depth(cls, frozenset())
    return depths


def _pinned_cells(layout: Mapping[str, object] | None) -> dict[str, tuple[int, int]]:
    """Return the ``(col, row)`` cell saved for each node id in ``layout``."""
    pins: dict[str, tuple[int, int]] = {}
    for node_id, entry in (layout or {}).items():
        if not isinstance(entry, Mapping):
            continue
        col, row = entry.get("col"), entry.get("row")
        if all(isinstance(v, int) and not isinstance(v, bool) for v in (col, row)):
            pins[node_id] = (col, row)
    return pins


def _resolve_cells(
    auto: Mapping[type, tuple[int, int]], pins: Mapping[str, tuple[int, int]]
) -> dict[type, tuple[int, int]]:
    """Assign every class a unique ``(col, row)`` cell.

    A class with a saved cell keeps it (the first id wins if two share one).
    Any other class keeps its automatic cell unless a saved cell took it, in
    which case it moves to the nearest free row of its column.
    """
    cells: dict[type, tuple[int, int]] = {}
    taken: set[tuple[int, int]] = set()
    by_id = {_id(cls): cls for cls in auto}
    for node_id in sorted(pins):
        if node_id in by_id and pins[node_id] not in taken:
            cells[by_id[node_id]] = pins[node_id]
            taken.add(pins[node_id])
    displaced = []
    for cls in sorted(auto, key=lambda c: (auto[c], c.__name__)):
        if cls in cells:
            continue
        if auto[cls] in taken:
            displaced.append(cls)
        else:
            cells[cls] = auto[cls]
            taken.add(auto[cls])
    for cls in displaced:
        col, row = auto[cls]
        offset = 1
        while True:
            free = next(
                (
                    cell
                    for cell in ((col, row + offset), (col, row - offset))
                    if cell[1] >= 0 and cell not in taken
                ),
                None,
            )
            if free is not None:
                break
            offset += 1
        cells[cls] = free
        taken.add(free)
    return cells


def _id(cls: type) -> str:
    return kebab(cls.__name__)


def _exec_type(cls: type) -> str | None:
    for label, namespace in _EXEC_NAMESPACES:
        if cls in dict(namespace.items()).values():
            return label
    return None


def _layer_name(cls: type) -> str | None:
    for layer_name, layer_cls in Layer.items():
        if cls in dict(layer_cls.items()).values():
            return layer_name
    return None


def _decorator_label(cls: type, exec_type: str | None) -> str | None:
    if exec_type == "repository":
        entity = Repository.entity(cls)
        return f"@Repository({entity.__name__})" if entity else "@Repository"
    if exec_type:
        return f"@{exec_type.capitalize()}"
    return None


def _source_file(cls: type) -> str | None:
    try:
        path = inspect.getsourcefile(cls)
    except TypeError:
        return None
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(Path.cwd()))
    except ValueError:
        # cls is defined outside the project (e.g. the framework's own
        # Config, or any other class not owned by this project) — showing
        # its install path (often deep inside .venv/site-packages) isn't
        # actionable, so omit the badge instead.
        return None


def _describe(cls: type, decorator: str | None) -> str:
    doc = inspect.getdoc(cls)
    if doc:
        return doc.split("\n\n")[0].replace("\n", " ").strip()
    if decorator:
        return f"{cls.__name__}, registered via {decorator}."
    return f"{cls.__name__}, pre-seeded into the Context."


def _describe_node(cls: type, instance: object, col: int, row: int) -> dict:
    exec_type = _exec_type(cls)
    node_type = "config" if isinstance(instance, Config) else exec_type
    layer = _layer_name(cls)
    decorator = _decorator_label(cls, exec_type)
    return {
        "id": _id(cls),
        "label": cls.__name__,
        "type": node_type,
        "layer": layer,
        "decorator": decorator,
        "file": _source_file(cls),
        "desc": _describe(cls, decorator),
        "col": col,
        "row": row,
        "details": isinstance(instance, DetailsProtocol),
        "chart": isinstance(instance, ChartProtocol),
    }


def _stats(nodes: list[dict], edges: list[dict]) -> dict:
    types: dict[str, int] = {}
    for node in nodes:
        types[node["type"]] = types.get(node["type"], 0) + 1
    return {
        "objects": len(nodes),
        "links": len(edges),
        "types": types,
    }
