"""Tests for the CLI interface."""

import re

from typer.testing import CliRunner

from simpli_sentiment.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "simpli-sentiment" in result.output


def test_serve_help() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "--host" in output
    assert "--port" in output
    assert "--workers" in output
    assert "--log-level" in output
    assert "--reload" in output
