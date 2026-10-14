"""Maps resolved objects to their keys, execution types and HTTP paths.

``opendataframework`` addresses every registered class or function by a key,
``<namespace>.<name>`` (``task.loader``, ``agent.librarian``), unique by
construction. The topology uses the key as a node's id and passes it to every
``Context`` call.

The namespace in a key is the one the object was gathered from, which is its
execution type in a default ``Context`` but not in one scoped to a custom
namespace (``Context(namespaces={NS})`` keys a task ``n-s.loader``). So a
node's type, and the route collection it is served under, come from its
execution type instead: a ``@Task`` registered as ``loader`` is served under
``/api/tasks/loader`` whatever its key's namespace.

Pure introspection, like ``ui/data.py``: no HTTP concerns live here.
"""

from collections.abc import Callable

from opendataframework.agent import Agent
from opendataframework.component import Component
from opendataframework.context import Context
from opendataframework.namespace import Namespace, parse
from opendataframework.pipeline import Pipeline
from opendataframework.repository import Repository
from opendataframework.service import Service
from opendataframework.task import Task
from opendataframework.utils import normalize

# Order matters only in that a class is expected to be registered under
# exactly one of these — first match wins if that assumption is ever broken.
EXEC_NAMESPACES: list[tuple[str, type[Namespace]]] = [
    ("repository", Repository),
    ("service", Service),
    ("task", Task),
    ("pipeline", Pipeline),
    ("agent", Agent),
    ("component", Component),
]

# Execution type -> its route collection under ``/api``.
COLLECTIONS: dict[str, str] = {
    "component": "components",
    "repository": "repositories",
    "service": "services",
    "task": "tasks",
    "pipeline": "pipelines",
    "agent": "agents",
}


def exec_type(obj: type | Callable[..., object]) -> str | None:
    """Return the execution type ``obj`` is registered under, such as ``"task"``."""
    for label, namespace in EXEC_NAMESPACES:
        if obj in dict(namespace.items()).values():
            return label
    return None


def key_of(context: Context, obj: type | Callable[..., object]) -> str | None:
    """Return ``obj``'s key, or ``None`` if it has none (such as the pre-seeded ``Config``)."""
    try:
        return context.key(obj)
    except KeyError:
        return None


def name_of(key: str) -> str:
    """Return a key's name part: ``"task.load-job"`` → ``"load-job"``."""
    return key.partition(".")[2]


def href(context: Context, obj: type | Callable[..., object]) -> str | None:
    """Return the base path ``obj`` is served under, or ``None`` if it has no routes."""
    key = key_of(context, obj)
    collection = COLLECTIONS.get(exec_type(obj))
    return f"/api/{collection}/{name_of(key)}" if key and collection else None


def lookup(context: Context, key: str) -> type | None:
    """Return the resolved class addressed by ``key``, in any casing, if any.

    Raises:
        ValueError: If ``key`` is not ``<namespace>.<name>``.
    """
    wanted = parse(key)
    return next((cls for cls in context.instances if key_of(context, cls) == wanted), None)


def resolve(context: Context, kind: str, name: str) -> type | None:
    """Return the resolved class of execution type ``kind`` registered as ``name``, if any.

    Args:
        context: A ``Context`` that has already been opened.
        kind: An execution type, such as ``"task"``.
        name: The registered name, in any casing.
    """
    wanted = normalize(name)
    for cls in context.instances:
        key = key_of(context, cls)
        if key is not None and name_of(key) == wanted and exec_type(cls) == kind:
            return cls
    return None


def resolve_collection(context: Context, collection: str, name: str) -> type | None:
    """Return the resolved class served at ``/api/{collection}/{name}``, if any."""
    kind = next((kind for kind, path in COLLECTIONS.items() if path == collection), None)
    return resolve(context, kind, name) if kind is not None else None
