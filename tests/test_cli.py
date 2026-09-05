import importlib
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from odf import cli

runner = CliRunner()

# tests/demo/conftest.py permanently inserts the real demo/ dir onto sys.path
# so its test modules can `import app`. In a full-suite run that entry
# outlives those tests, so clearing sys.modules alone isn't enough — a fresh
# `import_module("app")` here would still resolve to the real demo package
# from that leaked path entry instead of failing as this file expects.
_DEMO_DIR = str(Path(__file__).parents[1] / "demo")


def _pop_app_modules() -> None:
    for name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _clean_app_module(monkeypatch):
    _pop_app_modules()
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != _DEMO_DIR])
    yield
    _pop_app_modules()


class FakeServer:
    instances = []

    def __init__(self):
        self.started_with = None
        self.stopped = False
        self._ui_url = None
        self._mcp_url = None
        FakeServer.instances.append(self)

    def start(self, **kwargs):
        self.started_with = kwargs
        if kwargs.get("ui"):
            self._ui_url = f"http://{kwargs['ui_host']}:{kwargs['ui_port']}"
        if kwargs.get("mcp"):
            self._mcp_url = f"http://{kwargs['mcp_host']}:{kwargs['mcp_port']}/mcp"

    def wait(self):
        self.stopped = True

    def stop(self):
        self.stopped = True

    @property
    def ui_url(self):
        return self._ui_url

    @property
    def mcp_url(self):
        return self._mcp_url


@pytest.fixture
def fake_project(monkeypatch):
    FakeServer.instances = []
    calls = {}

    class FromConfigServer(FakeServer):
        @classmethod
        def from_config(cls, path):
            calls["config_path"] = path
            return cls()

    monkeypatch.setattr(cli, "Server", FromConfigServer)
    return calls


def make_project_dir(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("")
    (tmp_path / "config.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))


def test_run_imports_app_module_and_loads_config(tmp_path, monkeypatch, fake_project):
    make_project_dir(tmp_path, monkeypatch)

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code == 0, result.output
    assert "app" in sys.modules
    assert fake_project["config_path"] == "config.toml"


def test_run_passes_flags_through_to_start(tmp_path, monkeypatch, fake_project):
    make_project_dir(tmp_path, monkeypatch)

    result = runner.invoke(
        cli.app,
        ["run", "--no-ui", "--mcp", "--mcp-port", "9999", "--chat"],
    )

    assert result.exit_code == 0, result.output
    server = FakeServer.instances[0]
    assert server.started_with == {
        "ui": False,
        "ui_host": "127.0.0.1",
        "ui_port": 4747,
        "mcp": True,
        "mcp_host": "127.0.0.1",
        "mcp_port": 9999,
        "chat": True,
        "app_module": None,
    }


def test_run_calls_wait_which_stops_the_server(tmp_path, monkeypatch, fake_project):
    make_project_dir(tmp_path, monkeypatch)

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code == 0, result.output
    assert FakeServer.instances[0].stopped is True


def test_run_prints_ui_and_mcp_urls(tmp_path, monkeypatch, fake_project):
    make_project_dir(tmp_path, monkeypatch)

    result = runner.invoke(cli.app, ["run", "--mcp"])

    assert "UI running at http://127.0.0.1:4747" in result.output
    assert "MCP server running at http://127.0.0.1:4748/mcp" in result.output


def test_run_accepts_explicit_config_path(tmp_path, monkeypatch, fake_project):
    make_project_dir(tmp_path, monkeypatch)
    (tmp_path / "prod.toml").write_text("")

    result = runner.invoke(cli.app, ["run", "prod.toml"])

    assert result.exit_code == 0, result.output
    assert fake_project["config_path"] == "prod.toml"


def test_run_respects_custom_app_module(tmp_path, monkeypatch, fake_project):
    (tmp_path / "myapp.py").write_text("")
    (tmp_path / "config.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    result = runner.invoke(cli.app, ["run", "--app", "myapp"])

    assert result.exit_code == 0, result.output
    assert "myapp" in sys.modules
    sys.modules.pop("myapp", None)


def test_run_missing_app_module_reports_clean_error(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    result = runner.invoke(cli.app, ["run"])

    assert result.exit_code != 0
    assert "Could not import 'app'" in result.output


@pytest.mark.parametrize(
    "template", ["default", "data-analytics", "data-science", "data-engineering", "research"]
)
def test_init_scaffolds_an_importable_app_package(tmp_path, monkeypatch, template):
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    result = runner.invoke(cli.app, ["init", "--template", template])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "config.toml").exists()
    assert f'name = "{tmp_path.name}"' in (tmp_path / "config.toml").read_text()

    importlib.import_module("app")


def test_init_defaults_to_default_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "app" / "entities.py").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "data").exists()


def test_init_with_name_creates_subdirectory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["init", "myproject"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "myproject" / "config.toml").exists()
    assert 'name = "myproject"' in (tmp_path / "myproject" / "config.toml").read_text()
    assert "cd myproject" in result.output
    assert "odf run" in result.output


def test_init_rejects_non_empty_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing.txt").write_text("hi")

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code != 0
    assert "not empty" in result.output
