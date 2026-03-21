from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class AssetSources:
    sources: List[Path] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class ToolConfig:
    context_dir: Optional[Path] = None
    context_filename: Optional[str] = None
    skills_dir: Optional[Path] = None
    subagents_dir: Optional[Path] = None


@dataclass
class Config:
    context: AssetSources = field(default_factory=AssetSources)
    skills: AssetSources = field(default_factory=AssetSources)
    subagents: AssetSources = field(default_factory=AssetSources)
    tools: Dict[str, ToolConfig] = field(default_factory=dict)


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def _parse_asset_sources(raw: dict) -> AssetSources:
    sources = [_expand(s) for s in raw.get("sources", [])]
    exclude = raw.get("exclude", [])
    return AssetSources(sources=sources, exclude=exclude)


def _parse_tool_config(raw: dict) -> ToolConfig:
    tc = ToolConfig()
    if "context_dir" in raw:
        tc.context_dir = _expand(raw["context_dir"])
    if "context_filename" in raw:
        tc.context_filename = raw["context_filename"]
    if "skills_dir" in raw:
        tc.skills_dir = _expand(raw["skills_dir"])
    if "subagents_dir" in raw:
        tc.subagents_dir = _expand(raw["subagents_dir"])
    return tc


def load_config(path: str) -> Config:
    config_path = Path(path).expanduser()
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    config = Config()

    if "context" in raw:
        config.context = _parse_asset_sources(raw["context"])
    if "skills" in raw:
        config.skills = _parse_asset_sources(raw["skills"])
    if "subagents" in raw:
        config.subagents = _parse_asset_sources(raw["subagents"])

    for tool_name, tool_raw in raw.get("tools", {}).items():
        config.tools[tool_name] = _parse_tool_config(tool_raw)

    # Validate sources exist
    for label, asset in [("context", config.context), ("skills", config.skills), ("subagents", config.subagents)]:
        for src in asset.sources:
            if not src.exists():
                print(f"Warning: {label} source does not exist: {src}", file=sys.stderr)

    return config
