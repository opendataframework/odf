"""Named UI views from the ``[ui.views.<name>]`` config tables.

A view is one way of looking at the project, picked in the UI's header: a
manager's view showing the bakery's data and the actions they take, a
system view showing all of its wiring. Each is a table, and each part of the
UI it shapes is a table of its own under it, so a view can grow without
moving what it already holds::

    [ui.views.manager]
    label = "Bakery"        # the switcher's text; defaults to the name
    default = true          # else the first view declared is the default

    [ui.views.manager.topology]   # the keys [ui.topology] takes
    components = []

Views only change what the UI shows. MCP and chat still reach every
component, whatever view is open.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from odf.ui.topology import TopologyView

_VIEW_KEYS = {"label", "default", "topology"}


@dataclass(frozen=True)
class View:
    """One named view of the UI.

    Attributes:
        name: The view's name, its table's key (``manager`` for
            ``[ui.views.manager]``), and the ``?view=`` that opens it.
        label: The switcher's text for it.
        topology: What the topology shows in it.
    """

    name: str
    label: str
    topology: TopologyView = field(default_factory=TopologyView)


def from_config(ui_cfg: Mapping) -> tuple[dict[str, View], str | None]:
    """Read the views declared in the ``[ui]`` table.

    Args:
        ui_cfg: The parsed ``[ui]`` table.

    Returns:
        The views by name, in the order declared, and the default view's
        name: the one with ``default = true``, else the first. ``({}, None)``
        when no view is declared (an empty ``[ui.views]`` included).

    Raises:
        ValueError: On a view that isn't a table, an unknown key, a ``label``
            that isn't text, a ``default`` that isn't true or false, more than
            one default, a ``topology`` table that isn't valid (see
            ``TopologyView.from_config``), or ``[ui.topology]`` set alongside
            ``[ui.views]``.
    """
    tables = ui_cfg.get("views", {})
    if not isinstance(tables, Mapping):
        raise ValueError(f"[ui.views] must be a table of views, got {tables!r}")
    if not tables:
        return {}, None
    if "topology" in ui_cfg:
        raise ValueError(
            "[ui.topology] and [ui.views] are both set: move the topology settings "
            "into each view's own [ui.views.<name>.topology] table."
        )
    views: dict[str, View] = {}
    defaults: list[str] = []
    for name, table in tables.items():
        where = f"[ui.views.{name}]"
        if not isinstance(table, Mapping):
            raise ValueError(f"{where} must be a table, got {table!r}")
        unknown = set(table) - _VIEW_KEYS
        if unknown:
            raise ValueError(f"Unknown {where} key(s): {', '.join(sorted(unknown))}")
        label = table.get("label", name)
        if not isinstance(label, str):
            raise ValueError(f"{where} label must be text, got {label!r}")
        default = table.get("default", False)
        if not isinstance(default, bool):
            raise ValueError(f"{where} default must be true or false, got {default!r}")
        if default:
            defaults.append(name)
        topology = table.get("topology", {})
        if not isinstance(topology, Mapping):
            raise ValueError(f"[ui.views.{name}.topology] must be a table, got {topology!r}")
        views[name] = View(
            name=name,
            label=label,
            topology=TopologyView.from_config(topology, f"[ui.views.{name}.topology]"),
        )
    if len(defaults) > 1:
        raise ValueError(f"More than one view has default = true: {', '.join(defaults)}")
    return views, defaults[0] if defaults else next(iter(views))
