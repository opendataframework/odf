"""Project scaffolding for ``odf init`` — copies a bundled template onto disk."""

import importlib.resources
import shutil
from pathlib import Path


class ScaffoldError(Exception):
    """Raised when a project cannot be scaffolded into the requested target."""


def resolve_target(name: str | None) -> Path:
    return Path.cwd() / name if name else Path.cwd()


def ensure_target_is_empty(target: Path) -> None:
    if target.is_file():
        raise ScaffoldError(f"{target} already exists and is a file.")
    if target.is_dir() and any(target.iterdir()):
        raise ScaffoldError(f"{target} already exists and is not empty.")


def project_name_for(target: Path) -> str:
    return target.resolve().name


def copy_template(template: str, target: Path, project_name: str) -> None:
    root = importlib.resources.files("odf") / "templates" / template
    with importlib.resources.as_file(root) as src:
        shutil.copytree(src, target, dirs_exist_ok=True)

    config_path = target / "config.toml"
    escaped = project_name.replace("\\", "\\\\").replace('"', '\\"')
    config_path.write_text(config_path.read_text().replace("{{project_name}}", escaped))
