"""Resolves a UI theme name to its file-set directory.

A theme is a self-contained ``index.html``/``favicon.svg`` pair under
``static/themes/<name>/`` — the whole UI (HTML/CSS/JS, including its own
copy of the light/dark color-mode toggle) in one file, so themes never
share templates/styles and can't bleed into each other. Orthogonal to that
toggle: a "theme" here means which visual/layout file-set is served, not
light vs. dark.
"""

from pathlib import Path

_THEMES_DIR = Path(__file__).parent / "static" / "themes"
_REQUIRED_FILES = ("index.html", "favicon.svg")


def list_themes() -> list[str]:
    """Return the names of every available theme, sorted.

    A directory under ``static/themes/`` counts as a theme once it has an
    ``index.html`` — ``theme_dir`` checks for the rest of the required
    files at resolve time, so an incomplete theme still shows up here but
    fails clearly when selected.
    """
    if not _THEMES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in _THEMES_DIR.iterdir() if p.is_dir() and (p / "index.html").is_file()
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
