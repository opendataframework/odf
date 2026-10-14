"""Describes and validates the arguments of a resolved ``Agent``'s ``invoke()``.

Pure introspection, mirroring ``ui/data.py``'s shape: no HTTP or MCP concerns
live here, only functions that ``ui/server.py`` and ``mcp/server.py`` wire to
a route or a tool. The agent itself is always called through
``Context.call()``, so its call is logged like any other.
"""

import inspect
import typing
from typing import Any

from opendataframework.agent import Agent
from opendataframework.context import Context
from opendataframework.utils import kebab
from pydantic import BaseModel, create_model

# ``Context.call()`` passes arguments by keyword only, so these can't be given.
_UNSUPPORTED_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)


def find_agent(context: Context, agent_id: str) -> type | None:
    """Look up a resolved agent by its topology id (kebab-case class name).

    Args:
        context: A ``Context`` that has already been opened.
        agent_id: The kebab-case id, as used by ``ui/topology.py`` node ids.

    Returns:
        The agent class, or ``None`` if no resolved agent matches.
    """
    agents = set(dict(Agent.items()).values())
    for cls in context.instances:
        if cls in agents and kebab(cls.__name__) == agent_id:
            return cls
    return None


def agents(context: Context) -> list[type]:
    """Return every resolved agent class, sorted by class name."""
    registered = set(dict(Agent.items()).values())
    return sorted((cls for cls in context.instances if cls in registered), key=lambda c: c.__name__)


def invoke_parameters(context: Context, cls: type) -> list[inspect.Parameter]:
    """Return the ``invoke()`` parameters a caller can supply, in signature order.

    String annotations (from ``from __future__ import annotations``) are
    resolved to the types they name. Positional-only, ``*args`` and
    ``**kwargs`` parameters are left out, since ``Context.call()`` can't pass
    them.

    Args:
        context: A ``Context`` that has already been opened.
        cls: A resolved agent class.
    """
    try:
        hints = typing.get_type_hints(cls.invoke)
    except Exception:
        hints = {}
    return [
        parameter.replace(annotation=hints.get(name, parameter.annotation))
        for name, parameter in context.parameters(cls).items()
        if parameter.kind not in _UNSUPPORTED_KINDS
    ]


def invoke_model(context: Context, cls: type) -> type[BaseModel]:
    """Build a pydantic model of ``invoke()``'s arguments.

    Its JSON schema describes the form the UI shows, and validating a request
    body against it coerces form values to the annotated types. An
    unannotated parameter accepts any value.

    Args:
        context: A ``Context`` that has already been opened.
        cls: A resolved agent class.
    """
    fields: dict[str, Any] = {}
    for parameter in invoke_parameters(context, cls):
        annotation = (
            Any if parameter.annotation is inspect.Parameter.empty else parameter.annotation
        )
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[parameter.name] = (annotation, default)
    return create_model(cls.__name__, **fields)


def describe(cls: type) -> str:
    """Return the first paragraph of ``cls``'s docstring, or a fallback."""
    doc = inspect.getdoc(cls)
    if doc:
        return doc.split("\n\n")[0].replace("\n", " ").strip()
    return f"Invoke the {cls.__name__} agent."
