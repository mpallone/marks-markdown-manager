# marks-markdown-manager (mmm)

A Python 3 CLI tool that distributes AI tool configuration (global context, skills, subagents) from a canonical source to the correct directories for Windsurf, Gemini CLI, Codex CLI, and Claude Code.

## Architecture

```
src/mmm/
├── cli.py        — argparse entry point with deploy/status subcommands
├── config.py     — YAML config loading into dataclasses (Config, AssetSources, ToolConfig)
└── deployer.py   — file gathering, concatenation, and copying to tool directories
```

## How deployment works

1. Load config, gather source files for each asset type
2. **Deploy phase**: for each tool, copy files to target directories (with user confirmation before overwriting)

## Target tool directories

| Tool | Context | Skills | Subagents |
|------|---------|--------|-----------|
| Windsurf | `~/.codeium/windsurf/rules/<filename>` | `~/.codeium/windsurf/skills/<name>/` | N/A |
| Gemini CLI | `~/.gemini/<filename>` | `~/.gemini/skills/<name>/` | `~/.gemini/skills/<name>/` |
| Codex CLI | `~/.codex/<filename>` | `~/.agents/skills/<name>/` | `~/.codex/agents/<name>/` |
| Claude Code | `~/.claude/<filename>` | `~/.claude/skills/<name>/` | `~/.claude/agents/<name>/` |
