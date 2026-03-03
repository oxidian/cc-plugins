# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code plugin marketplace providing commit workflows, code quality hooks, and platform skills for Oxidian projects. Contains three plugins: **ox** (base plugin), **oxgh** (GitHub workflows), and **oxgl** (GitLab workflows).

## Commands

```bash
make setup      # Install dependencies and pre-commit hooks
make dev        # Run Claude Code with local plugins loaded
make format     # Auto-format code
make check      # Run this instead of pytest directly - includes formatting, linting, type checking, and tests
make bump       # Bump plugin versions
make bump-check # Check version bump without applying
```

Uses `uv` as the package manager. Python 3.14+.

## Architecture

### Plugin Structure

```
plugins/
├── ox/                      # Base plugin
│   ├── skills/              # Skill definitions (SKILL.md with YAML frontmatter)
│   ├── hooks/               # Hook definitions (hooks.json)
│   ├── scripts/             # Python hook implementations
│   └── .claude-plugin/      # Plugin metadata (plugin.json)
├── oxgh/                    # GitHub workflow plugin
│   ├── skills/              # PR, issue, triage, merge skills
│   ├── scripts/             # Workflow automation scripts
│   └── .claude-plugin/      # Plugin metadata
└── oxgl/                    # GitLab workflow plugin
    ├── skills/              # MR, issue, merge skills
    ├── scripts/             # Workflow automation scripts
    └── .claude-plugin/      # Plugin metadata
```

### Skill File Format

Skills are markdown files (`SKILL.md`) in named subdirectories under `skills/`, with YAML frontmatter specifying `allowed-tools` and `description`. The body contains context templates and task instructions.

### Hook System (ox plugin)

Three hook types orchestrated by Python scripts in `plugins/ox/scripts/`:

- **PreToolUse** — Quality guards that block bad patterns (redundant cd, debug scripts, lint suppressions)
- **PostToolUse** — Auto-formats files after Write/Edit/MultiEdit operations
- **Stop** — Runs check commands before Claude stops

Hooks are configured per-project via `.claude/ox-hooks.json`:

```json
{
  "checks": [
    {
      "fast": "make format",
      "slow": "make check"
    }
  ]
}
```

For monorepos, use `directory` to scope commands to subdirectories.

## Workflow

- **Bugfixes use TDD**: write/update the failing test first (red), then fix the code (green). Run `make check` after each phase to confirm.

## Key Files

- `.claude/settings.json` — Permissions, environment variables, MCP server config
- `.claude/ox-hooks.json` — Hook configuration for this project
- `.claude-plugin/marketplace.json` — Marketplace metadata defining available plugins
