# marks-markdown-manager (mmm)

A Python 3 CLI tool that distributes AI tool configuration (global context, skills, subagents) from a canonical source to the correct directories for Windsurf, Gemini CLI, Codex CLI, and Claude Code.

## Architecture

```
src/mmm/
├── cli.py        — argparse entry point with deploy/check/status subcommands
├── config.py     — YAML config loading into dataclasses (Config, AssetSources, ToolConfig)
├── deployer.py   — file gathering, concatenation, and copying to tool directories
└── dedup.py      — AI dedup skill invocation via subprocess
```

## How deployment works

1. Load config, gather source files for each asset type
2. **Dedup phase** (unless `--skip-dedup`): copy dedup-checker skill to AI tool's skills dir (with user confirmation), write sources to temp dir, invoke AI command, ask user to proceed
3. **Deploy phase**: for each tool, copy files to target directories (with user confirmation before overwriting)

## Target tool directories

| Tool | Context | Skills | Subagents |
|------|---------|--------|-----------|
| Windsurf | `~/.codeium/windsurf/rules/<filename>` | `~/.codeium/windsurf/skills/<name>/` | N/A |
| Gemini CLI | `~/.gemini/<filename>` | `~/.gemini/skills/<name>/` | `~/.gemini/skills/<name>/` |
| Codex CLI | `~/.codex/<filename>` | `~/.agents/skills/<name>/` | `~/.codex/agents/<name>/` |
| Claude Code | `~/.claude/<filename>` | `~/.claude/skills/<name>/` | `~/.claude/agents/<name>/` |
