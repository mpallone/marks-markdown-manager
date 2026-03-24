"""marks-markdown-manager (mmm): distribute AI tool configuration across platforms.

mmm manages three asset types from central source directories and deploys them
to tool-specific locations for Windsurf, Gemini CLI, Codex CLI, Claude Code,
and others:

- **context**: Markdown files concatenated into a single rules file per tool
  (e.g. all your .md files merged into ~/.gemini/GEMINI.md)
- **skills**: Directory trees copied wholesale to each tool's skills location
- **subagents**: Directory trees copied wholesale to each tool's subagents location

Usage::

    mmm deploy --config mmm.yaml
    mmm diff --config mmm.yaml
    mmm status --config mmm.yaml
"""

__version__ = "0.1.0"
