# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code plugin marketplace providing commit workflows, code quality hooks, and platform commands for Oxidian projects. Contains three plugins: **ox** (base plugin), **oxgh** (GitHub workflows), and **oxgl** (GitLab workflows).

## Commands

```bash
make setup      # Install dependencies and pre-commit hooks
make dev        # Run Claude Code with local plugins loaded
make format     # Auto-format code
make check      # Verify formatting and linting passes
make bump       # Bump plugin versions
make bump-check # Check version bump without applying
```

Uses `uv` as the package manager. Python 3.14+.

## Architecture

### Plugin Structure

```
plugins/
├── ox/                      # Base plugin
│   ├── commands/            # Command definitions (*.md with YAML frontmatter)
│   ├── hooks/               # Hook definitions (hooks.json)
│   ├── scripts/             # Python hook implementations
│   └── .claude-plugin/      # Plugin metadata (plugin.json)
├── oxgh/                    # GitHub workflow plugin
│   ├── commands/            # PR, issue, triage, merge commands
│   ├── scripts/             # Workflow automation scripts
│   └── .claude-plugin/      # Plugin metadata
└── oxgl/                    # GitLab workflow plugin
    ├── commands/            # MR, issue, merge commands
    ├── scripts/             # Workflow automation scripts
    └── .claude-plugin/      # Plugin metadata
```

### Command File Format

Commands are markdown files with YAML frontmatter specifying `allowed-tools` and `description`. The body contains context templates and task instructions.

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

## Key Files

- `.claude/settings.json` — Permissions, environment variables, MCP server config
- `.claude/ox-hooks.json` — Hook configuration for this project
- `.claude-plugin/marketplace.json` — Marketplace metadata defining available plugins
