# marks-markdown-manager (mmm)

A CLI tool for distributing AI tool configuration across multiple AI coding assistants.

## WARNING

**I have not yet dogfooded and tested this thoroughly enough to have faith that it works well!**

## Problems it solves

**1. Distribution across tools**

Skills, subagents, and global context (e.g. `AGENTS.md`) need to reach multiple AI tools — Claude Code, Windsurf, Gemini CLI, Codex CLI, etc. — each with their own directory conventions. Maintaining separate copies manually is error-prone and tedious. `mmm` keeps one canonical source and deploys to all targets.

**2. Control over many sources**

An engineer may have multiple potential sources for these assets (personal, team, org-wide, project-specific). `mmm` gives explicit control over which sources are active and what gets deployed, so you're never guessing what's actually loaded into your tools.

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

## Key files

- `mmm.yaml.example` — example config with all options documented
- `mock-mmm.yaml` — working config with mock data for testing
- `skills/dedup-checker/SKILL.md` — the agent skill used for dedup checking
- `mock/` — sample context, skills, and subagents for testing
- `mock-target/` — empty target directories for test deployments

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

## License

MIT
