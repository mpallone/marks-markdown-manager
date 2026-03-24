"""YAML configuration loading and data model for mmm.

Defines the dataclasses that represent an mmm.yaml config file and provides
the ``load_config()`` function to parse it. The config specifies:

1. Where to find source assets (context .md files, skill dirs, subagent dirs)
2. Where each AI tool expects those assets to be deployed

Example mmm.yaml::

    context:
      sources:
        - ~/rules/context/
      exclude:
        - "draft-*"
    tools:
      gemini:
        context_dir: ~/.gemini
        context_filename: GEMINI.md
        skills_dir: ~/.gemini/skills/
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class AssetSources:
    """Source directories and exclusion patterns for one asset type.

    Groups together where to find assets and what to skip. Used for each of
    the three asset types: context, skills, and subagents.

    Example::

        AssetSources(
            sources=[Path("~/rules/context/"), Path("~/extra-rules/")],
            exclude=["draft-*", "*.tmp"],
        )

    Attributes:
        sources: Directories (or individual files) to gather assets from.
            Each path is expanded via ``Path.expanduser()`` during config loading.
        exclude: fnmatch glob patterns for filenames/dirnames to skip.
            For example, "draft-*" excludes any file starting with "draft-".
    """

    sources: List[Path] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class ToolConfig:
    """Target directories where mmm deploys assets for a single AI tool.

    Each AI tool (Gemini, Claude, Windsurf, etc.) has its own filesystem
    layout for configuration. This dataclass captures where each asset type
    should be written for one tool.

    Example for Gemini CLI::

        ToolConfig(
            context_dir=Path("~/.gemini"),
            context_filename="GEMINI.md",
            skills_dir=Path("~/.gemini/skills/"),
            subagents_dir=None,  # Gemini doesn't support subagents
        )

    Attributes:
        context_dir: Directory where the concatenated context file is written.
        context_filename: Name of the output context file (e.g. "GEMINI.md").
            Both context_dir and context_filename must be set for context deployment.
        skills_dir: Directory where skill subdirectories are copied into.
        subagents_dir: Directory where subagent subdirectories are copied into.
    """

    context_dir: Optional[Path] = None
    context_filename: Optional[str] = None
    skills_dir: Optional[Path] = None
    subagents_dir: Optional[Path] = None


@dataclass
class Config:
    """Top-level mmm configuration: asset sources and per-tool deployment targets.

    Ties together *where to find* assets (the three ``AssetSources`` fields)
    with *where to put them* (the ``tools`` dict mapping tool names to their
    ``ToolConfig``).

    Attributes:
        context: Sources and excludes for context markdown files.
        skills: Sources and excludes for skill directories.
        subagents: Sources and excludes for subagent directories.
        tools: Mapping of tool name (e.g. "gemini", "claude") to its
            deployment target configuration.
    """

    context: AssetSources = field(default_factory=AssetSources)
    skills: AssetSources = field(default_factory=AssetSources)
    subagents: AssetSources = field(default_factory=AssetSources)
    tools: Dict[str, ToolConfig] = field(default_factory=dict)


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def _parse_asset_sources(raw: dict) -> AssetSources:
    """Convert a raw YAML mapping into an AssetSources instance.

    Example input (from parsed YAML)::

        {"sources": ["~/rules/context/"], "exclude": ["draft-*"]}

    Becomes::

        AssetSources(sources=[Path("/home/user/rules/context/")], exclude=["draft-*"])

    Args:
        raw: Dictionary from YAML with optional "sources" (list of path strings)
            and "exclude" (list of glob pattern strings) keys.

    Returns:
        An AssetSources with expanded paths and exclusion patterns.
    """
    sources = [_expand(s) for s in raw.get("sources", [])]
    exclude = raw.get("exclude", [])
    return AssetSources(sources=sources, exclude=exclude)


def _parse_tool_config(raw: dict) -> ToolConfig:
    """Convert a raw YAML mapping into a ToolConfig instance.

    Example input (from parsed YAML)::

        {"context_dir": "~/.gemini", "context_filename": "GEMINI.md",
         "skills_dir": "~/.gemini/skills/"}

    Becomes::

        ToolConfig(context_dir=Path("/home/user/.gemini"),
                   context_filename="GEMINI.md",
                   skills_dir=Path("/home/user/.gemini/skills/"))

    Args:
        raw: Dictionary from YAML with optional keys: "context_dir",
            "context_filename", "skills_dir", "subagents_dir".

    Returns:
        A ToolConfig with path fields expanded via expanduser().
    """
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
    """Load and validate an mmm.yaml configuration file.

    Reads the YAML file, parses it into a Config object, and validates that
    all declared source directories actually exist on disk.

    Error handling:
    - Missing config file: prints error to stderr and calls ``sys.exit(1)``.
    - Missing source directory: prints a warning to stderr but continues
      (allows partial configs where some sources aren't on the current machine).

    Args:
        path: Path to the mmm.yaml file (e.g. "~/projects/mmm.yaml").
            Tilde is expanded automatically.

    Returns:
        A fully populated Config object ready for use by the deployer.
    """
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
