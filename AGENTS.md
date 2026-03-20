# marks-markdown-manager (mmm)

A Python 3 CLI tool that distributes AI tool configuration (global context, skills, subagents) from a canonical source to the correct directories for Windsurf, Gemini CLI, Codex CLI, and Claude Code.

## What it does

`mmm` reads a YAML config file specifying:
- **Context sources**: markdown files to concatenate into a single global context file
- **Skills sources**: directories containing `SKILL.md` files
- **Subagents sources**: directories containing `SKILL.md` files for subagents
- **Tool targets**: where to copy each type for each AI tool

Before deploying, it can run an AI-powered dedup check that identifies overlapping or duplicated content across sources.

## Architecture

```
src/mmm/
├── cli.py        — argparse entry point with deploy/check/status subcommands
├── config.py     — YAML config loading into dataclasses (Config, AssetSources, ToolConfig)
├── deployer.py   — file gathering, concatenation, and copying to tool directories
└── dedup.py      — AI dedup skill invocation via subprocess
```

## Key files

- `mmm.yaml.example` — example config with all options documented
- `mock-mmm.yaml` — working config with mock data for testing
- `skills/dedup-checker/SKILL.md` — the agent skill used for dedup checking
- `mock/` — sample context, skills, and subagents for testing
- `mock-target/` — empty target directories for test deployments

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

## Testing with mock data

```bash
pip install -e .
mmm deploy --config mock-mmm.yaml --skip-dedup    # deploy mock data
mmm status --config mock-mmm.yaml                  # see what's deployed
mmm deploy --config mock-mmm.yaml --dry-run        # preview without writing
```

## Dependencies

- Python >= 3.9
- PyYAML >= 6.0
