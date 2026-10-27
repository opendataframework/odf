"""Resolves a UI theme name, or a path to a project's own theme, to its file-set directory.

The UI's markup (``static/index.html``) and behavior (``static/app.js``)
are shared by every theme. A theme is a ``theme.css``/``favicon.svg`` pair
under ``static/themes/<name>/`` — a complete stylesheet of its own, so
themes never share styles and can't bleed into each other — plus an
optional ``theme.js`` for canvas drawing a stylesheet can't express. A
project's own theme is a directory with the same files anywhere on disk,
selected by its path instead of a name.
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


def _is_path(name: str) -> bool:
    """Whether ``name`` reads as a path rather than a built-in theme's name."""
    return "/" in name or "\\" in name or name.startswith((".", "~"))


def theme_dir(name: str) -> Path:
    """Resolve a theme name, or a path to a theme directory, to its directory.

    Args:
        name: Theme name, matched against ``list_themes()`` first. Anything
            else containing a path separator or starting with ``.``/``~``
            (``"./my-theme"``, ``"~/themes/dark"``) is a path to a theme
            directory of the project's own, relative to the current working
            directory, like ``[ui] favicon``/``[ui] logo``.

    Returns:
        The theme's directory, guaranteed to contain every file in
        ``_REQUIRED_FILES``.

    Raises:
        ValueError: If ``name`` is neither an available theme nor a path,
            if it's a path to no directory, or if its directory is missing
            a required file.
    """
    available = list_themes()
    if name in available:
        path = _THEMES_DIR / name
    elif _is_path(name):
        path = Path(name).expanduser()
        if not path.is_dir():
            raise ValueError(f"UI theme directory {name!r} does not exist")
    else:
        raise ValueError(
            f"Unknown UI theme {name!r} — available themes: {', '.join(available)}, "
            'or a path to a theme directory such as "./my-theme"'
        )
    for filename in _REQUIRED_FILES:
        if not (path / filename).is_file():
            raise ValueError(f"UI theme {name!r} is missing required file {filename!r}")
    return path
