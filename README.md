# marks-markdown-manager (mmm)

A CLI tool for distributing AI tool configuration across multiple AI coding assistants.

## Problems it solves

**1. Distribution across tools**

Skills, subagents, and global context (e.g. `AGENTS.md`) need to reach multiple AI tools — Claude Code, Windsurf, Gemini CLI, Codex CLI, etc. — each with their own directory conventions. Maintaining separate copies manually is error-prone and tedious. `mmm` keeps one canonical source and deploys to all targets.

**2. Control over many sources**

An engineer may have multiple potential sources for these assets (personal, team, org-wide, project-specific). `mmm` gives explicit control over which sources are active and what gets deployed, so you're never guessing what's actually loaded into your tools.

## Usage

```
mmm deploy --config mmm.yaml        # deploy to all tools
mmm deploy --config mmm.yaml --dry-run  # preview without writing
mmm check  --config mmm.yaml        # run dedup check only
mmm status --config mmm.yaml        # show what's currently deployed
```

## License

MIT
