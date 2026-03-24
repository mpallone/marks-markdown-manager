from __future__ import annotations

import difflib
import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Set

from mmm.config import AssetSources, Config, ToolConfig


def gather_context_files(sources: AssetSources) -> List[Path]:
    """Collect .md files from source dirs/files, applying excludes."""
    files = []
    for src in sources.sources:
        if src.is_file() and src.suffix == ".md":
            if not _is_excluded(src.name, sources.exclude):
                files.append(src)
        elif src.is_dir():
            for md in sorted(src.rglob("*.md")):
                if md.is_file() and not _is_excluded(md.name, sources.exclude):
                    files.append(md)
    return files


def gather_asset_dirs(sources: AssetSources) -> List[Path]:
    """Find subdirectories containing at least one .md file, applying excludes."""
    dirs = []
    for src in sources.sources:
        if not src.is_dir():
            continue
        # Check if src itself contains .md files
        if _has_md_files(src):
            if not _is_excluded(src.name, sources.exclude):
                dirs.append(src)
            continue
        # Otherwise scan immediate subdirs
        for child in sorted(src.iterdir()):
            if child.is_dir() and _has_md_files(child):
                if not _is_excluded(child.name, sources.exclude):
                    dirs.append(child)
    return dirs


def _has_md_files(directory: Path) -> bool:
    """Check if a directory contains at least one .md file."""
    return any(f.is_file() and f.suffix == ".md" for f in directory.iterdir())


def _is_excluded(name: str, excludes: List[str]) -> bool:
    return any(fnmatch(name, pat) for pat in excludes)


def concatenate_files(files: List[Path]) -> str:
    """Join files with source path headers."""
    parts = []
    for f in files:
        parts.append(f"<!-- Source: {f} -->")
        parts.append(f.read_text())
    return "\n".join(parts)


def _format_file_diff(current: str, incoming: str, label: str) -> str:
    """Return a unified diff string between current and incoming content, or empty if identical."""
    if current == incoming:
        return ""
    current_lines = current.splitlines(keepends=True)
    incoming_lines = incoming.splitlines(keepends=True)
    diff = difflib.unified_diff(
        current_lines,
        incoming_lines,
        fromfile=f"{label} (current)",
        tofile=f"{label} (incoming)",
    )
    return "".join(diff)


def _diff_tree(src_dir: Path, dest_dir: Path) -> str:
    """Compare all files in a source tree against a destination tree. Return combined diff."""
    parts = []
    # Diff files that exist in source
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        dest_file = dest_dir / rel
        incoming = src_file.read_text()
        if dest_file.exists():
            current = dest_file.read_text()
            diff = _format_file_diff(current, incoming, str(dest_file))
            if diff:
                parts.append(diff)
        else:
            # New file — show all lines as additions
            lines = incoming.splitlines(keepends=True)
            diff = difflib.unified_diff(
                [], lines,
                fromfile=f"{dest_file} (new file)",
                tofile=f"{dest_file} (incoming)",
            )
            parts.append("".join(diff))
    return "\n".join(parts)


def _check_tool_base_dir(tool_name: str, tool_config: ToolConfig) -> bool:
    """Check if the tool's base directory exists on the system."""
    # Determine the base dir from whichever target dir is configured
    for d in [tool_config.context_dir, tool_config.skills_dir, tool_config.subagents_dir]:
        if d is not None:
            # Walk up to find the tool's home dir (e.g. ~/.gemini, ~/.codex)
            # For paths like ~/.codeium/windsurf/rules/, we check ~/.codeium/windsurf/
            if d.exists() or d.parent.exists():
                return True
    return False


def deploy(
    config: Config,
    tools_filter: Optional[List[str]],
    type_filter: Set[str],
    dry_run: bool,
) -> None:
    """Deploy approved asset types to all enabled tools."""
    for tool_name, tool_config in config.tools.items():
        if tools_filter and tool_name not in tools_filter:
            continue

        if not _check_tool_base_dir(tool_name, tool_config):
            print(f"[{tool_name}] Skipping — base directory not found on system")
            continue

        print(f"\n=== Deploying to {tool_name} ===")

        # Context
        if "context" in type_filter and tool_config.context_dir and tool_config.context_filename:
            files = gather_context_files(config.context)
            if files:
                content = concatenate_files(files)
                _deploy_context(content, tool_name, tool_config, dry_run)
            else:
                print(f"[{tool_name}] No context files found to deploy")

        # Skills
        if "skills" in type_filter and tool_config.skills_dir:
            dirs = gather_asset_dirs(config.skills)
            if dirs:
                _deploy_assets(dirs, tool_config.skills_dir, tool_name, "skill", dry_run)
            else:
                print(f"[{tool_name}] No skill directories found to deploy")

        # Subagents
        if "subagents" in type_filter and tool_config.subagents_dir:
            dirs = gather_asset_dirs(config.subagents)
            if dirs:
                _deploy_assets(dirs, tool_config.subagents_dir, tool_name, "subagent", dry_run)
            else:
                print(f"[{tool_name}] No subagent directories found to deploy")


def _deploy_context(content: str, tool_name: str, tool_config: ToolConfig, dry_run: bool) -> None:
    target = tool_config.context_dir / tool_config.context_filename

    if not content.strip():
        print(f"[{tool_name}] Skipping context — source content is empty")
        return

    if target.exists():
        current = target.read_text()
        diff = _format_file_diff(current, content, str(target))
        if not diff:
            print(f"[{tool_name}] Context: no changes")
            return
        print(f"[{tool_name}] Context diff for {target}:")
        print(diff)
        if not dry_run:
            answer = input(f"[{tool_name}] Overwrite {target}? [Y/n] ").strip().lower()
            if answer and answer != "y":
                print(f"[{tool_name}] Skipping context deployment")
                return
    else:
        print(f"[{tool_name}] Creating {target}")

    if not dry_run:
        tool_config.context_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def _deploy_assets(
    dirs: List[Path],
    target_dir: Path,
    tool_name: str,
    asset_type: str,
    dry_run: bool,
) -> None:
    for src_dir in dirs:
        # Skip if source directory has no real content
        src_files = [f for f in src_dir.rglob("*") if f.is_file()]
        if not src_files or all(f.read_text().strip() == "" for f in src_files):
            print(f"[{tool_name}] Skipping {asset_type} {src_dir.name} — source content is empty")
            continue

        dest = target_dir / src_dir.name

        if dest.exists():
            diff = _diff_tree(src_dir, dest)
            if not diff:
                print(f"[{tool_name}] {asset_type} {src_dir.name}: no changes")
                continue
            print(f"[{tool_name}] {asset_type} {src_dir.name} diff:")
            print(diff)
            if not dry_run:
                answer = input(f"[{tool_name}] Overwrite {dest}? [Y/n] ").strip().lower()
                if answer and answer != "y":
                    print(f"[{tool_name}] Skipping {asset_type} {src_dir.name}")
                    continue
        else:
            print(f"[{tool_name}] Copying {asset_type} {src_dir} -> {dest}")

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src_dir, dest)


def show_diff(
    config: Config,
    tools_filter: Optional[List[str]],
    type_filter: Set[str],
) -> None:
    """Show what would change in target repos without deploying."""
    for tool_name, tool_config in config.tools.items():
        if tools_filter and tool_name not in tools_filter:
            continue

        if not _check_tool_base_dir(tool_name, tool_config):
            print(f"[{tool_name}] Skipping — base directory not found on system")
            continue

        print(f"\n=== Diff for {tool_name} ===")

        # Context
        if "context" in type_filter and tool_config.context_dir and tool_config.context_filename:
            files = gather_context_files(config.context)
            if files:
                content = concatenate_files(files)
                target = tool_config.context_dir / tool_config.context_filename
                if target.exists():
                    current = target.read_text()
                    diff = _format_file_diff(current, content, str(target))
                    if diff:
                        print(diff)
                    else:
                        print(f"[{tool_name}] Context: no changes")
                else:
                    print(f"[{tool_name}] Context: {target} (new file, {len(content)} bytes)")
            else:
                print(f"[{tool_name}] No context files found")

        # Skills
        if "skills" in type_filter and tool_config.skills_dir:
            dirs = gather_asset_dirs(config.skills)
            for src_dir in dirs:
                dest = tool_config.skills_dir / src_dir.name
                if dest.exists():
                    diff = _diff_tree(src_dir, dest)
                    if diff:
                        print(diff)
                    else:
                        print(f"[{tool_name}] Skill {src_dir.name}: no changes")
                else:
                    print(f"[{tool_name}] Skill {src_dir.name}: new")

        # Subagents
        if "subagents" in type_filter and tool_config.subagents_dir:
            dirs = gather_asset_dirs(config.subagents)
            for src_dir in dirs:
                dest = tool_config.subagents_dir / src_dir.name
                if dest.exists():
                    diff = _diff_tree(src_dir, dest)
                    if diff:
                        print(diff)
                    else:
                        print(f"[{tool_name}] Subagent {src_dir.name}: no changes")
                else:
                    print(f"[{tool_name}] Subagent {src_dir.name}: new")


def show_status(config: Config) -> None:
    """Show what is currently deployed at each tool's target directories."""
    for tool_name, tool_config in config.tools.items():
        print(f"\n=== {tool_name} ===")

        if not _check_tool_base_dir(tool_name, tool_config):
            print("  Base directory not found on system")
            continue

        # Context
        if tool_config.context_dir and tool_config.context_filename:
            target = tool_config.context_dir / tool_config.context_filename
            if target.exists():
                stat = target.stat()
                size = stat.st_size
                print(f"  Context: {target} ({size} bytes)")
            else:
                print(f"  Context: {target} (not deployed)")

        # Skills
        if tool_config.skills_dir:
            if tool_config.skills_dir.exists():
                skills = [d.name for d in sorted(tool_config.skills_dir.iterdir()) if d.is_dir()]
                if skills:
                    print(f"  Skills ({tool_config.skills_dir}): {', '.join(skills)}")
                else:
                    print(f"  Skills ({tool_config.skills_dir}): (empty)")
            else:
                print(f"  Skills: {tool_config.skills_dir} (directory not found)")

        # Subagents
        if tool_config.subagents_dir:
            if tool_config.subagents_dir.exists():
                agents = [d.name for d in sorted(tool_config.subagents_dir.iterdir()) if d.is_dir()]
                if agents:
                    print(f"  Subagents ({tool_config.subagents_dir}): {', '.join(agents)}")
                else:
                    print(f"  Subagents ({tool_config.subagents_dir}): (empty)")
            else:
                print(f"  Subagents: {tool_config.subagents_dir} (directory not found)")
