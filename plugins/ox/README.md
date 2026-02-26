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

Runs before Claude stops — executes slow checks on modified directories.

## Project configuration

The PostToolUse and Stop hooks read `.claude/ox-hooks.json` from the project root to determine what to run. If the file is missing, the hooks are no-ops.

Each entry in `checks` defines a `fast` command (run on PostToolUse) and a `slow` command (run on Stop). If `directory` is set, the command only triggers when files under that directory have changed and runs inside that subdirectory. If omitted, the command triggers on any file change and runs at the project root.

**Whole-project** (e.g. a Python project using ruff):

```json
{
  "checks": [
    { "fast": "uv run ruff format .", "slow": "uv run ruff check ." }
  ]
}
```

**Multi-directory** (e.g. a fullstack monorepo):

```json
{
  "checks": [
    { "directory": "backend",    "fast": "make format",    "slow": "make check" },
    { "directory": "frontend",   "fast": "npm run format", "slow": "npm run check" },
    { "directory": "hocuspocus", "fast": "npm run format", "slow": "npm run check" }
  ]
}
```

The script also skips formatting for import-only edits (Python and JS/TS) to avoid unnecessary formatter runs while imports are being added.

### Throttling fast checks

When Claude makes many sequential edits, running the formatter on every single one is wasteful. The `fast_every` option throttles PostToolUse fast checks so they only run on the 1st edit and every Nth edit thereafter. The Stop hook always runs slow checks regardless of the throttle, catching any missed formatting.

```json
{
  "fast_every": 5,
  "checks": [
    { "fast": "make format", "slow": "make check" }
  ]
}
```

- **Default:** `5` — format runs on edit 1, then every 5th edit (1, 5, 10, 15, ...)
- Set to `1` to disable throttling (run on every edit)
