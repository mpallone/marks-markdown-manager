from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Set

from mmm.config import Config
from mmm.deployer import concatenate_files, gather_asset_dirs, gather_context_files


# Path to the dedup-checker skill shipped with this repo
_DEDUP_SKILL_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "dedup-checker"


def _copy_dedup_skill(config: Config) -> bool:
    """Copy the dedup-checker skill to the AI tool's skills dir. Returns True if copied."""
    if not _DEDUP_SKILL_DIR.exists():
        print("Warning: dedup-checker skill not found in repo, skipping skill copy", file=sys.stderr)
        return False

    if not config.ai_skills_dir:
        print("Warning: ai_skills_dir not configured, skipping dedup-checker skill copy", file=sys.stderr)
        print("Set ai_skills_dir in your config to the skills directory for your ai_command tool", file=sys.stderr)
        return False

    dest = config.ai_skills_dir / "dedup-checker"
    if dest.exists():
        return True  # Already there

    answer = input(f"Copy dedup-checker skill to {dest}? [Y/n] ").strip().lower()
    if answer and answer != "y":
        print("Skipping dedup-checker skill copy")
        return False

    print(f"Copying dedup-checker skill -> {dest}")
    config.ai_skills_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_DEDUP_SKILL_DIR, dest)
    return True


def _gather_content(config: Config, asset_type: str) -> str | None:
    """Gather all source content for a given asset type."""
    if asset_type == "context":
        files = gather_context_files(config.context)
        if not files:
            return None
        return concatenate_files(files)
    elif asset_type in ("skills", "subagents"):
        sources = config.skills if asset_type == "skills" else config.subagents
        dirs = gather_asset_dirs(sources)
        if not dirs:
            return None
        # Concatenate all .md files with path headers
        all_files: List[Path] = []
        for d in dirs:
            for md in sorted(d.rglob("*.md")):
                if md.is_file():
                    all_files.append(md)
        if not all_files:
            return None
        return concatenate_files(all_files)
    return None


def run_dedup_checks(config: Config, asset_types: Set[str]) -> Set[str]:
    """Run dedup checks for each asset type. Returns set of approved types."""
    if not config.ai_command:
        print("Warning: no ai_command configured, skipping dedup checks", file=sys.stderr)
        return asset_types

    # Check if AI command is available
    if not shutil.which(config.ai_command):
        print(f"Warning: ai_command '{config.ai_command}' not found on PATH, skipping dedup checks", file=sys.stderr)
        return asset_types

    # Copy dedup skill to a tool's skills dir
    _copy_dedup_skill(config)

    approved = set()
    for asset_type in sorted(asset_types):
        content = _gather_content(config, asset_type)
        if not content:
            print(f"No {asset_type} sources found, skipping dedup check")
            approved.add(asset_type)
            continue

        print(f"\n--- Dedup check: {asset_type} ---")

        # Write content to a temp directory inside the current working directory
        # so the AI tool can access it (some tools restrict access to the project dir)
        with tempfile.TemporaryDirectory(prefix=f"mmm-dedup-{asset_type}-", dir=".") as tmpdir:
            content_file = Path(tmpdir) / f"{asset_type}-content.md"
            content_file.write_text(content)

            prompt = (
                f"Run the dedup-checker skill. Check the following {asset_type} content "
                f"in {content_file} for overlaps, duplications, and very-similar-looking content. "
                f"Report any issues found with file paths and suggestions for consolidation."
            )

            cmd = [config.ai_command] + config.ai_command_args + [prompt]
            print(f"Running: {' '.join(cmd)}")

            try:
                subprocess.run(cmd, check=False)
            except KeyboardInterrupt:
                print("\nDedup check interrupted")
                return approved

        answer = input(f"\nProceed with {asset_type} deployment? [Y/n] ").strip().lower()
        if not answer or answer == "y":
            approved.add(asset_type)
        else:
            print(f"Skipping {asset_type} deployment")

    return approved
