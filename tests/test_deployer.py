from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mmm.config import AssetSources, Config, ToolConfig
from mmm.deployer import (
    _check_tool_base_dir,
    _deploy_assets,
    _deploy_context,
    _diff_tree,
    _format_file_diff,
    _has_md_files,
    _is_excluded,
    concatenate_files,
    deploy,
    gather_asset_dirs,
    gather_context_files,
    show_diff,
    show_status,
)


# ============================================================
# _is_excluded
# ============================================================


def test_is_excluded_match():
    assert _is_excluded("draft.md", ["draft*"]) is True


def test_is_excluded_no_match():
    assert _is_excluded("final.md", ["draft*"]) is False


def test_is_excluded_empty_patterns():
    assert _is_excluded("anything.md", []) is False


def test_is_excluded_multiple_patterns():
    assert _is_excluded("draft-v2.md", ["*.bak", "draft*"]) is True


# ============================================================
# _has_md_files
# ============================================================


def test_has_md_files_true(tmp_path: Path):
    (tmp_path / "file.md").write_text("content")
    assert _has_md_files(tmp_path) is True


def test_has_md_files_false(tmp_path: Path):
    (tmp_path / "file.txt").write_text("content")
    assert _has_md_files(tmp_path) is False


def test_has_md_files_empty_dir(tmp_path: Path):
    d = tmp_path / "empty"
    d.mkdir()
    assert _has_md_files(d) is False


# ============================================================
# gather_context_files
# ============================================================


def test_gather_context_files_basic(mock_source_tree):
    sources = AssetSources(sources=[mock_source_tree["context_dir"]])
    files = gather_context_files(sources)
    assert len(files) == 2
    names = {f.name for f in files}
    assert "persona.md" in names
    assert "coding-standards.md" in names


def test_gather_context_files_with_exclude(tmp_path: Path):
    d = tmp_path / "ctx"
    d.mkdir()
    (d / "a.md").write_text("keep")
    (d / "draft-b.md").write_text("exclude")
    sources = AssetSources(sources=[d], exclude=["draft*"])
    files = gather_context_files(sources)
    assert len(files) == 1
    assert files[0].name == "a.md"


def test_gather_context_files_single_file_source(tmp_path: Path):
    f = tmp_path / "single.md"
    f.write_text("content")
    sources = AssetSources(sources=[f])
    files = gather_context_files(sources)
    assert len(files) == 1
    assert files[0] == f


def test_gather_context_files_single_file_excluded(tmp_path: Path):
    f = tmp_path / "draft.md"
    f.write_text("content")
    sources = AssetSources(sources=[f], exclude=["draft*"])
    files = gather_context_files(sources)
    assert len(files) == 0


def test_gather_context_files_empty_sources():
    sources = AssetSources(sources=[], exclude=[])
    files = gather_context_files(sources)
    assert files == []


def test_gather_context_files_nested_dirs(tmp_path: Path):
    d = tmp_path / "ctx"
    nested = d / "sub" / "deep"
    nested.mkdir(parents=True)
    (d / "top.md").write_text("top")
    (nested / "deep.md").write_text("deep")
    sources = AssetSources(sources=[d])
    files = gather_context_files(sources)
    names = {f.name for f in files}
    assert "top.md" in names
    assert "deep.md" in names


# ============================================================
# gather_asset_dirs
# ============================================================


def test_gather_asset_dirs_basic(mock_source_tree):
    sources = AssetSources(sources=[mock_source_tree["skills_dir"]])
    dirs = gather_asset_dirs(sources)
    assert len(dirs) == 2
    names = {d.name for d in dirs}
    assert "code-review" in names
    assert "test-writer" in names


def test_gather_asset_dirs_with_exclude(tmp_path: Path):
    parent = tmp_path / "skills"
    parent.mkdir()
    a = parent / "keep-me"
    a.mkdir()
    (a / "SKILL.md").write_text("keep")
    b = parent / "draft-skill"
    b.mkdir()
    (b / "SKILL.md").write_text("exclude")
    sources = AssetSources(sources=[parent], exclude=["draft*"])
    dirs = gather_asset_dirs(sources)
    assert len(dirs) == 1
    assert dirs[0].name == "keep-me"


def test_gather_asset_dirs_empty_subdir(tmp_path: Path):
    parent = tmp_path / "skills"
    parent.mkdir()
    empty = parent / "empty-skill"
    empty.mkdir()
    (empty / "readme.txt").write_text("no md here")
    sources = AssetSources(sources=[parent])
    dirs = gather_asset_dirs(sources)
    assert len(dirs) == 0


def test_gather_asset_dirs_source_has_md_directly(tmp_path: Path):
    """When source dir itself has .md files, return it and skip children."""
    src = tmp_path / "my-skill"
    src.mkdir()
    (src / "SKILL.md").write_text("content")
    child = src / "nested"
    child.mkdir()
    (child / "OTHER.md").write_text("nested")
    sources = AssetSources(sources=[src])
    dirs = gather_asset_dirs(sources)
    assert len(dirs) == 1
    assert dirs[0] == src


def test_gather_asset_dirs_source_is_file(tmp_path: Path):
    f = tmp_path / "not-a-dir.md"
    f.write_text("content")
    sources = AssetSources(sources=[f])
    dirs = gather_asset_dirs(sources)
    assert dirs == []


def test_gather_asset_dirs_empty_sources():
    sources = AssetSources(sources=[], exclude=[])
    dirs = gather_asset_dirs(sources)
    assert dirs == []


# ============================================================
# concatenate_files
# ============================================================


def test_concatenate_files_basic(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("alpha")
    b.write_text("beta")
    result = concatenate_files([a, b])
    assert f"<!-- Source: {a} -->" in result
    assert f"<!-- Source: {b} -->" in result
    assert "alpha" in result
    assert "beta" in result


def test_concatenate_files_single(tmp_path: Path):
    a = tmp_path / "a.md"
    a.write_text("only")
    result = concatenate_files([a])
    assert "<!-- Source:" in result
    assert "only" in result


def test_concatenate_files_empty_list():
    result = concatenate_files([])
    assert result == ""


def test_concatenate_files_empty_content(tmp_path: Path):
    a = tmp_path / "empty.md"
    a.write_text("")
    result = concatenate_files([a])
    assert "<!-- Source:" in result


# ============================================================
# _format_file_diff
# ============================================================


def test_format_file_diff_identical():
    assert _format_file_diff("same", "same", "label") == ""


def test_format_file_diff_different():
    result = _format_file_diff("old\n", "new\n", "test")
    assert "---" in result
    assert "+++" in result


def test_format_file_diff_empty_current():
    result = _format_file_diff("", "new content\n", "test")
    assert "+++" in result


# ============================================================
# _diff_tree
# ============================================================


def test_diff_tree_identical(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "a.md").write_text("same")
    (dest / "a.md").write_text("same")
    assert _diff_tree(src, dest) == ""


def test_diff_tree_modified(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "a.md").write_text("new\n")
    (dest / "a.md").write_text("old\n")
    result = _diff_tree(src, dest)
    assert "---" in result
    assert "+++" in result


def test_diff_tree_new_file(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "new.md").write_text("brand new\n")
    result = _diff_tree(src, dest)
    assert "new file" in result


def test_diff_tree_nested(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    sub = src / "sub"
    sub.mkdir(parents=True)
    dest.mkdir()
    (sub / "nested.md").write_text("nested\n")
    result = _diff_tree(src, dest)
    assert "nested" in result


# ============================================================
# _check_tool_base_dir
# ============================================================


def test_check_tool_base_dir_exists(tmp_path: Path):
    d = tmp_path / "ctx"
    d.mkdir()
    tc = ToolConfig(context_dir=d)
    assert _check_tool_base_dir("test", tc) is True


def test_check_tool_base_dir_parent_exists(tmp_path: Path):
    # tmp_path exists, but child does not
    tc = ToolConfig(context_dir=tmp_path / "nonexistent")
    assert _check_tool_base_dir("test", tc) is True


def test_check_tool_base_dir_none_dirs():
    tc = ToolConfig()
    assert _check_tool_base_dir("test", tc) is False


def test_check_tool_base_dir_nonexistent():
    tc = ToolConfig(
        context_dir=Path("/no/such/deeply/nested/path"),
        skills_dir=Path("/also/no/such/path"),
    )
    assert _check_tool_base_dir("test", tc) is False


# ============================================================
# _deploy_context
# ============================================================


def test_deploy_context_new_file(tmp_path: Path):
    ctx_dir = tmp_path / "ctx"
    ctx_dir.mkdir()
    tc = ToolConfig(context_dir=ctx_dir, context_filename="out.md")
    _deploy_context("hello world", "test", tc, dry_run=False)
    assert (ctx_dir / "out.md").read_text() == "hello world"


def test_deploy_context_dry_run_new_file(tmp_path: Path, capsys):
    ctx_dir = tmp_path / "ctx"
    ctx_dir.mkdir()
    tc = ToolConfig(context_dir=ctx_dir, context_filename="out.md")
    _deploy_context("hello", "test", tc, dry_run=True)
    assert not (ctx_dir / "out.md").exists()
    out = capsys.readouterr().out
    assert "Creating" in out


def test_deploy_context_empty_content(tmp_path: Path, capsys):
    ctx_dir = tmp_path / "ctx"
    ctx_dir.mkdir()
    tc = ToolConfig(context_dir=ctx_dir, context_filename="out.md")
    _deploy_context("   \n  ", "test", tc, dry_run=False)
    assert not (ctx_dir / "out.md").exists()
    out = capsys.readouterr().out
    assert "empty" in out.lower()


def test_deploy_context_overwrite_confirmed(tmp_path: Path, monkeypatch):
    ctx_dir = tmp_path / "ctx"
    ctx_dir.mkdir()
    target = ctx_dir / "out.md"
    target.write_text("old")
    monkeypatch.setattr("builtins.input", lambda _: "y")
    tc = ToolConfig(context_dir=ctx_dir, context_filename="out.md")
    _deploy_context("new", "test", tc, dry_run=False)
    assert target.read_text() == "new"


def test_deploy_context_overwrite_rejected(tmp_path: Path, monkeypatch):
    ctx_dir = tmp_path / "ctx"
    ctx_dir.mkdir()
    target = ctx_dir / "out.md"
    target.write_text("old")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    tc = ToolConfig(context_dir=ctx_dir, context_filename="out.md")
    _deploy_context("new", "test", tc, dry_run=False)
    assert target.read_text() == "old"


def test_deploy_context_no_changes(tmp_path: Path, capsys):
    ctx_dir = tmp_path / "ctx"
    ctx_dir.mkdir()
    target = ctx_dir / "out.md"
    target.write_text("same")
    tc = ToolConfig(context_dir=ctx_dir, context_filename="out.md")
    _deploy_context("same", "test", tc, dry_run=False)
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


# ============================================================
# _deploy_assets
# ============================================================


def test_deploy_assets_copies_tree(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("skill content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert (target_dir / "my-skill" / "SKILL.md").exists()
    assert (target_dir / "my-skill" / "SKILL.md").read_text() == "skill content"


def test_deploy_assets_skips_empty_source(tmp_path: Path, capsys):
    src = tmp_path / "src" / "empty-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert not (target_dir / "empty-skill").exists()
    out = capsys.readouterr().out
    assert "empty" in out.lower()


def test_deploy_assets_overwrite_rejected(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("new")
    target_dir = tmp_path / "target" / "skills"
    dest = target_dir / "my-skill"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert (dest / "SKILL.md").read_text() == "old"


def test_deploy_assets_no_changes(tmp_path: Path, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("same")
    target_dir = tmp_path / "target" / "skills"
    dest = target_dir / "my-skill"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("same")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


def test_deploy_assets_dry_run(tmp_path: Path, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert not (target_dir / "my-skill").exists()
    out = capsys.readouterr().out
    assert "Copying" in out


# ============================================================
# deploy (integration)
# ============================================================


def test_deploy_dry_run_no_writes(minimal_config: Config, capsys):
    deploy(minimal_config, None, {"context", "skills", "subagents"}, dry_run=True)
    # Verify no files were created in target dirs
    tc = minimal_config.tools["tool-a"]
    target_file = tc.context_dir / tc.context_filename
    assert not target_file.exists()


def test_deploy_tools_filter(minimal_config: Config, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, tools_filter=["nonexistent"], type_filter={"context"}, dry_run=False)
    tc = minimal_config.tools["tool-a"]
    target_file = tc.context_dir / tc.context_filename
    assert not target_file.exists()


def test_deploy_type_filter_context_only(minimal_config: Config, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, None, type_filter={"context"}, dry_run=False)
    tc = minimal_config.tools["tool-a"]
    # Context should be deployed
    assert (tc.context_dir / tc.context_filename).exists()
    # Skills should NOT be deployed (target skills dir is empty besides what was already there)
    skill_dirs = [d for d in tc.skills_dir.iterdir() if d.is_dir()]
    assert len(skill_dirs) == 0


def test_deploy_skips_missing_base_dir(capsys):
    config = Config(
        context=AssetSources(sources=[]),
        skills=AssetSources(sources=[]),
        subagents=AssetSources(sources=[]),
        tools={
            "ghost": ToolConfig(
                context_dir=Path("/no/such/deeply/nested/tool"),
                context_filename="ctx.md",
            ),
        },
    )
    deploy(config, None, {"context"}, dry_run=False)
    out = capsys.readouterr().out
    assert "Skipping" in out


# ============================================================
# show_diff
# ============================================================


def test_show_diff_no_changes(minimal_config: Config, monkeypatch, capsys):
    # First deploy, then diff should show no changes
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, None, {"context", "skills", "subagents"}, dry_run=False)
    show_diff(minimal_config, None, {"context", "skills", "subagents"})
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


def test_show_diff_new_target(minimal_config: Config, capsys):
    show_diff(minimal_config, None, {"context"})
    out = capsys.readouterr().out
    assert "new file" in out.lower() or "new" in out.lower()


def test_show_diff_with_changes(minimal_config: Config, monkeypatch, capsys):
    # Deploy first, then modify source
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, None, {"context"}, dry_run=False)
    # Modify the deployed file
    tc = minimal_config.tools["tool-a"]
    target = tc.context_dir / tc.context_filename
    target.write_text("modified content")
    show_diff(minimal_config, None, {"context"})
    out = capsys.readouterr().out
    assert "---" in out or "+++" in out


def test_show_diff_tools_filter(minimal_config: Config, capsys):
    show_diff(minimal_config, tools_filter=["nonexistent"], type_filter={"context"})
    out = capsys.readouterr().out
    # tool-a output should not appear
    assert "tool-a" not in out


# ============================================================
# show_status
# ============================================================


def test_show_status_deployed(minimal_config: Config, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, None, {"context", "skills"}, dry_run=False)
    show_status(minimal_config)
    out = capsys.readouterr().out
    assert "bytes" in out.lower()
    assert "code-review" in out or "test-writer" in out


def test_show_status_not_deployed(minimal_config: Config, capsys):
    show_status(minimal_config)
    out = capsys.readouterr().out
    assert "not deployed" in out.lower() or "empty" in out.lower()


def test_show_status_base_dir_missing(capsys):
    config = Config(
        tools={
            "ghost": ToolConfig(
                context_dir=Path("/no/such/deeply/nested/path"),
                context_filename="ctx.md",
            ),
        },
    )
    show_status(config)
    out = capsys.readouterr().out
    assert "not found" in out.lower()
