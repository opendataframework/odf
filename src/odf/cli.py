"""Command-line entry point (``odf``), installed as a console script."""

import importlib
import sys
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel

from odf import scaffold
from odf.server import Server

app = typer.Typer(add_completion=False, no_args_is_help=True)

_BRAND = "#00FA92"
_BRAND_LIGHT = "#6BFFC0"
_BRAND_DARK = "#00C273"
_ACCENT = "#B36AE2"
_ACCENT_LIGHT = "#D6AEF2"
_ACCENT_DARK = "#8B4FC0"
_FRAME = "#2b2b2b"


class Template(StrEnum):
    """Scaffold templates offered by ``odf init --template``."""

    default = "default"
    data_analytics = "data-analytics"
    data_science = "data-science"
    data_engineering = "data-engineering"
    research = "research"


def _version() -> str:
    """Return the installed ``odf`` package version, or ``"0.0.0"`` if unresolvable."""
    try:
        return version("odf")
    except PackageNotFoundError:
        return "0.0.0"


def _logo_flat() -> str:
    """Older, flat-color rendering — unused, kept for reference."""
    text = "\n".join(
        [
            "",
            "█████████████",
            "█████████████",
            "█████████████",
            "█████████████ Open",
            "█████████████ Data",
            "█████████████ Framework",
            "",
        ]
    )
    purple = {16, 17, 18, 19, 21, 22, 23, 24, 30, 31, 32, 33, 35, 36, 37, 38}
    gray = set(range(57, 61)) | set(range(76, 80)) | set(range(95, 104))

    colorized = []
    for i, ch in enumerate(text):
        if i in purple:
            colorized.append(f"[{_ACCENT}]{ch}[/{_ACCENT}]")
        elif i in gray:
            colorized.append(f"[bright_black]{ch}[/bright_black]")
        else:
            colorized.append(f"[{_BRAND}]{ch}[/{_BRAND}]")

    return "".join(colorized)


def _logo() -> str:
    """Pixel-styled rendering matching docs/images/logo.svg's frame + bevels.

    Column layout of the 13-unit-wide field (matching the SVG's 6px-per-unit
    grid: left bevel, square, gap, square, plain margin, right bevel) —
    the side bevels run the full inner height, not just alongside the
    squares, and the plain margin keeps the right bevel from crowding the
    second square.
    """

    def c(s: str, color: str) -> str:
        """Wrap ``s`` in a rich foreground-color tag."""
        return f"[{color}]{s}[/{color}]"

    def cell(top_color: str, bottom_color: str, width: int = 1) -> str:
        """Pack two SVG unit-rows into one terminal row via a half-block glyph."""
        # "▀" paints its own foreground in the cell's top half and the
        # background color in the bottom half, packing two SVG unit-rows
        # into one terminal row instead of a full block per unit.
        return f"[{top_color} on {bottom_color}]{'▀' * width}[/{top_color} on {bottom_color}]"

    block = "█"
    # u0 (frame, full width) + u1 (light-green bevel, inner 13 only) packed
    # into one row — the outer frame columns stay solid frame, not green.
    top_edge = c(block, _FRAME) + cell(_FRAME, _BRAND_LIGHT, 13) + c(block, _FRAME)
    # u13 (dark-green bevel, inner 13 only) + u14 (frame, full width).
    bottom_edge = c(block, _FRAME) + cell(_BRAND_DARK, _FRAME, 13) + c(block, _FRAME)

    def side(inner: str) -> str:
        """Wrap a row's inner cells with the frame and bevel side columns."""
        return (
            c(block, _FRAME)
            + c(block, _BRAND_LIGHT)
            + inner
            + c(block, _BRAND_DARK)
            + c(block, _FRAME)
        )

    gap_row = side(c(block * 11, _BRAND))

    # The SVG's 4x4-unit bevel grid per square (u0..u3 top-to-bottom):
    #   L L L L
    #   L P P D
    #   L P P D
    #   L D D D
    # Packed two SVG rows per terminal row so the plain-purple center and
    # the light/dark corners both survive instead of being sampled away.
    L, P, D = _ACCENT_LIGHT, _ACCENT, _ACCENT_DARK
    square_row_a = [(L, L), (L, P), (L, P), (L, D)]  # u0 over u1
    square_row_b = [(L, L), (P, D), (P, D), (D, D)]  # u2 over u3

    def square_row(cells: list[tuple[str, str]]) -> str:
        """Render one packed row of the two bevel-shaded logo squares."""
        square = "".join(cell(top, bottom) for top, bottom in cells)
        return side(square + c(block, _BRAND) + square + c(block * 2, _BRAND))

    def text_row(suffix: str) -> str:
        """Render one plain logo row followed by a line of caption text."""
        return side(c(block * 11, _BRAND)) + suffix

    lines = [
        "",
        top_edge,
        gap_row,
        square_row(square_row_a),
        square_row(square_row_b),
        text_row(" Open"),
        text_row(" Data"),
        text_row(" Framework"),
        bottom_edge,
        "",
    ]
    return "\n".join(lines)


def _banner() -> Panel:
    """Build the rich ``Panel`` shown on CLI startup, wrapping ``_logo()``."""
    body = f"{_logo()}[dim]Lightweight dependency-injection framework for data applications.[/dim]"
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=_BRAND,
        padding=(0, 3),
        expand=False,
        title=f"[bold {_BRAND}]odf[/bold {_BRAND}] [dim]v{_version()}[/dim]",
        title_align="left",
    )


@app.callback()
def main() -> None:
    """ODF — config-driven Python framework for building data applications."""


@app.command()
def run(
    config: str = typer.Argument(
        "config.toml",
        help="Path to a config file or a directory of config files.",
    ),
    app_module: str = typer.Option(
        "app",
        "--app",
        help="Import name of the package that registers components (@Component, @Repository, ...).",
    ),
    ui: bool = typer.Option(True, help="Start the UI."),
    ui_host: str = typer.Option("127.0.0.1", help="Interface for the UI to bind to."),
    ui_port: int = typer.Option(4747, help="Port for the UI to bind to."),
    mcp: bool = typer.Option(False, help="Start the MCP server."),
    mcp_host: str = typer.Option("127.0.0.1", help="Interface for the MCP server to bind to."),
    mcp_port: int = typer.Option(4748, help="Port for the MCP server to bind to."),
    chat: bool = typer.Option(False, help="Add a chat window to the UI (requires --ui)."),
) -> None:
    """Start a project: import its app package, load its config, and run until Ctrl+C.

    Run from the project's root directory (the one containing ``config.toml``
    and the ``app`` package), the same layout as ``demo/``.
    """
    console = Console()
    console.print(_banner())

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        importlib.import_module(app_module)
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            f"Could not import {app_module!r} from {cwd} — pass --app to point at the "
            "package that registers your components."
        ) from exc

    server = Server.from_config(config)
    server.start(
        ui=ui,
        ui_host=ui_host,
        ui_port=ui_port,
        mcp=mcp,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
        chat=chat,
        app_module=None,
    )

    lines = []
    if server.ui_url:
        lines.append(f"[{_BRAND}]●[/{_BRAND}] UI running at [bold]{server.ui_url}[/bold]")
    if server.mcp_url:
        lines.append(
            f"[{_ACCENT}]●[/{_ACCENT}] MCP server running at [bold]{server.mcp_url}[/bold]"
        )
    lines.append("[dim]Press Ctrl+C to stop[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            box=box.ROUNDED,
            border_style=_BRAND,
            padding=(0, 2),
            expand=False,
            title="[bold]odf run[/bold]",
            title_align="left",
        )
    )

    server.wait()


@app.command()
def init(
    name: str | None = typer.Argument(
        None, help="Directory to create the project in. Defaults to the current directory."
    ),
    template: Template = typer.Option(
        Template.default, "--template", "-t", help="Project template to scaffold."
    ),
) -> None:
    """Scaffold a new ODF project: a config.toml and an importable app package.

    Creates NAME as a new directory (or scaffolds into the current directory
    if NAME is omitted). The target directory must not already contain files.
    """
    console = Console()
    console.print(_banner())

    target = scaffold.resolve_target(name)
    try:
        scaffold.ensure_target_is_empty(target)
    except scaffold.ScaffoldError as exc:
        raise typer.BadParameter(str(exc)) from exc

    project_name = scaffold.project_name_for(target)
    scaffold.copy_template(template.value, target, project_name)

    console.print(
        f"Created [bold {_BRAND}]{template.value}[/bold {_BRAND}] project "
        f"[bold]{project_name}[/bold] in {target}"
    )

    steps = []
    if target != Path.cwd():
        try:
            cd_target = target.relative_to(Path.cwd())
        except ValueError:
            cd_target = target
        steps.append(f"cd {cd_target}")
    steps.append("odf run")

    console.print(
        Panel(
            "\n".join(f"[{_BRAND}]$[/{_BRAND}] {step}" for step in steps),
            box=box.ROUNDED,
            border_style=_BRAND,
            padding=(0, 2),
            expand=False,
            title="[bold]Next steps[/bold]",
            title_align="left",
        )
    )


if __name__ == "__main__":
    app()
