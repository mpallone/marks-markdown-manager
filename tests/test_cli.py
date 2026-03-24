from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mmm.cli import build_parser, main


# --- build_parser ---


def test_parser_deploy_full_args():
    parser = build_parser()
    args = parser.parse_args(
        ["deploy", "--config", "f.yaml", "--dry-run", "--type", "skills", "--tools", "claude,gemini"]
    )
    assert args.command == "deploy"
    assert args.config == "f.yaml"
    assert args.dry_run is True
    assert args.type == "skills"
    assert args.tools == "claude,gemini"


def test_parser_deploy_minimal():
    parser = build_parser()
    args = parser.parse_args(["deploy", "--config", "f.yaml"])
    assert args.command == "deploy"
    assert args.dry_run is False
    assert args.type is None
    assert args.tools is None


def test_parser_diff_args():
    parser = build_parser()
    args = parser.parse_args(["diff", "--config", "f.yaml", "--type", "context"])
    assert args.command == "diff"
    assert args.config == "f.yaml"
    assert args.type == "context"


def test_parser_status_args():
    parser = build_parser()
    args = parser.parse_args(["status", "--config", "f.yaml"])
    assert args.command == "status"
    assert args.config == "f.yaml"


def test_parser_deploy_missing_config():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["deploy"])


def test_parser_invalid_type_choice():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["deploy", "--config", "f.yaml", "--type", "invalid"])


def test_parser_no_subcommand():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None


# --- main ---


def test_main_no_command_exits():
    with pytest.raises(SystemExit):
        main([])


def test_main_deploy_dispatches(config_yaml: Path, monkeypatch):
    mock_deploy = MagicMock()
    monkeypatch.setattr("mmm.cli.deploy", mock_deploy)
    main(["deploy", "--config", str(config_yaml)])
    mock_deploy.assert_called_once()
    call_kwargs = mock_deploy.call_args
    assert call_kwargs[1]["dry_run"] is False


def test_main_diff_dispatches(config_yaml: Path, monkeypatch):
    mock_diff = MagicMock()
    monkeypatch.setattr("mmm.cli.show_diff", mock_diff)
    main(["diff", "--config", str(config_yaml)])
    mock_diff.assert_called_once()


def test_main_status_dispatches(config_yaml: Path, monkeypatch):
    mock_status = MagicMock()
    monkeypatch.setattr("mmm.cli.show_status", mock_status)
    main(["status", "--config", str(config_yaml)])
    mock_status.assert_called_once()


def test_main_tools_filter_parsing(config_yaml: Path, monkeypatch):
    mock_deploy = MagicMock()
    monkeypatch.setattr("mmm.cli.deploy", mock_deploy)
    main(["deploy", "--config", str(config_yaml), "--tools", "claude, gemini"])
    call_kwargs = mock_deploy.call_args
    assert call_kwargs[1]["tools_filter"] == ["claude", "gemini"]


def test_main_type_filter_passed(config_yaml: Path, monkeypatch):
    mock_deploy = MagicMock()
    monkeypatch.setattr("mmm.cli.deploy", mock_deploy)
    main(["deploy", "--config", str(config_yaml), "--type", "skills"])
    call_kwargs = mock_deploy.call_args
    assert call_kwargs[1]["type_filter"] == {"skills"}


def test_main_deploy_default_type_filter(config_yaml: Path, monkeypatch):
    mock_deploy = MagicMock()
    monkeypatch.setattr("mmm.cli.deploy", mock_deploy)
    main(["deploy", "--config", str(config_yaml)])
    call_kwargs = mock_deploy.call_args
    assert call_kwargs[1]["type_filter"] == {"context", "skills", "subagents"}
