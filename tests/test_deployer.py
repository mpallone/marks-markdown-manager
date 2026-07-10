from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mmm.config import AssetSources, Config, ToolConfig
from mmm.deployer import (
    _check_tool_base_dir,
    _classify_dest,
    _deploy_assets,
    _deploy_context,
    _diff_tree,
    _format_file_diff,
    _has_md_files,
    _is_excluded,
    _remove_dest,
    concatenate_files,
    deploy,
    gather_asset_dirs,
    gather_context_files,
    show_diff,
    show_status,
)


def _forbid_input(monkeypatch):
    """Make any input() call fail the test — for paths that must not prompt."""
    monkeypatch.setattr(
        "builtins.input",
        lambda _: pytest.fail("input() should not be called"),
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


def test_diff_tree_dest_only_file_shown_as_removed(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (src / "a.md").write_text("same\n")
    (dest / "a.md").write_text("same\n")
    (dest / "local-notes.md").write_text("only in dest\n")
    result = _diff_tree(src, dest)
    assert "will be removed" in result
    assert "local-notes.md" in result
    assert "only in dest" in result


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
# _classify_dest
# ============================================================


def test_classify_dest_missing(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    assert _classify_dest(src, tmp_path / "nothing-here") == "missing"


def test_classify_dest_linked(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.symlink_to(src.resolve(), target_is_directory=True)
    assert _classify_dest(src, dest) == "linked"


def test_classify_dest_wrong_link(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    dest = tmp_path / "dest"
    dest.symlink_to(other.resolve(), target_is_directory=True)
    assert _classify_dest(src, dest) == "wrong-link"


def test_classify_dest_broken_link(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.symlink_to(tmp_path / "gone", target_is_directory=True)
    assert _classify_dest(src, dest) == "broken-link"


def test_classify_dest_copy(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    assert _classify_dest(src, dest) == "copy"


def test_classify_dest_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.write_text("a plain file")
    assert _classify_dest(src, dest) == "file"


def test_classify_dest_self_same_dir(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    assert _classify_dest(src, src) == "self"


def test_classify_dest_self_via_symlinked_parent(tmp_path: Path):
    # e.g. the user made ~/.claude/skills a symlink to their source repo:
    # dest is a real dir reached through the symlinked parent.
    parent = tmp_path / "sources"
    src = parent / "my-skill"
    src.mkdir(parents=True)
    linked_parent = tmp_path / "target-skills"
    linked_parent.symlink_to(parent, target_is_directory=True)
    dest = linked_parent / "my-skill"
    assert not dest.is_symlink()
    assert _classify_dest(src, dest) == "self"


# ============================================================
# _remove_dest
# ============================================================


def test_remove_dest_symlink_leaves_target_intact(tmp_path: Path):
    target = tmp_path / "real-dir"
    target.mkdir()
    (target / "SKILL.md").write_text("precious")
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    _remove_dest(link)
    assert not link.is_symlink()
    assert (target / "SKILL.md").read_text() == "precious"


def test_remove_dest_file(tmp_path: Path):
    f = tmp_path / "plain"
    f.write_text("bye")
    _remove_dest(f)
    assert not f.exists()


def test_remove_dest_real_dir(tmp_path: Path):
    d = tmp_path / "dir"
    d.mkdir()
    (d / "a.md").write_text("bye")
    _remove_dest(d)
    assert not d.exists()


# ============================================================
# _deploy_assets
# ============================================================


def test_deploy_assets_creates_symlink(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("skill content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    dest = target_dir / "my-skill"
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    assert dest.readlink().is_absolute()
    assert (dest / "SKILL.md").read_text() == "skill content"


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


def test_deploy_assets_replace_rejected(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("new")
    target_dir = tmp_path / "target" / "skills"
    dest = target_dir / "my-skill"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert not dest.is_symlink()
    assert (dest / "SKILL.md").read_text() == "old"


def test_deploy_assets_no_changes(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("same")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(src.resolve(), target_is_directory=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


def test_deploy_assets_idempotent_second_deploy(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    dest = target_dir / "my-skill"
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


def test_deploy_assets_replaces_legacy_copy(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("new content\n")
    target_dir = tmp_path / "target" / "skills"
    dest = target_dir / "my-skill"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("stale copy\n")
    monkeypatch.setattr("builtins.input", lambda _: "y")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    assert (dest / "SKILL.md").read_text() == "new content\n"
    out = capsys.readouterr().out
    assert "will be replaced by symlink" in out
    assert "stale copy" in out  # the _diff_tree output shows what differed


def test_deploy_assets_repoints_wrong_link(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    other = tmp_path / "other-skill"
    other.mkdir()
    (other / "SKILL.md").write_text("other")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(other.resolve(), target_is_directory=True)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    # Repointing removes only the link — never the old target's contents
    assert (other / "SKILL.md").read_text() == "other"


def test_deploy_assets_repoint_wrong_link_rejected(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    other = tmp_path / "other-skill"
    other.mkdir()
    (other / "SKILL.md").write_text("other")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(other.resolve(), target_is_directory=True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert dest.is_symlink()
    assert dest.resolve() == other.resolve()


def test_deploy_assets_repairs_broken_link(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(tmp_path / "gone", target_is_directory=True)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()


def test_deploy_assets_replaces_regular_file(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.write_text("a plain file where a skill should be")
    monkeypatch.setattr("builtins.input", lambda _: "y")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    out = capsys.readouterr().out
    assert "existing file" in out


def test_deploy_assets_replace_file_rejected(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.write_text("keep me")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert not dest.is_symlink()
    assert dest.read_text() == "keep me"


def test_deploy_assets_repair_broken_link_rejected(tmp_path: Path, monkeypatch):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(tmp_path / "gone", target_is_directory=True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert dest.is_symlink()
    assert not dest.exists()  # still the original broken link


def test_deploy_assets_dest_is_source_untouched(tmp_path: Path, monkeypatch, capsys):
    # skills_dir configured to point straight at the sources: dest IS src.
    parent = tmp_path / "skills"
    src = parent / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("precious")
    _forbid_input(monkeypatch)
    _deploy_assets([src], parent, "test", "skill", dry_run=False)
    assert not src.is_symlink()
    assert (src / "SKILL.md").read_text() == "precious"
    out = capsys.readouterr().out
    assert "source directory itself" in out


def test_deploy_assets_dest_is_source_via_symlinked_parent(
    tmp_path: Path, monkeypatch, capsys
):
    # The user symlinked the whole target dir at their source repo before mmm:
    # dest is a real dir reached through the symlinked parent — still the source.
    parent = tmp_path / "sources"
    src = parent / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("precious")
    target_dir = tmp_path / "target-skills"
    target_dir.symlink_to(parent, target_is_directory=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    assert not src.is_symlink()
    assert not (target_dir / "my-skill").is_symlink()
    assert (src / "SKILL.md").read_text() == "precious"
    out = capsys.readouterr().out
    assert "source directory itself" in out


def test_deploy_assets_legacy_copy_with_dest_only_file(
    tmp_path: Path, monkeypatch, capsys
):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("same\n")
    target_dir = tmp_path / "target" / "skills"
    dest = target_dir / "my-skill"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("same\n")
    (dest / "local-notes.md").write_text("only in dest\n")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    _deploy_assets([src], target_dir, "test", "skill", dry_run=False)
    out = capsys.readouterr().out
    # The dest-only file must show up as a removal, not "(contents identical)"
    assert "will be removed" in out
    assert "local-notes.md" in out
    assert "contents identical" not in out
    assert (dest / "local-notes.md").exists()  # rejected -> untouched


def test_deploy_assets_dry_run(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert not (target_dir / "my-skill").exists()
    out = capsys.readouterr().out
    assert "Linking" in out


def test_deploy_assets_dry_run_legacy_copy(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("new\n")
    target_dir = tmp_path / "target" / "skills"
    dest = target_dir / "my-skill"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old\n")
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert not dest.is_symlink()
    assert (dest / "SKILL.md").read_text() == "old\n"
    out = capsys.readouterr().out
    assert "will be replaced by symlink" in out


def test_deploy_assets_dry_run_wrong_link(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    other = tmp_path / "other-skill"
    other.mkdir()
    (other / "SKILL.md").write_text("other")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(other.resolve(), target_is_directory=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert dest.resolve() == other.resolve()
    out = capsys.readouterr().out
    assert "will repoint" in out


def test_deploy_assets_dry_run_regular_file(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.write_text("keep me")
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert not dest.is_symlink()
    assert dest.read_text() == "keep me"
    out = capsys.readouterr().out
    assert "existing file" in out


def test_deploy_assets_dry_run_linked(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(src.resolve(), target_is_directory=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert dest.resolve() == src.resolve()
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


def test_deploy_assets_dry_run_broken_link(tmp_path: Path, monkeypatch, capsys):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("content")
    target_dir = tmp_path / "target" / "skills"
    target_dir.mkdir(parents=True)
    dest = target_dir / "my-skill"
    dest.symlink_to(tmp_path / "gone", target_is_directory=True)
    _forbid_input(monkeypatch)
    _deploy_assets([src], target_dir, "test", "skill", dry_run=True)
    assert dest.is_symlink()
    assert not dest.exists()  # still broken — dry run changed nothing
    out = capsys.readouterr().out
    assert "broken symlink" in out


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


def test_show_diff_new_asset_reports_symlink(minimal_config: Config, capsys):
    show_diff(minimal_config, None, {"skills"})
    out = capsys.readouterr().out
    assert "will create symlink" in out


def test_show_diff_legacy_copy(minimal_config: Config, capsys):
    tc = minimal_config.tools["tool-a"]
    dest = tc.skills_dir / "code-review"
    dest.mkdir()
    (dest / "SKILL.md").write_text("stale copy\n")
    show_diff(minimal_config, None, {"skills"})
    out = capsys.readouterr().out
    assert "legacy copy" in out
    assert "will be replaced by symlink" in out
    assert "stale copy" in out  # content diff of the stale copy is shown


def test_show_diff_correct_symlink_no_changes(minimal_config: Config, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, None, {"skills"}, dry_run=False)
    show_diff(minimal_config, None, {"skills"})
    out = capsys.readouterr().out
    assert "no changes" in out.lower()


def test_show_diff_broken_symlink_no_crash(minimal_config: Config, tmp_path: Path, capsys):
    tc = minimal_config.tools["tool-a"]
    dest = tc.skills_dir / "code-review"
    dest.symlink_to(tmp_path / "gone", target_is_directory=True)
    show_diff(minimal_config, None, {"skills"})
    out = capsys.readouterr().out
    assert "(broken)" in out
    assert "will repoint" in out


def test_show_diff_dest_is_source(mock_source_tree, capsys):
    # skills_dir pointing straight at the sources: report, don't propose replace
    config = Config(
        skills=AssetSources(sources=[mock_source_tree["skills_dir"]]),
        tools={
            "tool-a": ToolConfig(skills_dir=mock_source_tree["skills_dir"]),
        },
    )
    show_diff(config, None, {"skills"})
    out = capsys.readouterr().out
    assert "source directory itself" in out
    assert "will be replaced" not in out


def test_show_diff_legacy_copy_dest_only_file(minimal_config: Config, capsys):
    tc = minimal_config.tools["tool-a"]
    dest = tc.skills_dir / "code-review"
    dest.mkdir()
    (dest / "SKILL.md").write_text("# Code Review\nReview code carefully.\n")
    (dest / "local-notes.md").write_text("only in dest\n")
    show_diff(minimal_config, None, {"skills"})
    out = capsys.readouterr().out
    assert "will be removed" in out
    assert "local-notes.md" in out


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


def test_show_status_symlink_shows_target(minimal_config: Config, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    deploy(minimal_config, None, {"skills"}, dry_run=False)
    capsys.readouterr()  # discard deploy output — assert on show_status alone
    show_status(minimal_config)
    out = capsys.readouterr().out
    assert "Skills (" in out
    assert "code-review ->" in out
    assert "BROKEN" not in out


def test_show_status_broken_symlink(minimal_config: Config, tmp_path: Path, capsys):
    tc = minimal_config.tools["tool-a"]
    dest = tc.skills_dir / "code-review"
    dest.symlink_to(tmp_path / "gone", target_is_directory=True)
    show_status(minimal_config)
    out = capsys.readouterr().out
    assert "code-review ->" in out
    assert "BROKEN" in out


def test_show_status_legacy_copy_flagged(minimal_config: Config, capsys):
    tc = minimal_config.tools["tool-a"]
    dest = tc.skills_dir / "code-review"
    dest.mkdir()
    (dest / "SKILL.md").write_text("stale copy\n")
    show_status(minimal_config)
    out = capsys.readouterr().out
    assert "not a symlink" in out


def test_show_status_stray_file_listed(minimal_config: Config, capsys):
    tc = minimal_config.tools["tool-a"]
    (tc.skills_dir / "stray-notes.md").write_text("not a skill\n")
    (tc.skills_dir / ".gitkeep").write_text("")
    show_status(minimal_config)
    out = capsys.readouterr().out
    assert "stray-notes.md (file, not a symlink)" in out
    assert ".gitkeep" not in out  # hidden files stay hidden
    assert "(empty)" not in out.split("Subagents")[0]  # skills block isn't "(empty)"
