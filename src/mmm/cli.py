"""Command-line interface for mmm.

Provides three subcommands:

- ``deploy``: Copy assets from source directories to each tool's target location.
- ``diff``: Preview what would change without writing anything.
- ``status``: Show what is currently deployed at each tool's target directories.

Example invocations::

    mmm deploy --config mmm.yaml --dry-run
    mmm diff --config mmm.yaml --tools gemini,claude
    mmm status --config mmm.yaml
"""

from __future__ import annotations

import argparse
import sys

from mmm.config import load_config
from mmm.deployer import deploy, show_diff, show_status


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser with deploy, diff, and status subcommands.

    Example usages the parser supports::

        mmm deploy --config mmm.yaml
        mmm deploy --config mmm.yaml --dry-run --type skills --tools gemini,claude
        mmm diff --config mmm.yaml --type context
        mmm status --config mmm.yaml

    Returns:
        A configured ArgumentParser ready to parse sys.argv.
    """
    parser = argparse.ArgumentParser(
        prog="mmm",
        description="Distribute AI tool configuration across Windsurf, Gemini CLI, Codex CLI, and Claude Code",
    )
    sub = parser.add_subparsers(dest="command")

    # deploy
    dp = sub.add_parser("deploy", help="Deploy context, skills, and subagents to AI tools")
    dp.add_argument("--config", required=True, help="Path to mmm.yaml config file")
    dp.add_argument("--dry-run", action="store_true", help="Print what would be copied without writing")
    dp.add_argument("--type", choices=["context", "skills", "subagents"], help="Deploy only this asset type")
    dp.add_argument("--tools", help="Comma-separated list of tools to deploy to (e.g. gemini,claude)")

    # diff
    df = sub.add_parser("diff", help="Show what would change in target repos before deploying")
    df.add_argument("--config", required=True, help="Path to mmm.yaml config file")
    df.add_argument("--type", choices=["context", "skills", "subagents"], help="Diff only this asset type")
    df.add_argument("--tools", help="Comma-separated list of tools to diff (e.g. gemini,claude)")

    # status
    st = sub.add_parser("status", help="Show what is currently deployed at each tool's target directories")
    st.add_argument("--config", required=True, help="Path to mmm.yaml config file")

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse CLI args, load config, and dispatch to the appropriate action.

    Supports two filters to narrow what gets deployed or diffed:

    - ``--tools``: Comma-separated tool names, e.g. ``--tools gemini,claude``
      limits operations to just those tools.
    - ``--type``: A single asset type (``context``, ``skills``, or ``subagents``)
      to operate on. Defaults to all three.

    Args:
        argv: Command-line arguments to parse. Defaults to sys.argv if None.
            Primarily exists so tests can call ``main(["deploy", "--config", ...])``
            without monkeypatching sys.argv.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)
    tools_filter = None
    if hasattr(args, "tools") and args.tools:
        tools_filter = [t.strip() for t in args.tools.split(",")]

    type_filter = getattr(args, "type", None)

    if args.command == "deploy":
        approved_types = {"context", "skills", "subagents"}
        if type_filter:
            approved_types = {type_filter}

        deploy(config, tools_filter=tools_filter, type_filter=approved_types, dry_run=args.dry_run)

    elif args.command == "diff":
        approved_types = {"context", "skills", "subagents"}
        if type_filter:
            approved_types = {type_filter}
        show_diff(config, tools_filter=tools_filter, type_filter=approved_types)

    elif args.command == "status":
        show_status(config)
