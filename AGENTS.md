# marks-markdown-manager (mmm)

A Python 3 CLI tool that distributes AI tool configuration (global context, skills, subagents) from a canonical source to the correct directories for Windsurf, Gemini CLI, Codex CLI, and Claude Code.

## What it does

`mmm` reads a YAML config file specifying:
- **Context sources**: markdown files to concatenate into a single global context file
- **Skills sources**: directories containing `SKILL.md` files
- **Subagents sources**: directories containing `SKILL.md` files for subagents
- **Tool targets**: where to copy each type for each AI tool

Before deploying, it can run an AI-powered dedup check that identifies overlapping or duplicated content across sources.

## Getting started

### 1. Install (one-time setup)

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

After this, you only need to activate the venv before running `mmm`:

```bash
source venv/bin/activate
```

Re-run `pip install -e .` only if you change `pyproject.toml` (e.g., add a dependency). Code changes in `src/mmm/` are picked up automatically since it's an editable install.

### 2. Create your source content

Organize your canonical AI configuration files:

```
~/my-ai-config/
├── context/
│   ├── persona.md             # global persona / behavior instructions
│   └── coding-standards.md    # coding rules applied everywhere
├── skills/
│   └── code-review/
│       └── SKILL.md           # each skill is a directory with a SKILL.md
└── subagents/
    └── researcher/
        └── SKILL.md
```

### 3. Create your config file

```bash
cp mmm.yaml.example ~/mmm.yaml
```

Edit `~/mmm.yaml` to:
- Point `sources` at your actual content directories
- Set `ai_command` to your preferred AI CLI (e.g., `gemini`, `claude`)
- Adjust tool target directories if needed (defaults in the example cover standard locations)

### 4. Deploy

```bash
source venv/bin/activate

# Preview what would happen without writing anything
mmm deploy --config ~/mmm.yaml --dry-run --skip-dedup

# Deploy for real with AI dedup check
mmm deploy --config ~/mmm.yaml

# Deploy without dedup check
mmm deploy --config ~/mmm.yaml --skip-dedup

# Deploy only skills to a specific tool
mmm deploy --config ~/mmm.yaml --type skills --tools claude

# Check what's currently deployed
mmm status --config ~/mmm.yaml
```

The tool checks that each tool's base directory (e.g., `~/.gemini/`, `~/.codex/`, `~/.claude/`, `~/.codeium/windsurf/`) exists before copying. Tools not installed on your machine are skipped automatically.

### 5. Update after changes

Edit your source files, then re-run `mmm deploy`. It will ask before overwriting existing files.

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
