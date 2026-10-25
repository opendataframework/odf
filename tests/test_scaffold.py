import json
import os
import subprocess  # nosec B404 — runs this interpreter on a scaffolded project
import sys
from pathlib import Path

import pytest

from odf import scaffold


def test_resolve_target_uses_cwd_when_name_omitted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert scaffold.resolve_target(None) == tmp_path


def test_resolve_target_appends_name_to_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert scaffold.resolve_target("myproject") == tmp_path / "myproject"


def test_ensure_target_is_empty_allows_missing_directory(tmp_path):
    scaffold.ensure_target_is_empty(tmp_path / "does-not-exist")


def test_ensure_target_is_empty_allows_empty_directory(tmp_path):
    scaffold.ensure_target_is_empty(tmp_path)


def test_ensure_target_is_empty_rejects_non_empty_directory(tmp_path):
    (tmp_path / "existing.txt").write_text("hi")

    with pytest.raises(scaffold.ScaffoldError):
        scaffold.ensure_target_is_empty(tmp_path)


def test_ensure_target_is_empty_rejects_file(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("hi")

    with pytest.raises(scaffold.ScaffoldError):
        scaffold.ensure_target_is_empty(target)


def test_project_name_for_uses_target_basename(tmp_path):
    assert scaffold.project_name_for(tmp_path / "myproject") == "myproject"


def test_copy_template_writes_files_and_substitutes_project_name(tmp_path):
    target = tmp_path / "myproject"

    scaffold.copy_template("default", target, "myproject")

    assert (target / "app" / "entities.py").exists()
    assert 'name = "myproject"' in (target / "config.toml").read_text()


def test_copy_template_writes_the_ml_template(tmp_path):
    target = tmp_path / "trainer"

    scaffold.copy_template("ml", target, "trainer")

    for module in (
        "entities",
        "storages",
        "repositories",
        "training",
        "tasks",
        "charts",
        "exports",
    ):
        assert (target / "app" / f"{module}.py").exists()
    config = (target / "config.toml").read_text()
    assert 'name = "trainer"' in config
    assert "[task.sweep]" in config


# The scaffolded project runs in its own interpreter, so its `app` package
# never meets the examples' `app` packages this pytest process imports.
_SWEEP_AND_EXPORT = """
import json
import app
from odf.server import Server

server = Server.from_config("config.toml")
server.start()
summaries = server.context.execute("task.sweep")
best = min(summaries, key=lambda s: s["final"]["loss"])
folder = server.context.call("function.export-run", run_id=best["run_id"])
server.stop()
print(json.dumps({"best": best["run"], "folder": folder}))
"""


def test_ml_template_sweeps_and_exports_a_run_with_the_standard_library(tmp_path):
    target = tmp_path / "trainer"
    scaffold.copy_template("ml", target, "trainer")
    # pytest's `pythonpath = ["src"]` doesn't reach the subprocess, and CI
    # installs with `--no-root`, so point it at this checkout's `odf`.
    src = str(Path(scaffold.__file__).parents[1])
    env = os.environ | {
        "PYTHONPATH": os.pathsep.join(filter(None, [src, os.environ.get("PYTHONPATH")]))
    }

    result = subprocess.run(  # nosec B603 — fixed arguments, this interpreter
        [sys.executable, "-c", _SWEEP_AND_EXPORT],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
    )

    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["best"] == "lr=0.1"
    folder = target / out["folder"]
    # The template trains no real model, so there is no model file to export.
    assert sorted(p.name for p in folder.iterdir()) == [
        "metrics.csv",
        "params.json",
        "summary.json",
    ]


def test_copy_template_escapes_quotes_in_project_name(tmp_path):
    target = tmp_path / "weird"

    scaffold.copy_template("default", target, 'weird"name')

    assert 'name = "weird\\"name"' in (target / "config.toml").read_text()
