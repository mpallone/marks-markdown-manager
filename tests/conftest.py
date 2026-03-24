from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mmm.config import AssetSources, Config, ToolConfig


@pytest.fixture
def mock_source_tree(tmp_path: Path) -> dict[str, Path]:
    """Create a miniature replica of the mock/ directory structure."""
    # Context
    ctx = tmp_path / "context"
    ctx.mkdir()
    (ctx / "persona.md").write_text("# Persona\nYou are a helpful assistant.\n")
    (ctx / "coding-standards.md").write_text("# Coding Standards\nUse type hints.\n")

    # Skills
    skills = tmp_path / "skills"
    skills.mkdir()
    cr = skills / "code-review"
    cr.mkdir()
    (cr / "SKILL.md").write_text("# Code Review\nReview code carefully.\n")
    tw = skills / "test-writer"
    tw.mkdir()
    (tw / "SKILL.md").write_text("# Test Writer\nWrite thorough tests.\n")

    # Subagents
    subagents = tmp_path / "subagents"
    subagents.mkdir()
    pl = subagents / "planner"
    pl.mkdir()
    (pl / "SKILL.md").write_text("# Planner\nPlan the work.\n")
    rs = subagents / "researcher"
    rs.mkdir()
    (rs / "SKILL.md").write_text("# Researcher\nResearch the topic.\n")

    return {
        "context_dir": ctx,
        "skills_dir": skills,
        "subagents_dir": subagents,
    }


@pytest.fixture
def mock_target_tree(tmp_path: Path) -> dict[str, Path]:
    """Create empty target directories for a fictional tool."""
    base = tmp_path / "target" / "tool-a"
    rules = base / "rules"
    skills = base / "skills"
    agents = base / "agents"
    for d in [rules, skills, agents]:
        d.mkdir(parents=True)
    return {
        "base": base,
        "context_dir": rules,
        "skills_dir": skills,
        "subagents_dir": agents,
    }


@pytest.fixture
def minimal_config(
    mock_source_tree: dict[str, Path],
    mock_target_tree: dict[str, Path],
) -> Config:
    """Build a Config object using fixture paths (no YAML involved)."""
    return Config(
        context=AssetSources(sources=[mock_source_tree["context_dir"]]),
        skills=AssetSources(sources=[mock_source_tree["skills_dir"]]),
        subagents=AssetSources(sources=[mock_source_tree["subagents_dir"]]),
        tools={
            "tool-a": ToolConfig(
                context_dir=mock_target_tree["context_dir"],
                context_filename="context.md",
                skills_dir=mock_target_tree["skills_dir"],
                subagents_dir=mock_target_tree["subagents_dir"],
            ),
        },
    )


@pytest.fixture
def config_yaml(
    tmp_path: Path,
    mock_source_tree: dict[str, Path],
    mock_target_tree: dict[str, Path],
) -> Path:
    """Write a valid YAML config file and return its path."""
    data = {
        "context": {"sources": [str(mock_source_tree["context_dir"])], "exclude": []},
        "skills": {"sources": [str(mock_source_tree["skills_dir"])], "exclude": []},
        "subagents": {"sources": [str(mock_source_tree["subagents_dir"])], "exclude": []},
        "tools": {
            "tool-a": {
                "context_dir": str(mock_target_tree["context_dir"]),
                "context_filename": "context.md",
                "skills_dir": str(mock_target_tree["skills_dir"]),
                "subagents_dir": str(mock_target_tree["subagents_dir"]),
            },
        },
    }
    cfg_path = tmp_path / "mmm.yaml"
    cfg_path.write_text(yaml.dump(data))
    return cfg_path
