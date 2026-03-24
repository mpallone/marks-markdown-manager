"""Core deployment logic: gather source files, diff against targets, and deploy.

Handles three asset types, each with different deployment strategies:

- **context**: All .md files from source directories are concatenated (with
  ``<!-- Source: path -->`` headers) into a single file per tool.
  Example: 5 markdown files → one ``~/.gemini/GEMINI.md``.

- **skills**: Each skill is a directory containing .md files. Directories are
  copied wholesale into the tool's skills location via ``shutil.copytree``.
  Example: ``~/rules/skills/code-review/`` → ``~/.gemini/skills/code-review/``.

- **subagents**: Same as skills — directory trees copied to the tool's
  subagents location.

All write operations show a unified diff first and prompt for confirmation
(unless ``dry_run=True``).
"""

from __future__ import annotations

import difflib
import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Set

from mmm.config import AssetSources, Config, ToolConfig


def gather_context_files(sources: AssetSources) -> List[Path]:
    """Collect all .md files from source directories and files, applying excludes.

    Walks each source path: if it's a single .md file, includes it directly;
    if it's a directory, recursively globs for ``*.md`` files. Files whose
    names match any exclusion pattern are skipped.

    Example: given sources pointing to ``~/rules/context/`` containing
    ``setup.md`` and ``draft-ideas.md`` with exclude ``["draft-*"]``,
    returns ``[Path("~/rules/context/setup.md")]``.

    Args:
        sources: An AssetSources with paths to scan and patterns to exclude.

    Returns:
        Sorted list of Path objects pointing to .md files.
    """
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
    """Find directories containing at least one .md file, applying excludes.

    For each source path, checks if the directory itself contains .md files
    (in which case it's treated as an asset directory). If not, scans its
    immediate children for subdirectories that do contain .md files.

    Example: given ``~/rules/skills/`` containing subdirs ``code-review/``
    (has .md files) and ``empty-skill/`` (no .md files), returns
    ``[Path("~/rules/skills/code-review/")]``.

    Args:
        sources: An AssetSources with paths to scan and patterns to exclude.

    Returns:
        List of directory Paths, each containing at least one .md file.
    """
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
    """Check if a directory contains at least one .md file (non-recursive).

    Args:
        directory: Path to the directory to check.

    Returns:
        True if any immediate child is a .md file.
    """
    return any(f.is_file() and f.suffix == ".md" for f in directory.iterdir())


def _is_excluded(name: str, excludes: List[str]) -> bool:
    """Check if a filename matches any fnmatch exclusion pattern.

    Example::

        _is_excluded("draft-ideas.md", ["draft-*", "*.tmp"])  # True
        _is_excluded("setup-guide.md", ["draft-*", "*.tmp"])   # False

    Args:
        name: The filename (not full path) to check, e.g. "draft-ideas.md".
        excludes: List of fnmatch glob patterns, e.g. ["draft-*", "*.tmp"].

    Returns:
        True if the name matches any pattern in the excludes list.
    """
    return any(fnmatch(name, pat) for pat in excludes)


def concatenate_files(files: List[Path]) -> str:
    """Join multiple .md files into a single string, each prefixed with a source header.

    Each file's content is preceded by an HTML comment identifying its origin,
    e.g. ``<!-- Source: /home/user/rules/context/setup.md -->``. Files are
    joined with newlines.

    Args:
        files: List of Path objects to concatenate.

    Returns:
        A single string with all file contents joined together.
    """
    parts = []
    for f in files:
        parts.append(f"<!-- Source: {f} -->")
        parts.append(f.read_text())
    return "\n".join(parts)


def _format_file_diff(current: str, incoming: str, label: str) -> str:
    """Return a unified diff string between current and incoming content.

    Args:
        current: The existing file content (what's deployed now).
        incoming: The new content that would replace it.
        label: File path used in the diff header (e.g. "~/.gemini/GEMINI.md").

    Returns:
        A unified diff string, or empty string if the contents are identical.
    """
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
    """Compare all files in a source tree against a destination tree.

    Walks the source directory recursively. For each file, if it exists in
    the destination, produces a unified diff. If it's new (not in dest),
    shows all lines as additions.

    Args:
        src_dir: The source directory (what we want to deploy).
        dest_dir: The destination directory (what's currently deployed).

    Returns:
        Combined unified diff string for all changed/new files, or empty
        string if the trees are identical.
    """
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
    """Check if the tool's base directory exists on this machine.

    Used to skip tools that aren't installed. For example, if Gemini CLI
    isn't installed, ``~/.gemini/`` won't exist and we skip deploying to it.

    Args:
        tool_name: Tool name for logging (currently unused but available).
        tool_config: The tool's config — checks if any configured target
            directory (or its parent) exists.

    Returns:
        True if at least one target directory or its parent exists on disk.
    """
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
    """Deploy approved asset types to all enabled tools.

    Iterates over each tool in the config, skipping tools not on this machine
    or not in the tools_filter. For each tool, deploys context, skills, and/or
    subagents based on the type_filter.

    Args:
        config: The loaded mmm configuration.
        tools_filter: If provided, only deploy to these tool names
            (e.g. ["gemini", "claude"]). None means deploy to all.
        type_filter: Set of asset types to deploy, e.g. {"context", "skills"}.
        dry_run: If True, show what would happen but don't write anything.
    """
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
    """Write concatenated context content to a tool's target file.

    Writes the pre-concatenated markdown string to the tool's context file
    (e.g. ``~/.gemini/GEMINI.md``). If the target already exists, shows a
    unified diff and prompts the user to confirm the overwrite. Skips
    deployment if the content is empty or whitespace-only.

    Args:
        content: The concatenated markdown string (output of ``concatenate_files()``).
        tool_name: Display name for log messages, e.g. "gemini".
        tool_config: The tool's deployment config, providing ``context_dir``
            and ``context_filename``.
        dry_run: If True, show what would happen but don't write anything.
    """
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
    """Copy skill or subagent directory trees to a tool's target location.

    Each source directory is copied into ``target_dir`` using its own name.
    For example, if ``dirs`` contains ``~/rules/skills/code-review/`` and
    ``target_dir`` is ``~/.gemini/skills/``, the result is
    ``~/.gemini/skills/code-review/`` (a full copy via ``shutil.copytree``).

    If the destination already exists, shows a unified diff and prompts for
    confirmation. Skips source directories that are empty or contain only
    whitespace files.

    Args:
        dirs: Source directories to deploy (output of ``gather_asset_dirs()``).
        target_dir: Parent directory to copy into, e.g. ``~/.gemini/skills/``.
        tool_name: Display name for log messages, e.g. "gemini".
        asset_type: "skill" or "subagent" — used in log messages.
        dry_run: If True, show what would happen but don't write anything.
    """
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
    """Show what would change in target repos without deploying.

    Same iteration logic as ``deploy()``, but only prints diffs — never
    writes to disk and never prompts for confirmation.

    Args:
        config: The loaded mmm configuration.
        tools_filter: If provided, only diff these tool names. None means all.
        type_filter: Set of asset types to diff, e.g. {"context", "skills"}.
    """
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
    """Show what is currently deployed at each tool's target directories.

    For each tool, reports:
    - Context: file path and size in bytes, or "not deployed".
    - Skills: lists deployed skill directory names, or "empty"/"not found".
    - Subagents: same as skills.

    Args:
        config: The loaded mmm configuration.
    """
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
