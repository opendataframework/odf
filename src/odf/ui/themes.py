"""Resolves a UI theme name to its file-set directory.

The UI's markup (``static/index.html``) and behavior (``static/app.js``)
are shared by every theme. A theme is a ``theme.css``/``favicon.svg`` pair
under ``static/themes/<name>/`` — a complete stylesheet of its own, so
themes never share styles and can't bleed into each other — plus an
optional ``theme.js`` for canvas drawing a stylesheet can't express.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
_THEMES_DIR = STATIC_DIR / "themes"
_REQUIRED_FILES = ("theme.css", "favicon.svg")


def list_themes() -> list[str]:
    """Return the names of every available theme, sorted.

    A directory under ``static/themes/`` counts as a theme once it has a
    ``theme.css`` — ``theme_dir`` checks for the rest of the required
    files at resolve time, so an incomplete theme still shows up here but
    fails clearly when selected.
    """
    if not _THEMES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in _THEMES_DIR.iterdir() if p.is_dir() and (p / "theme.css").is_file()
    )


def theme_dir(name: str) -> Path:
    """Resolve a theme name to its directory.

    Args:
        name: Theme name, matched against ``list_themes()``.

    Returns:
        The theme's directory, guaranteed to contain every file in
        ``_REQUIRED_FILES``.

    Raises:
        ValueError: If ``name`` isn't an available theme, or its directory
            is missing a required file.
    """
    available = list_themes()
    if name not in available:
        raise ValueError(f"Unknown UI theme {name!r} — available themes: {', '.join(available)}")
    path = _THEMES_DIR / name
    for filename in _REQUIRED_FILES:
        if not (path / filename).is_file():
            raise ValueError(f"UI theme {name!r} is missing required file {filename!r}")
    return path
