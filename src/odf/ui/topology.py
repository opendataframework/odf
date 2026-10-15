"""Builds a JSON-serializable topology graph from a resolved ``Context``.

Pure introspection: reads ``Context.instances`` and ``Context.functions``
(populated after ``Context.open()`` / ``Project.start()``), each object's
``<namespace>.<name>`` key (``Context.key``), and the registration metadata
already tracked by ``Namespace`` subclasses (``Component``, ``Repository``,
``Service``, ``Task``, ``Pipeline``, ``Agent``, ``Function``, ``Layer``).
Nothing here touches the DI container or drives lifecycle — it only describes
what has already been resolved.

A node is a resolved class or function. Its id is its key (``task.loader``)
and its type its execution type (``task``; see ``odf.ui.keys``). ``Config`` is
pre-seeded rather than registered, so it has no key and keeps the id
``config``.
"""

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from opendataframework.component import ChartProtocol, DetailsProtocol
from opendataframework.config import Config
from opendataframework.context import Context, Resolver
from opendataframework.layer import Layer
from opendataframework.repository import Repository
from opendataframework.utils import kebab, normalize

from odf.ui import keys

# ``[ui.topology]`` list key -> the execution type (a node's type) it filters.
_KIND_KEYS = {
    "repositories": "repository",
    "services": "service",
    "tasks": "task",
    "pipelines": "pipeline",
    "agents": "agent",
    "functions": "function",
    "components": "component",
}

# What a node describes: a resolved class, or a resolved function.
type Resolved = type | Callable[..., object]


@dataclass(frozen=True)
class TopologyView:
    """Which components and connections the topology shows.

    The default shows everything. Built from the ``[ui.topology]`` config
    table by ``from_config``.

    Attributes:
        connections: Whether edges between components are drawn.
        show: Per kind (an execution type such as ``"task"``), the normalized
            registered names to show. A kind that is absent from the mapping
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
                ``agents``/``functions``/``components`` as lists of registered
                names, in any
                casing (``"LoadJob"`` or ``"load-job"``).

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

    def is_visible(self, cls: Resolved, node_id: str, instance: object) -> bool:
        """Return whether ``cls`` (node ``node_id``, resolved to ``instance``) is shown."""
        if isinstance(instance, Config):
            return self.config
        names = self.show.get(keys.exec_type(cls))
        return names is None or keys.name_of(node_id) in names

    def unmatched(self, context: Context) -> list[tuple[str, str]]:
        """Return ``(list key, name)`` pairs naming no component of that kind."""
        found: dict[str, set[str]] = {}
        for cls in keys.resolved(context):
            key = keys.key_of(context, cls)
            if key is not None:
                found.setdefault(keys.exec_type(cls) or "", set()).add(keys.name_of(key))
        list_keys = {kind: list_key for list_key, kind in _KIND_KEYS.items()}
        return [
            (list_keys[kind], name)
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
            ``Context.instances`` and ``Context.functions`` are populated).
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
    # A function's "instance" is its bound callable, the one ``Context.get`` returns.
    instances: dict[Resolved, object] = {**context.instances, **context.functions}
    ids = {cls: _id(context, cls) for cls in instances}
    all_set = set(instances)
    node_set = {cls for cls in all_set if view.is_visible(cls, ids[cls], instances[cls])}

    deps = {cls: _visible_dependencies(cls, node_set, all_set) for cls in node_set}
    depths = _compute_depths(deps)
    by_depth: dict[int, list[Resolved]] = {}
    for cls in node_set:
        by_depth.setdefault(depths[cls], []).append(cls)

    auto: dict[Resolved, tuple[int, int]] = {}
    for depth in sorted(by_depth):
        for row, cls in enumerate(sorted(by_depth[depth], key=lambda c: (c.__name__, ids[c]))):
            auto[cls] = (depth, row)
    cells = _resolve_cells(auto, _pinned_cells(layout), ids)

    nodes = []
    for cls in sorted(node_set, key=lambda c: (cells[c], c.__name__, ids[c])):
        col, row = cells[cls]
        node = _describe_node(context, cls, instances[cls], ids[cls], col=col, row=row)
        if node["type"] == "service":
            node["running"] = context.is_running(ids[cls])
        nodes.append(node)

    edges = (
        [
            {"from": ids[dep], "to": ids[cls]}
            for cls in sorted(node_set, key=lambda c: ids[c])
            for dep in sorted(deps[cls], key=lambda c: ids[c])
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


def _visible_dependencies(
    cls: Resolved, visible: set[Resolved], all_set: set[Resolved]
) -> set[Resolved]:
    """Return the nearest visible dependencies of ``cls``, looking through hidden ones.

    A dependency is a constructor parameter or, for a function, a parameter of
    its own; either may ask for a function through ``Annotated[..., func]``.
    """
    found: set[Resolved] = set()
    seen: set[Resolved] = set()
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


def _compute_depths(deps: Mapping[Resolved, set[Resolved]]) -> dict[Resolved, int]:
    """Return each node's longest-path depth given its dependencies among the same nodes."""
    depths: dict[Resolved, int] = {}

    def depth(cls: Resolved, trail: frozenset[Resolved]) -> int:
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
    auto: Mapping[Resolved, tuple[int, int]],
    pins: Mapping[str, tuple[int, int]],
    ids: Mapping[Resolved, str],
) -> dict[Resolved, tuple[int, int]]:
    """Assign every node a unique ``(col, row)`` cell.

    A node with a saved cell keeps it (the first id wins if two share one).
    Any other node keeps its automatic cell unless a saved cell took it, in
    which case it moves to the nearest free row of its column.
    """
    cells: dict[Resolved, tuple[int, int]] = {}
    taken: set[tuple[int, int]] = set()
    by_id = {ids[cls]: cls for cls in auto}
    for node_id in sorted(pins):
        if node_id in by_id and pins[node_id] not in taken:
            cells[by_id[node_id]] = pins[node_id]
            taken.add(pins[node_id])
    displaced = []
    for cls in sorted(auto, key=lambda c: (auto[c], c.__name__, ids[c])):
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


def _id(context: Context, cls: Resolved) -> str:
    """Return a node's id: its key, or the kebab-case class name if it has none."""
    return keys.key_of(context, cls) or kebab(cls.__name__)


def _layer_name(cls: Resolved) -> str | None:
    for layer_name, layer_cls in Layer.items():
        if cls in dict(layer_cls.items()).values():
            return layer_name
    return None


def _decorator_label(cls: Resolved, exec_type: str | None) -> str | None:
    if exec_type == "repository":
        entity = Repository.entity(cls)
        return f"@Repository({entity.__name__})" if entity else "@Repository"
    if exec_type:
        return f"@{exec_type.capitalize()}"
    return None


def _source_file(cls: Resolved) -> str | None:
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


def _describe(cls: Resolved, decorator: str | None) -> str:
    doc = inspect.getdoc(cls)
    if doc:
        return doc.split("\n\n")[0].replace("\n", " ").strip()
    if decorator:
        return f"{cls.__name__}, registered via {decorator}."
    return f"{cls.__name__}, pre-seeded into the Context."


def _describe_node(
    context: Context, cls: Resolved, instance: object, node_id: str, col: int, row: int
) -> dict:
    exec_type = keys.exec_type(cls)
    node_type = "config" if isinstance(instance, Config) else exec_type
    layer = _layer_name(cls)
    decorator = _decorator_label(cls, exec_type)
    key = keys.key_of(context, cls)
    return {
        "id": node_id,
        "name": keys.name_of(key) if key else None,
        "href": keys.href(context, cls),
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
