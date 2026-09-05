"""Persists topology grid-cell/icon/color overrides to a JSON sidecar file.

Backs the "drag a node to a new cell", "change a node's icon", "change a
node's color", and "add cells to the grid" interactions in the UI
(see ``index.html``'s drag handling, icon/color pickers, and grid-controls
buttons) so layout customizations survive a page refresh. Scoped to whatever
``Path`` a ``UiServer`` is constructed with — not process-global state, so
multiple ``Project`` instances never share a file unless explicitly
configured to point at the same one (see ``Project.start``'s ``layout-file``
config key).

This module treats the file as an opaque JSON object — it neither knows nor
validates the per-key shape described below; that's entirely the frontend's
concern.
"""

import json
from pathlib import Path


def load(path: Path) -> dict[str, dict[str, int | str]]:
    """Return saved node layout overrides, or ``{}`` if the file is absent/invalid.

    Args:
        path: Location of the layout JSON file.

    Returns:
        Mapping of node id to ``{"col": int, "row": int, "icon": str, "color": str}``,
        where ``"icon"`` and ``"color"`` are optional (a node with no such
        override omits the corresponding key). The reserved key ``"_grid"``
        (never a valid node id — those are always kebab-case class names) maps
        instead to ``{"nw": int, "ne": int, "se": int, "sw": int}``, the number
        of user-added empty cells extending each edge of the isometric diamond
        past the auto-fit bounds derived from node positions.
    """
    try:
        raw = path.read_text()
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save(path: Path, positions: dict[str, dict[str, int | str]]) -> None:
    """Write node layout overrides, replacing any existing file.

    Args:
        path: Location of the layout JSON file. Parent directories are
            created as needed.
        positions: Mapping of node id to
            ``{"col": int, "row": int, "icon": str, "color": str}``, where
            ``"icon"`` and ``"color"`` are optional.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(positions, indent=2, sort_keys=True))
