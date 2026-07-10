"""Core deployment logic: gather source files, diff against targets, and deploy.

Handles three asset types, each with different deployment strategies:

- **context**: All .md files from source directories are concatenated (with
  ``<!-- Source: path -->`` headers) into a single file per tool.
  Example: 5 markdown files → one ``~/.gemini/GEMINI.md``.

- **skills**: Each skill is a directory containing .md files. A symlink to
  the source directory is created in the tool's skills location, so source
  edits are live immediately without redeploying.
  Example: ``~/.gemini/skills/code-review`` → ``~/rules/skills/code-review/``.

- **subagents**: Same as skills — symlinks to the source directories are
  created in the tool's subagents location.

All write operations that would replace existing content show what would
change first and prompt for confirmation (unless ``dry_run=True``).
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
    shows all lines as additions. Files that exist only in the destination
    are shown as deletions — replacing the destination would remove them.

    Args:
        src_dir: The source directory (what we want to deploy).
        dest_dir: The destination directory (what's currently deployed).

    Returns:
        Combined unified diff string for all changed/new/removed files, or
        empty string if the trees are identical.
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
    # Files that exist only in the destination — lost if it's replaced
    for dest_file in sorted(dest_dir.rglob("*")):
        if not dest_file.is_file():
            continue
        rel = dest_file.relative_to(dest_dir)
        if (src_dir / rel).is_file():
            continue
        lines = dest_file.read_text().splitlines(keepends=True)
        diff = difflib.unified_diff(
            lines, [],
            fromfile=f"{dest_file} (current)",
            tofile=f"{dest_file} (will be removed)",
        )
        parts.append("".join(diff))
    return "\n".join(parts)


def _classify_dest(src_dir: Path, dest: Path) -> str:
    """Classify what currently occupies an asset deploy destination.

    Checks ``is_symlink()`` before ``exists()`` because a broken symlink
    reports ``is_symlink() == True`` but ``exists() == False`` (``exists()``
    follows the link). Link correctness is compared via ``resolve()`` on both
    sides, never ``samefile()``, which raises on broken links.

    Args:
        src_dir: The source directory the symlink should point to.
        dest: The destination path to classify.

    Returns:
        One of ``'missing'`` (nothing there), ``'linked'`` (symlink already
        pointing at src_dir), ``'wrong-link'`` (symlink to somewhere else),
        ``'broken-link'`` (symlink whose target is gone), ``'self'`` (dest IS
        the source directory — e.g. the tool's target dir points straight at
        the sources, possibly through a symlinked parent), ``'copy'`` (a real
        directory — a legacy copy from before symlink deployment), or
        ``'file'`` (a regular file).
    """
    if dest.is_symlink():           # True even when the link target is gone
        if not dest.exists():       # exists() follows the link
            return "broken-link"
        if dest.resolve() == src_dir.resolve():
            return "linked"
        return "wrong-link"
    if dest.is_dir():
        # A real dir that resolves to the source is the source itself
        # (same path, or reached through a symlinked parent). Never treat
        # it as a replaceable copy: removing it would destroy the source.
        if dest.resolve() == src_dir.resolve():
            return "self"
        return "copy"
    if dest.exists():
        return "file"
    return "missing"


def _remove_dest(dest: Path) -> None:
    """Remove whatever occupies a deploy destination, symlink-safely.

    Symlinks and regular files are ``unlink()``-ed; only real directories go
    through ``shutil.rmtree`` (rmtree on a symlink raises, and following the
    link would delete source content).

    Args:
        dest: The destination path to remove. Missing paths are a no-op.
    """
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)


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
    assume_yes: bool = False,
) -> None:
    """Deploy the selected asset types to all enabled tools.

    Iterates over each tool in the config, skipping tools not on this machine
    or not in the tools_filter. For each tool, deploys context, skills, and/or
    subagents based on the type_filter.

    Args:
        config: The loaded mmm configuration.
        tools_filter: If provided, only deploy to these tool names
            (e.g. ["gemini", "claude"]). None means deploy to all.
        type_filter: Set of asset types to deploy, e.g. {"context", "skills"}.
        dry_run: If True, show what would happen but don't write anything.
        assume_yes: If True, skip the interactive overwrite/replace
            confirmation prompts and proceed automatically.
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
                _deploy_context(content, tool_name, tool_config, dry_run, assume_yes)
            else:
                print(f"[{tool_name}] No context files found to deploy")

        # Skills
        if "skills" in type_filter and tool_config.skills_dir:
            dirs = gather_asset_dirs(config.skills)
            if dirs:
                _deploy_assets(dirs, tool_config.skills_dir, tool_name, "skill", dry_run, assume_yes)
            else:
                print(f"[{tool_name}] No skill directories found to deploy")

        # Subagents
        if "subagents" in type_filter and tool_config.subagents_dir:
            dirs = gather_asset_dirs(config.subagents)
            if dirs:
                _deploy_assets(dirs, tool_config.subagents_dir, tool_name, "subagent", dry_run, assume_yes)
            else:
                print(f"[{tool_name}] No subagent directories found to deploy")


def _deploy_context(
    content: str,
    tool_name: str,
    tool_config: ToolConfig,
    dry_run: bool,
    assume_yes: bool = False,
) -> None:
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
        assume_yes: If True, skip the overwrite confirmation prompt and
            overwrite automatically.
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
        if not dry_run and not assume_yes:
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
    assume_yes: bool = False,
) -> None:
    """Symlink skill or subagent source directories into a tool's target location.

    Each source directory gets a symlink in ``target_dir`` under its own name,
    pointing at the resolved (absolute) source path. For example, if ``dirs``
    contains ``~/rules/skills/code-review/`` and ``target_dir`` is
    ``~/.gemini/skills/``, the result is a symlink
    ``~/.gemini/skills/code-review -> /home/user/rules/skills/code-review``.
    Source edits are therefore live immediately; re-running deploy on an
    already-linked asset is a no-op (idempotent).

    Anything else at the destination — a legacy copied directory from before
    symlink deployment, a symlink pointing elsewhere, a broken symlink, or a
    regular file — is described and replaced only after user confirmation.
    A destination that is the source directory itself (the target dir points
    straight at the sources, possibly through a symlinked parent) is never
    touched. Skips source directories that are empty or contain only
    whitespace files.

    Args:
        dirs: Source directories to deploy (output of ``gather_asset_dirs()``).
        target_dir: Parent directory to link into, e.g. ``~/.gemini/skills/``.
        tool_name: Display name for log messages, e.g. "gemini".
        asset_type: "skill" or "subagent" — used in log messages.
        dry_run: If True, show what would happen but don't write anything.
        assume_yes: If True, skip the replace confirmation prompt and
            replace the destination automatically.
    """
    for src_dir in dirs:
        # Skip if source directory has no real content
        src_files = [f for f in src_dir.rglob("*") if f.is_file()]
        if not src_files or all(f.read_text().strip() == "" for f in src_files):
            print(f"[{tool_name}] Skipping {asset_type} {src_dir.name} — source content is empty")
            continue

        dest = target_dir / src_dir.name
        # Resolve to an absolute path so links work regardless of cwd
        # (config allows relative source paths like ./mock/skills/)
        link_target = src_dir.resolve()
        state = _classify_dest(src_dir, dest)

        if state == "linked":
            print(f"[{tool_name}] {asset_type} {src_dir.name}: no changes (symlink up to date)")
            continue
        if state == "self":
            print(
                f"[{tool_name}] {asset_type} {src_dir.name}: destination is the "
                f"source directory itself — nothing to link"
            )
            continue
        if state == "missing":
            print(f"[{tool_name}] Linking {asset_type} {dest} -> {link_target}")
        else:
            if state == "copy":
                print(
                    f"[{tool_name}] {asset_type} {src_dir.name}: existing directory "
                    f"will be replaced by symlink -> {link_target}"
                )
                diff = _diff_tree(src_dir, dest)
                print(diff if diff else f"[{tool_name}] (contents identical)")
            elif state in ("wrong-link", "broken-link"):
                label = "broken symlink" if state == "broken-link" else "symlink"
                print(
                    f"[{tool_name}] {asset_type} {src_dir.name}: {label} currently "
                    f"-> {dest.readlink()}, will repoint to {link_target}"
                )
            else:  # file
                print(
                    f"[{tool_name}] {asset_type} {src_dir.name}: existing file "
                    f"will be replaced by symlink -> {link_target}"
                )
            if not dry_run and not assume_yes:
                answer = input(f"[{tool_name}] Replace {dest} with symlink? [Y/n] ").strip().lower()
                if answer and answer != "y":
                    print(f"[{tool_name}] Skipping {asset_type} {src_dir.name}")
                    continue

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            _remove_dest(dest)
            dest.symlink_to(link_target, target_is_directory=True)


def _show_asset_diff(
    dirs: List[Path],
    target_dir: Path,
    tool_name: str,
    asset_label: str,
) -> None:
    """Report the deploy state of each asset destination without writing.

    For each source directory, classifies the destination and prints what a
    deploy would do: nothing (already linked), create a symlink (missing),
    replace a legacy copied directory (with a content diff), repoint a wrong
    or broken symlink, or replace a regular file.

    Args:
        dirs: Source directories to report on (output of ``gather_asset_dirs()``).
        target_dir: Parent directory the symlinks live in, e.g. ``~/.gemini/skills/``.
        tool_name: Display name for log messages, e.g. "gemini".
        asset_label: "Skill" or "Subagent" — used in log messages.
    """
    for src_dir in dirs:
        dest = target_dir / src_dir.name
        state = _classify_dest(src_dir, dest)
        if state == "linked":
            print(f"[{tool_name}] {asset_label} {src_dir.name}: no changes")
        elif state == "self":
            print(
                f"[{tool_name}] {asset_label} {src_dir.name}: destination is the "
                f"source directory itself — nothing to deploy"
            )
        elif state == "missing":
            print(
                f"[{tool_name}] {asset_label} {src_dir.name}: new — "
                f"will create symlink {dest} -> {src_dir.resolve()}"
            )
        elif state == "copy":
            print(
                f"[{tool_name}] {asset_label} {src_dir.name}: directory (legacy copy) — "
                f"will be replaced by symlink -> {src_dir.resolve()}"
            )
            diff = _diff_tree(src_dir, dest)
            if diff:
                print(diff)
        elif state in ("wrong-link", "broken-link"):
            broken = " (broken)" if state == "broken-link" else ""
            print(
                f"[{tool_name}] {asset_label} {src_dir.name}: symlink -> "
                f"{dest.readlink()}{broken} — will repoint to {src_dir.resolve()}"
            )
        else:  # file
            print(
                f"[{tool_name}] {asset_label} {src_dir.name}: file — "
                f"will be replaced by symlink"
            )


def show_diff(
    config: Config,
    tools_filter: Optional[List[str]],
    type_filter: Set[str],
) -> None:
    """Show what would change in target repos without deploying.

    Same iteration logic as ``deploy()``, but only prints — never writes to
    disk and never prompts for confirmation. Context targets get a unified
    content diff; skill/subagent targets get a state-based report (already
    linked, new symlink, legacy copy to replace, wrong/broken symlink to
    repoint, or file to replace).

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
            _show_asset_diff(dirs, tool_config.skills_dir, tool_name, "Skill")

        # Subagents
        if "subagents" in type_filter and tool_config.subagents_dir:
            dirs = gather_asset_dirs(config.subagents)
            _show_asset_diff(dirs, tool_config.subagents_dir, tool_name, "Subagent")


def _show_asset_status(label: str, asset_dir: Path) -> None:
    """Print one status block for a tool's skills or subagents directory.

    Lists each entry on its own line: symlinks show their target (flagged
    ``(BROKEN)`` when the target is gone), real directories are flagged as
    probable legacy copies, and stray regular files are flagged too (hidden
    files like ``.gitkeep`` are skipped). Checks ``is_symlink()`` before
    anything else — filtering on ``is_dir()`` would silently hide broken
    links.

    Args:
        label: "Skills" or "Subagents" — used as the block header.
        asset_dir: The tool's deployed skills/subagents directory.
    """
    if not asset_dir.exists():
        print(f"  {label}: {asset_dir} (directory not found)")
        return
    lines = []
    for entry in sorted(asset_dir.iterdir()):
        if entry.is_symlink():
            broken = " (BROKEN)" if not entry.exists() else ""
            lines.append(f"    {entry.name} -> {entry.readlink()}{broken}")
        elif entry.is_dir():
            lines.append(f"    {entry.name} (directory, not a symlink — legacy copy?)")
        elif not entry.name.startswith("."):
            lines.append(f"    {entry.name} (file, not a symlink)")
    if lines:
        print(f"  {label} ({asset_dir}):")
        for line in lines:
            print(line)
    else:
        print(f"  {label} ({asset_dir}): (empty)")


def show_status(config: Config) -> None:
    """Show what is currently deployed at each tool's target directories.

    For each tool, reports:
    - Context: file path and size in bytes, or "not deployed".
    - Skills: each deployed entry with its symlink target — broken links are
      flagged ``(BROKEN)``, real directories are flagged as probable legacy
      copies — or "empty"/"not found".
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
            _show_asset_status("Skills", tool_config.skills_dir)

        # Subagents
        if tool_config.subagents_dir:
            _show_asset_status("Subagents", tool_config.subagents_dir)
