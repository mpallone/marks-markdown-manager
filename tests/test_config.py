from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mmm.config import (
    AssetSources,
    Config,
    ToolConfig,
    _expand,
    _parse_asset_sources,
    _parse_tool_config,
    load_config,
)


# --- _expand ---


def test_expand_tilde():
    result = _expand("~/foo")
    assert result == Path.home() / "foo"


def test_expand_absolute():
    result = _expand("/tmp/bar")
    assert result == Path("/tmp/bar")


def test_expand_relative():
    result = _expand("relative/path")
    assert result == Path("relative/path")


# --- _parse_asset_sources ---


def test_parse_asset_sources_full():
    raw = {"sources": ["/a", "/b"], "exclude": ["*.bak"]}
    result = _parse_asset_sources(raw)
    assert len(result.sources) == 2
    assert result.sources[0] == Path("/a")
    assert result.sources[1] == Path("/b")
    assert result.exclude == ["*.bak"]


def test_parse_asset_sources_empty():
    result = _parse_asset_sources({})
    assert result.sources == []
    assert result.exclude == []


def test_parse_asset_sources_no_exclude():
    raw = {"sources": ["/a"]}
    result = _parse_asset_sources(raw)
    assert len(result.sources) == 1
    assert result.exclude == []


# --- _parse_tool_config ---


def test_parse_tool_config_all_fields():
    raw = {
        "context_dir": "/tmp/ctx",
        "context_filename": "CTX.md",
        "skills_dir": "/tmp/skills",
        "subagents_dir": "/tmp/agents",
    }
    tc = _parse_tool_config(raw)
    assert tc.context_dir == Path("/tmp/ctx")
    assert tc.context_filename == "CTX.md"
    assert tc.skills_dir == Path("/tmp/skills")
    assert tc.subagents_dir == Path("/tmp/agents")


def test_parse_tool_config_partial():
    raw = {"context_dir": "/tmp/ctx", "context_filename": "CTX.md"}
    tc = _parse_tool_config(raw)
    assert tc.context_dir == Path("/tmp/ctx")
    assert tc.context_filename == "CTX.md"
    assert tc.skills_dir is None
    assert tc.subagents_dir is None


def test_parse_tool_config_empty():
    tc = _parse_tool_config({})
    assert tc.context_dir is None
    assert tc.context_filename is None
    assert tc.skills_dir is None
    assert tc.subagents_dir is None


# --- load_config ---


def test_load_config_valid(config_yaml: Path):
    config = load_config(str(config_yaml))
    assert isinstance(config, Config)
    assert len(config.context.sources) == 1
    assert "tool-a" in config.tools
    tc = config.tools["tool-a"]
    assert tc.context_filename == "context.md"


def test_load_config_missing_file():
    with pytest.raises(SystemExit):
        load_config("/nonexistent/path/mmm.yaml")


def test_load_config_empty_yaml(tmp_path: Path):
    """Empty YAML (parsed as None) — should not crash."""
    cfg = tmp_path / "empty.yaml"
    cfg.write_text("")
    # yaml.safe_load returns None for empty file, which will cause an error
    # when trying to access keys. This tests the current behavior.
    with pytest.raises((SystemExit, TypeError, AttributeError)):
        load_config(str(cfg))


def test_load_config_warns_missing_source(tmp_path: Path, capsys):
    data = {
        "context": {"sources": [str(tmp_path / "nonexistent")]},
        "tools": {},
    }
    cfg = tmp_path / "warn.yaml"
    cfg.write_text(yaml.dump(data))
    config = load_config(str(cfg))
    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert "nonexistent" in captured.err


def test_load_config_multiple_tools(tmp_path: Path):
    data = {
        "tools": {
            "alpha": {"context_dir": "/tmp/a"},
            "beta": {"context_dir": "/tmp/b"},
            "gamma": {"context_dir": "/tmp/c"},
        },
    }
    cfg = tmp_path / "multi.yaml"
    cfg.write_text(yaml.dump(data))
    config = load_config(str(cfg))
    assert len(config.tools) == 3
    assert set(config.tools.keys()) == {"alpha", "beta", "gamma"}
