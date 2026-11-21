"""Unit tests for CyGuide CLI parser, router, and context."""

import os

import pytest

from cyguide.cli.context import CliContext
from cyguide.cli.router import build_parser


def test_cli_parser_build():
    """Verify that build_parser constructs all domain subparsers."""
    parser = build_parser()
    assert parser.prog == "cyg"
    subparsers_action = next(a for a in parser._actions if a.dest == "subcommand")
    choices = subparsers_action.choices
    assert "session" in choices
    assert "workspace" in choices
    assert "tool" in choices
    assert "doctor" in choices
    assert "lab" in choices


def test_cli_context_from_args():
    """Verify CliContext resolution and environment variable defaults."""
    parser = build_parser()
    args = parser.parse_args(["--data-dir", "/tmp/custom_data", "doctor", "--json"])
    context = CliContext.from_args(args)

    assert context.data_dir == "/tmp/custom_data"
    assert context.db_path == "/tmp/custom_data/cyguide.db"
    assert context.is_json is True
    assert context.verbose is False


def test_cli_context_offline_flag(monkeypatch):
    """Verify --offline flag sets environment flags."""
    parser = build_parser()
    args = parser.parse_args(["--offline", "doctor"])
    context = CliContext.from_args(args)

    assert context.offline is True
    assert os.environ.get("CYGUIDE_OFFLINE") == "1"
    assert os.environ.get("CYGUIDE_NO_AI") == "1"


def test_cli_unknown_subcommand_handling():
    """Verify parser rejects unregistered commands with standard usage error."""
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["unknown-cmd"])
    assert exc.value.code != 0
