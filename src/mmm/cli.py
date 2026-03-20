from __future__ import annotations

import argparse
import sys

from mmm.config import load_config
from mmm.deployer import deploy, show_status
from mmm.dedup import run_dedup_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mmm",
        description="Distribute AI tool configuration across Windsurf, Gemini CLI, Codex CLI, and Claude Code",
    )
    sub = parser.add_subparsers(dest="command")

    # deploy
    dp = sub.add_parser("deploy", help="Deploy context, skills, and subagents to AI tools")
    dp.add_argument("--config", required=True, help="Path to mmm.yaml config file")
    dp.add_argument("--dry-run", action="store_true", help="Print what would be copied without writing")
    dp.add_argument("--skip-dedup", action="store_true", help="Skip AI dedup check before deploying")
    dp.add_argument("--type", choices=["context", "skills", "subagents"], help="Deploy only this asset type")
    dp.add_argument("--tools", help="Comma-separated list of tools to deploy to (e.g. gemini,claude)")

    # check
    ck = sub.add_parser("check", help="Run dedup check without deploying")
    ck.add_argument("--config", required=True, help="Path to mmm.yaml config file")
    ck.add_argument("--type", choices=["context", "skills", "subagents"], help="Check only this asset type")

    # status
    st = sub.add_parser("status", help="Show what is currently deployed at each tool's target directories")
    st.add_argument("--config", required=True, help="Path to mmm.yaml config file")

    return parser


def main(argv: list[str] | None = None) -> None:
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
        # Dedup phase
        approved_types = {"context", "skills", "subagents"}
        if type_filter:
            approved_types = {type_filter}

        if not args.skip_dedup:
            approved_types = run_dedup_checks(config, approved_types)

        if not approved_types:
            print("All asset types were declined. Nothing to deploy.")
            return

        deploy(config, tools_filter=tools_filter, type_filter=approved_types, dry_run=args.dry_run)

    elif args.command == "check":
        types_to_check = {"context", "skills", "subagents"}
        if type_filter:
            types_to_check = {type_filter}
        run_dedup_checks(config, types_to_check)

    elif args.command == "status":
        show_status(config)
