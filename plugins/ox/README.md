# ox

Base plugin.


> [!WARNING]
> Hooks require pre-configuration to function. See #project-configuration

## Commands

- **`/commit`** — clean commit workflow (branch creation, staging, imperative messages)

## Hooks

### PreToolUse

Quality guards that block bad patterns before they reach the codebase:

- **`ban_redundant_cd.py`** — blocks redundant `cd` into directories the shell is already in
- **`ban_custom_debug.py`** — blocks `python -c` debug scripts and custom debug files
- **`ban_lint_suppressions.py`** — blocks `# noqa`, `# type: ignore`, `# pyright: ignore`

### PostToolUse

Runs on `Write|Edit|MultiEdit` — auto-formats changed files using the project's configured commands.

### Stop

Runs before Claude stops — executes check commands on modified subsystems.

## Project configuration

The PostToolUse and Stop hooks read `.claude/ox-hooks.json` from the project root to determine what to run. If the file is missing, the hooks are no-ops.

Each entry in `subsystems` defines a `format` command (run on PostToolUse) and a `check` command (run on Stop). If `directory` is set, the command only triggers when files under that directory have changed and runs inside that subdirectory. If omitted, the command triggers on any file change and runs at the project root.

**Whole-project** (e.g. a Python project using ruff):

```json
{
  "subsystems": [
    { "format": "uv run ruff format .", "check": "uv run ruff check ." }
  ]
}
```

**Multi-directory** (e.g. a fullstack monorepo):

```json
{
  "subsystems": [
    { "directory": "backend",    "format": "make format",    "check": "make check" },
    { "directory": "frontend",   "format": "npm run format", "check": "npm run check" },
    { "directory": "hocuspocus", "format": "npm run format", "check": "npm run check" }
  ]
}
```

The script also skips formatting for import-only edits (Python and JS/TS) to avoid unnecessary formatter runs while imports are being added.
