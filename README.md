# marks-markdown-manager (mmm)

A CLI tool for distributing AI tool configuration across multiple AI coding assistants.

## Example of why this is useful: combining personal and work sources

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

The config file (`mmm.yaml`) has two halves: **what** to deploy (your
sources) and **where** each tool wants it (the targets). Here is a complete,
working config for the layout above, deploying to Claude Code and Gemini CLI:

```yaml
# WHAT to deploy: your sources, in the order they should appear
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

# WHERE each tool expects it — add other tools the same way
# (see mmm.yaml.example for Codex CLI and Windsurf entries)
tools:
  claude:
    context_dir: "~/.claude/"          # combined context becomes ~/.claude/CLAUDE.md
    context_filename: "CLAUDE.md"
    skills_dir: "~/.claude/skills/"    # each skill is symlinked here under its own name
  gemini:
    context_dir: "~/.gemini/"          # same content, Gemini's conventions
    context_filename: "GEMINI.md"
    skills_dir: "~/.gemini/skills/"
```

Run `mmm deploy --config mmm.yaml`, and:

- The two `AGENTS.md` files are concatenated, in the order listed, into a
  single context file per tool: `~/.claude/CLAUDE.md` and `~/.gemini/GEMINI.md`.
  Each section is prefixed with a `<!-- Source: ... -->` comment so you can
  always tell which repo a rule came from.
- Skills are gathered from both repos and each is symlinked as its own entry
  into every tool's skills location, so `code-review/` and `deploy-runbook/`
  end up side by side in `~/.claude/skills/` and `~/.gemini/skills/`.

No copy-pasting between tool directories, and no wondering which copy is
current — the deployed skills are symlinks, so edits to the source repos
are live in every tool immediately.

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
[the example above](#example-of-why-this-is-useful-combining-personal-and-work-sources).

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

The tool checks that each tool's base directory (e.g., `~/.gemini/`, `~/.codex/`, `~/.claude/`, `~/.codeium/windsurf/`) exists before linking. Tools not installed on your machine are skipped automatically.

`--config` is required for `deploy` and `status`. Relative config paths resolve from your current working directory. The CLI does not auto-discover `mmm.yaml`.

### 5. Update after changes

Skills and subagents are deployed as symlinks, so edits to your source files
are live in every tool immediately — no redeploy needed. Re-run `mmm deploy`
only when:

- you add or remove a skill/subagent (new sources get linked; removed
  sources leave stale links behind — see `mmm status`, which flags them
  as `(BROKEN)`), or
- you change context sources — context files are real merged files, so
  they only update on deploy. `mmm` asks before overwriting them.

**Migrating from copies:** versions of `mmm` before symlink deployment
copied skills and subagents into the tool directories. On your first
deploy after upgrading, `mmm` detects those legacy copies, shows how they
differ from your sources, and asks before replacing each one with a
symlink. `mmm status` flags any remaining legacy copies with
`(directory, not a symlink — legacy copy?)`.

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

## Configuration reference

Everything `mmm` does is driven by one YAML file (conventionally `mmm.yaml`).
This section documents every option it supports.

The file has two halves:

- **What to deploy** — the `context`, `skills`, and `subagents` sections.
  Each lists where your source material lives.
- **Where it goes** — the `tools` section. Each entry maps one AI tool to
  the directories that tool reads its configuration from.

Every section and every key is optional. If a section is missing, `mmm`
simply has nothing to do for that asset type — so a config with no `tools:`
section deploys nothing at all. A minimal useful config is one source and
one tool:

```yaml
context:
  sources:
    - ~/my-ai-config/AGENTS.md
tools:
  claude:
    context_dir: "~/.claude/"
    context_filename: "CLAUDE.md"
```

### `context` — markdown files merged into one file per tool

Context is the "always loaded" material: persona, coding standards, general
instructions. At deploy time, all context sources are concatenated into a
**single** markdown file per tool, written to that tool's
`context_dir/context_filename`.

```yaml
context:
  sources:
    - ~/personal-ai-config/AGENTS.md     # a single file
    - ~/work-ai-config/context/          # or a whole directory
  exclude:
    - "draft-*"                          # skip files by name pattern
```

- **`sources`** — a list of paths. Each entry is either a single `.md` file
  (included as-is) or a directory (every `.md` file inside it is included,
  searched recursively, in alphabetical order). Sources are concatenated in
  the order you list them, so put the most general material first.
- **`exclude`** — a list of shell-style glob patterns (`*`, `?`, `[abc]`)
  matched against the **filename only**, not the full path. `draft-*` skips
  `draft-ideas.md` wherever it lives; it will not match on directory names
  like `drafts/`.

In the merged output, each file's content is prefixed with a
`<!-- Source: /path/to/file.md -->` comment so you can always trace a rule
back to the file it came from.

### `skills` and `subagents` — directories symlinked whole

Skills and subagents are not merged — each one is a directory (containing a
`SKILL.md` and any supporting files) that gets symlinked into every tool's
skills/subagents location, keeping its own name. Because the deployed entry
is a symlink back to your source, edits to the source are live in every tool
without redeploying. The two sections behave identically; they only differ
in which target directory they deploy to.

```yaml
skills:
  sources:
    - ~/personal-ai-config/skills/       # a folder of skills: each subdirectory is one skill
    - ~/work-ai-config/one-off-skill/    # or a single skill directory itself
  exclude:
    - "experimental-*"                   # skip skills by directory name

subagents:
  sources:
    - ~/personal-ai-config/subagents/
  exclude: []
```

- **`sources`** — a list of directories. Each entry is either a *folder of
  skills* (its immediate subdirectories are the skills) or a *single skill
  directory* (if the directory itself directly contains `.md` files, it is
  deployed as one skill under its own name). A directory only counts as a
  skill if it has at least one `.md` file directly inside it — deeper
  nesting is not searched.
- **`exclude`** — same glob patterns as above, matched against the **skill's
  directory name**. `experimental-*` skips a skill folder named
  `experimental-parser/`.

If two sources contain a skill with the same directory name, they collide at
the destination: the later one asks to repoint the earlier one's symlink.
Rename one of them if you want both deployed.

### `tools` — where each tool wants its files

Each entry under `tools:` describes one AI tool. The name of the entry
(`claude`, `gemini`, ...) is just a label you choose — it shows up in
`mmm`'s output and is what you pass to `--tools` to target specific tools.
The four keys inside it are what matter:

| Key | What it does | If omitted |
|---|---|---|
| `context_dir` | Directory the merged context file is written into | No context deployed to this tool |
| `context_filename` | Name of that merged file (e.g. `CLAUDE.md`) | No context deployed (both keys are required for context) |
| `skills_dir` | Directory each skill is symlinked into, under its own name | No skills deployed to this tool |
| `subagents_dir` | Same as `skills_dir`, but for subagents | No subagents deployed to this tool |

Only include the keys a tool actually supports. This is how you express
per-tool differences:

```yaml
tools:
  windsurf:
    context_dir: "~/.codeium/windsurf/rules/"
    context_filename: "global-context.md"
    skills_dir: "~/.codeium/windsurf/skills/"
    # no subagents_dir — Windsurf doesn't support subagents,
    # so subagents are simply never deployed to it
  gemini:
    context_dir: "~/.gemini/"
    context_filename: "GEMINI.md"
    skills_dir: "~/.gemini/skills/"
    subagents_dir: "~/.gemini/skills/"   # Gemini reads both from one place —
                                         # pointing both keys at it is fine
```

### Path rules

- `~` is expanded to your home directory in every path.
- Relative paths (like `./mock/context/`) are resolved from the directory
  you run `mmm` in — handy for testing inside a repo, but use `~` or
  absolute paths in your real config so it works from anywhere.
- If a source path doesn't exist, `mmm` prints a warning and carries on.
  This is deliberate: it lets one config serve machines where, say, the
  work repo isn't checked out.

### What happens at deploy time

Safety behavior you get on every run, with no extra configuration:

- **Tools you don't have are skipped.** Before deploying to a tool, `mmm`
  checks that its target directory (or that directory's parent) exists. No
  `~/.gemini/`? Gemini is skipped with a note, not an error.
- **Nothing is overwritten silently.** If a context file already exists and
  differs, `mmm` shows a unified diff of exactly what would change and asks
  `Overwrite? [Y/n]`. If a skill destination is anything other than the
  correct symlink — a legacy copied directory, a symlink pointing elsewhere,
  a broken symlink, or a plain file — `mmm` describes what's there (with a
  content diff for legacy copies) and asks `Replace? [Y/n]` per skill. If
  nothing changed, it says so and moves on.
- **`--dry-run` never writes.** It prints what would happen and exits.
  `mmm diff` does the same job in read-only form.
- **Empty skills are skipped.** A skill or subagent whose files are all
  empty is not deployed. (Empty context files are currently still included
  in the merged output — each contributes just its `<!-- Source: ... -->`
  header line.)
- **Deployed skills are symlinks into your sources.** The tool directories
  hold links, not copies, so a second deploy with nothing changed is a
  no-op — already-linked skills report "no changes" without prompting.
  Be aware the link works both ways: editing a file under a tool's skills
  directory edits your source repo.

## Dependencies

- Python >= 3.9
- PyYAML >= 6.0

## License

MIT
