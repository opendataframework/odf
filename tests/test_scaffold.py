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


def test_copy_template_escapes_quotes_in_project_name(tmp_path):
    target = tmp_path / "weird"

    scaffold.copy_template("default", target, 'weird"name')

    assert 'name = "weird\\"name"' in (target / "config.toml").read_text()
