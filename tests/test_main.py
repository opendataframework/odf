"""Tests for main module."""

from odf.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()


def test_init():
    """Tests app's `init` command."""
    result = runner.invoke(app, ["init", "PROJECT"])
    assert result.exit_code == 0
    assert "is not intended for use" in result.stdout


def test_create():
    """Tests app's `create` command."""
    result = runner.invoke(app, ["create", "PROJECT"])
    assert result.exit_code == 0
    assert "is not intended for use" in result.stdout
