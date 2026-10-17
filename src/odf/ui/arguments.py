"""Describes and validates the arguments of whatever is called with them.

An ``@Agent`` is invoked and an ``@Function`` is called, both with arguments,
unlike a task's ``execute()``. ``ENTRIES`` names, per execution type, the
callable whose signature gives those arguments and the verb the call goes by:
the last segment of its HTTP route (``/api/agents/{name}/invoke``) and of its
MCP tool (``<key>.invoke``), and the label of its action in the UI. Every
other helper here takes any resolved object, so a new kind that takes
arguments is one more entry.

Pure introspection, mirroring ``ui/data.py``'s shape: no HTTP or MCP concerns
live here, only functions that ``ui/server.py`` and ``mcp/server.py`` wire to
a route or a tool. The object itself is always called through
``Context.call()``, so its call is logged like any other.
"""

import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from opendataframework.context import Context
from pydantic import BaseModel, create_model

from odf.ui import keys

# ``Context.call()`` passes arguments by keyword only, so these can't be given.
_UNSUPPORTED_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)


@dataclass(frozen=True)
class Entry:
    """How one execution type is called with arguments.

    Attributes:
        verb: What a call is named: the route, tool and action name.
        target: Returns the callable whose annotations type the arguments,
            given the resolved class or function.
    """

    verb: str
    target: Callable[[Any], Callable[..., object]]


# Execution type -> how it is called. Tasks and pipelines are absent: their
# ``execute()`` takes no arguments through ``Context.execute()``.
ENTRIES: dict[str, Entry] = {
    "agent": Entry(verb="invoke", target=lambda cls: cls.invoke),
    "function": Entry(verb="call", target=lambda func: func),
}


def entry(obj: type | Callable[..., object]) -> Entry | None:
    """Return how ``obj`` is called with arguments, or ``None`` if it isn't."""
    return ENTRIES.get(keys.exec_type(obj))


def verb(obj: type | Callable[..., object]) -> str | None:
    """Return the verb ``obj`` is called with (``"invoke"``, ``"call"``), if any."""
    found = entry(obj)
    return found.verb if found else None


def callables(context: Context, kind: str) -> list[type | Callable[..., object]]:
    """Return every resolved object of execution type ``kind``, sorted by name.

    Args:
        context: A ``Context`` that has already been opened.
        kind: An execution type in ``ENTRIES``, such as ``"agent"``.
    """
    return sorted(
        (obj for obj in keys.resolved(context) if keys.exec_type(obj) == kind),
        key=lambda obj: obj.__name__,
    )


def parameters(context: Context, obj: type | Callable[..., object]) -> list[inspect.Parameter]:
    """Return the parameters a caller can supply to ``obj``, in signature order.

    That is an agent's ``invoke()`` parameters, or a function's own minus the
    ones the ``Context`` injects. String annotations (from ``from __future__
    import annotations``) are resolved to the types they name.
    Positional-only, ``*args`` and ``**kwargs`` parameters are left out, since
    ``Context.call()`` can't pass them.

    Args:
        context: A ``Context`` that has already been opened.
        obj: A resolved object that takes arguments (see ``entry``).
    """
    try:
        hints = typing.get_type_hints(entry(obj).target(obj))
    except Exception:
        hints = {}
    return [
        parameter.replace(annotation=hints.get(name, parameter.annotation))
        for name, parameter in context.parameters(obj).items()
        if parameter.kind not in _UNSUPPORTED_KINDS
    ]


def model(context: Context, obj: type | Callable[..., object]) -> type[BaseModel]:
    """Build a pydantic model of ``obj``'s arguments.

    Its JSON schema describes the form the UI shows, and validating a request
    body against it coerces form values to the annotated types. An
    unannotated parameter accepts any value.

    Args:
        context: A ``Context`` that has already been opened.
        obj: A resolved object that takes arguments (see ``entry``).
    """
    fields: dict[str, Any] = {}
    for parameter in parameters(context, obj):
        annotation = (
            Any if parameter.annotation is inspect.Parameter.empty else parameter.annotation
        )
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[parameter.name] = (annotation, default)
    return create_model(obj.__name__, **fields)


def describe(obj: type | Callable[..., object]) -> str:
    """Return the first paragraph of ``obj``'s docstring, or a fallback."""
    doc = inspect.getdoc(obj)
    if doc:
        return doc.split("\n\n")[0].replace("\n", " ").strip()
    return f"{verb(obj).capitalize()} the {obj.__name__} {keys.exec_type(obj)}."
