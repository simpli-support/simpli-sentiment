"""Tests for the CLI interface."""

from typer.testing import CliRunner

from simpli_sentiment.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "simpli-sentiment" in result.output


def test_serve_help() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--workers" in result.output
    assert "--log-level" in result.output
    assert "--reload" in result.output
