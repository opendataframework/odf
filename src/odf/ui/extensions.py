"""Process-global registries for extending the UI's icon and color options.

Mirrors the side-effecting registration pattern already used by
``Namespace``/``Layer``/``Component`` — a framework-extension package calls
``register_icon_script``/``register_color`` at import time, and every
``Server`` in the process picks up whatever is currently registered when its
``UiServer`` starts (see ``Server.start``). Project-local config (``[ui]``
in ``config.toml``) is merged in on top at that point — this module only
holds the package-registered half.

Icons are procedural canvas vector art (see ``index.html``'s ``ICONS``
registry and shared ``drawBox``/``isoBox``/``isoDisc`` primitives), so a
"custom icon" is a plain ``.js`` file defining draw function(s) with the same
``(sx, sy, accent, lit)`` signature as the built-ins, registered into the
frontend's ``ICONS`` object via a small ``ODF.registerIcon`` hook rather than
being spliced in at build time. Colors need no function — just a hex string —
so they're registered directly as data.
"""

from pathlib import Path

from opendataframework.utils import normalize

_ICON_SCRIPTS: list[Path] = []
_COLORS: dict[str, str] = {}


def register_icon_script(path: str | Path) -> None:
    """Register a JS file to be served and loaded into the UI.

    The file must define one or more draw functions matching the built-in
    signature ``(sx, sy, accent, lit)`` and register each via the frontend's
    ``ODF.registerIcon(key, drawFn, meta)`` hook.

    Args:
        path: Filesystem path to the ``.js`` file.
    """
    _ICON_SCRIPTS.append(Path(path))


def register_color(name: str, hex: str) -> None:
    """Register a named color swatch for the UI's color pickers.

    Args:
        name: Display name for the swatch, normalised to kebab-case.
        hex: Hex color string, e.g. ``"#b7410e"``.
    """
    _COLORS[normalize(name)] = hex


def icon_scripts() -> list[Path]:
    """Return all currently registered icon script paths."""
    return list(_ICON_SCRIPTS)


def colors() -> dict[str, str]:
    """Return all currently registered colors, name → hex."""
    return dict(_COLORS)
