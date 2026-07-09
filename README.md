# marks-markdown-manager (mmm)

A CLI tool for distributing AI tool configuration across multiple AI coding assistants.

## Example: combining personal and work sources

Every AI coding assistant — Claude Code, Gemini CLI, Codex CLI, Windsurf —
wants the same kinds of configuration (global context, skills, subagents),
but each expects it in its own directory, under its own filename. Meanwhile,
the content itself rarely lives in one place. `mmm` keeps your sources
wherever they naturally live, then combines and deploys them to every tool.

For example, suppose you keep a personal repo with generic preferences and a
work repo with employer-specific material:

```
~/personal-ai-config/            # personal repo
├── AGENTS.md                    # generic: writing style, tone, general preferences
└── skills/
    └── code-review/
        └── SKILL.md

~/work-ai-config/                # work repo
├── AGENTS.md                    # work-specific: team conventions, internal terminology
└── skills/
    └── deploy-runbook/
        └── SKILL.md
```

A config that combines them (tool targets omitted — use the `tools:` section
from `mmm.yaml.example`):

```yaml
context:
  sources:
    - ~/personal-ai-config/AGENTS.md   # generic writing style and preferences
    - ~/work-ai-config/AGENTS.md       # work-specific standards
  exclude: []

skills:
  sources:
    - ~/personal-ai-config/skills/     # skills from your personal repo
    - ~/work-ai-config/skills/         # skills from your work repo
  exclude: []
```

On `mmm deploy`:

- The two `AGENTS.md` files are concatenated, in the order listed, into a
  single context file per tool (`~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`,
  `~/.codex/AGENTS.md`, ...). Each section is prefixed with a
  `<!-- Source: ... -->` comment so you can always tell which repo a rule
  came from.
- Skills are gathered from both repos and each is copied as its own directory
  into every tool's skills location, so `code-review/` and `deploy-runbook/`
  end up side by side in e.g. `~/.claude/skills/`.

No copy-pasting between tool directories, and no wondering which copy is
current — edit the source repos and redeploy.

## Problems it solves

**1. Distribution across tools**

Skills, subagents, and global context (e.g. `AGENTS.md`) need to reach multiple AI tools — Claude Code, Windsurf, Gemini CLI, Codex CLI, etc. — each with their own directory conventions. Maintaining separate copies manually is error-prone and tedious. `mmm` keeps one canonical source and deploys to all targets.

**2. Control over many sources**

An engineer may have multiple potential sources for these assets (personal, team, org-wide, project-specific). `mmm` gives explicit control over which sources are active and what gets deployed, so you're never guessing what's actually loaded into your tools.

## Getting started

### 1. Install (one-time setup)

Recommended for daily use:

```bash
uv tool install --editable /Users/mpallone/src/mpallone/marks-markdown-manager
```

This installs `mmm` on your shell `PATH` without requiring you to create or activate a manual virtualenv. `uv` manages the isolated Python environment for you.

`uv tool` installs executables into:

```bash
/Users/mpallone/.local/bin
```

Make sure that directory is on your `PATH`, then verify the install:

```bash
which mmm
mmm --help
```

If you prefer direct control of the Python environment while developing on this repo, the old manual option still works:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Re-run `uv tool install --editable ...` or `pip install -e .` only if you change package metadata such as `pyproject.toml`. Code changes in `src/mmm/` are picked up automatically because the install is editable.

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
- Adjust tool target directories if needed (defaults in the example cover standard locations)

Context sources can be individual `.md` files or directories, in which case
every `.md` file inside them is included. Skill sources are directories whose
subdirectories each hold one skill. For a concrete two-repo config, see
[the example above](#example-combining-personal-and-work-sources).

### 4. Deploy

```bash
# Preview what would happen without writing anything
mmm deploy --config /path/to/dir/mmm.yaml --dry-run

# Deploy for real
mmm deploy --config /path/to/dir/mmm.yaml

# Deploy only skills to a specific tool
mmm deploy --config /path/to/dir/mmm.yaml --type skills --tools claude

# Check what's currently deployed
mmm status --config /path/to/dir/mmm.yaml
```

If you are already in the directory that contains the config file, a relative path is fine:

```bash
cd /path/to/dir/
mmm deploy --config mmm.yaml
mmm status --config mmm.yaml
```

The tool checks that each tool's base directory (e.g., `~/.gemini/`, `~/.codex/`, `~/.claude/`, `~/.codeium/windsurf/`) exists before copying. Tools not installed on your machine are skipped automatically.

`--config` is required for `deploy` and `status`. Relative config paths resolve from your current working directory. The CLI does not auto-discover `mmm.yaml`.

### 5. Update after changes

Edit your source files, then re-run `mmm deploy`. It will ask before overwriting existing files.

## Key files

- `mmm.yaml.example` — example config with all options documented
- `mock-mmm.yaml` — working config with mock data for testing
- `mock/` — sample context, skills, and subagents for testing
- `mock-target/` — empty target directories for test deployments

## Testing with mock data

```bash
uv tool install --editable /Users/mpallone/src/mpallone/marks-markdown-manager
mmm deploy --config mock-mmm.yaml    # deploy mock data
mmm status --config mock-mmm.yaml    # see what's deployed
mmm deploy --config mock-mmm.yaml --dry-run    # preview without writing
```

## Dependencies

- Python >= 3.9
- PyYAML >= 6.0

## License

MIT
