"""Persists topology grid-cell/icon/color overrides to a JSON sidecar file.

Backs the "drag a node to a new cell", "change a node's icon", "change a
node's color", and "add cells to the grid" interactions in the UI
(see ``app.js``'s drag handling, icon/color pickers, and grid-controls
buttons) so layout customizations survive a page refresh. Scoped to whatever
``Path`` a ``UiServer`` is constructed with — not process-global state, so
multiple ``Project`` instances never share a file unless explicitly
configured to point at the same one (see ``Project.start``'s ``layout-file``
config key).

This module treats the file as an opaque JSON object — it neither knows nor
validates the per-key shape described below; that's entirely the frontend's
concern. The one exception is ``for_view``, which reads the reserved
``"_views"`` key: with ``[ui.views]`` declared, each view's own places, as
``{"<view>": {"<node id>": {"col": int, "row": int}, "_grid": {...}}}``.
"""

import json
from collections.abc import Mapping
from pathlib import Path


def load(path: Path) -> dict[str, dict[str, int | str]]:
    """Return saved node layout overrides, or ``{}`` if the file is absent/invalid.

    Args:
        path: Location of the layout JSON file.

    Returns:
        Mapping of node id to
        ``{"col": int, "row": int, "icon": str, "flatIcon": str, "color": str}``,
        where ``"icon"`` (the isometric grid's icon), ``"flatIcon"`` (the flat
        grid's glyph) and ``"color"`` are optional (a node with no such
        override omits the corresponding key). The reserved key ``"_grid"``
        (never a valid node id — those are ``<namespace>.<name>`` keys, or
        ``config``) maps
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


def for_view(saved: Mapping[str, object], name: str) -> dict[str, object]:
    """Return the layout as view ``name`` sees it.

    A view keeps its own places under ``saved["_views"][name]``: a node's
    ``col``/``row`` there override its top-level ones, and the view's
    ``_grid`` overrides the top-level ``_grid``. Whatever a view has no place
    for (a node it was never moved in, icons, colors, layer colors) comes
    from the top level, so a new view starts from the layout already saved.

    Args:
        saved: The layout file's contents, as ``load`` returns them.
        name: The view's name.

    Returns:
        A new mapping shaped like ``saved``, without ``_views``.
    """
    views = saved.get("_views")
    own = views.get(name) if isinstance(views, Mapping) else None
    merged = {key: value for key, value in saved.items() if key != "_views"}
    if not isinstance(own, Mapping):
        return merged
    for key, value in own.items():
        top = merged.get(key)
        if isinstance(value, Mapping) and isinstance(top, Mapping):
            merged[key] = {**top, **value}
        else:
            merged[key] = value
    return merged


def save(path: Path, positions: dict[str, dict[str, int | str]]) -> None:
    """Write node layout overrides, replacing any existing file.

    Args:
        path: Location of the layout JSON file. Parent directories are
            created as needed.
        positions: Mapping of node id to
            ``{"col": int, "row": int, "icon": str, "flatIcon": str, "color": str}``,
            where ``"icon"``, ``"flatIcon"`` and ``"color"`` are optional.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(positions, indent=2, sort_keys=True))
