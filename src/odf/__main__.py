"""Main module."""

import typer
from rich import print as rprint

from odf import __version__

app = typer.Typer()


@app.command()
def init(project, path: str = None):
    """Initialize PROJECT, optionally with a --path."""
    rprint(f"[bright_black]{__version__} is not intended for use[/bright_black]")


@app.command()
def create(project, path: str = None):
    """Create PROJECT, optionally with a --path."""
    rprint(f"[bright_black]{__version__} is not intended for use[/bright_black]")


def main():
    """Main function which starts the app."""
    app()


if __name__ == "__main__":
    main()
