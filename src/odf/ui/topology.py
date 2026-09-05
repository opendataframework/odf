"""Builds a JSON-serializable topology graph from a resolved ``Context``.

Pure introspection: reads ``Context.instances`` (populated after
``Context.open()`` / ``Project.start()``) and the class-level registration
metadata already tracked by ``Namespace`` subclasses (``Component``,
``Repository``, ``Service``, ``Task``, ``Pipeline``, ``Layer``). Nothing here
touches the DI container or drives lifecycle — it only describes what has
already been resolved.
"""

import inspect
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
from opendataframework.utils import kebab

# Order matters only in that a class is expected to be registered under
# exactly one of these — first match wins if that assumption is ever broken.
_EXEC_NAMESPACES: list[tuple[str, type[Namespace]]] = [
    ("repository", Repository),
    ("service", Service),
    ("task", Task),
    ("pipeline", Pipeline),
    ("component", Component),
]


def build_topology(context: Context, project: str = "ODF Project") -> dict:
    """Build a JSON-serializable topology graph for the given ``Context``.

    Args:
        context: A ``Context`` that has already been opened (i.e.
            ``Context.instances`` is populated).
        project: Display name for the project, shown in the UI header.

    Returns:
        A dict with ``project``, ``nodes``, ``edges``, and ``stats`` keys,
        suitable for ``json`` serialization.
    """
    instances = context.instances
    node_set = set(instances)

    depths = _compute_depths(node_set)
    by_depth: dict[int, list[type]] = {}
    for cls in node_set:
        by_depth.setdefault(depths[cls], []).append(cls)

    nodes = []
    for depth in sorted(by_depth):
        row_classes = sorted(by_depth[depth], key=lambda c: c.__name__)
        for row, cls in enumerate(row_classes):
            node = _describe_node(cls, instances[cls], col=depth, row=row)
            if node["type"] == "service":
                node["running"] = context.is_running(cls.__name__)
            nodes.append(node)

    edges = [
        {"from": _id(dep), "to": _id(cls)}
        for cls in node_set
        for dep in Resolver.dependencies(cls).values()
        if dep in node_set and dep is not cls
    ]

    return {
        "project": project,
        "nodes": nodes,
        "edges": edges,
        "stats": _stats(nodes, edges),
    }


def _compute_depths(node_set: set[type]) -> dict[type, int]:
    """Return each class's longest-path depth among dependencies also in ``node_set``."""
    depths: dict[type, int] = {}

    def depth(cls: type, trail: frozenset[type]) -> int:
        if cls in depths:
            return depths[cls]
        if cls in trail:
            return 0  # circular deps can't happen post-resolve; guard defensively anyway
        deps = [d for d in Resolver.dependencies(cls).values() if d in node_set and d is not cls]
        result = 0 if not deps else 1 + max(depth(d, trail | {cls}) for d in deps)
        depths[cls] = result
        return result

    for cls in node_set:
        depth(cls, frozenset())
    return depths


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
