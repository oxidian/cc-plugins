#!/usr/bin/env python3
"""Run fast or slow checks when files have changed.

Reads project configuration from .claude/ox-hooks.json to determine which
checks to run. Each check config defines fast/slow commands and an
optional directory scope.

Usage:
  python run_if_changed.py --project-dir $CLAUDE_PROJECT_DIR --action fast
  python run_if_changed.py --project-dir $CLAUDE_PROJECT_DIR --action slow
  python run_if_changed.py --runtime codex --action slow
"""

import argparse
import contextlib
import json
import os
import subprocess
import sys
from typing import TextIO

# https://docs.anthropic.com/en/docs/claude-code/hooks#simple%3A-exit-code
BLOCKING_ERROR_CODE = 2
SUCCESS_CODE = 0
RUNTIME_CLAUDE = "claude"
RUNTIME_CODEX = "codex"
MAX_CODEX_FEEDBACK_CHARS = 20000

CONFIG_PATH = ".claude/ox-hooks.json"
DEFAULT_FAST_EVERY = 5


def _emit(runtime: str, message: str, *, file: TextIO = sys.stdout) -> None:
    """Print hook output only for runtimes that accept plain text logs."""
    if runtime == RUNTIME_CLAUDE:
        print(message, file=file)


def _git_root_or_cwd(cwd: str) -> str:
    """Return the Git root for cwd, falling back to cwd outside Git repos."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except Exception:
        return cwd

    if result.returncode == 0:
        root = result.stdout.strip()
        if root:
            return root
    return cwd


def _codex_project_dir(hook_input: dict | None) -> str:
    """Derive the Codex project directory from hook input."""
    if hook_input:
        cwd = hook_input.get("cwd")
        if isinstance(cwd, str) and cwd:
            return _git_root_or_cwd(cwd)
    return _git_root_or_cwd(os.getcwd())


def _codex_failure_feedback(action: str, failure_outputs: list[str]) -> str:
    """Build the continuation prompt Codex receives when checks fail."""
    check_name = "Final checks" if action == "slow" else "Fast checks"
    body = "\n\n".join(output.strip() for output in failure_outputs if output.strip())
    if len(body) > MAX_CODEX_FEEDBACK_CHARS:
        body = body[-MAX_CODEX_FEEDBACK_CHARS:]
    if body:
        return f"{check_name} failed. Fix these issues before finishing.\n\n{body}\n"
    return f"{check_name} failed. Re-run the configured checks and fix the failures before finishing.\n"


def _get_state_file_path(session_id: str) -> str:
    """Return the path to the throttle state file for this session."""
    return f"/tmp/ox-hooks-{session_id}.json"


def _load_edit_count(state_file: str) -> int:
    """Read the edit counter from the state file. Returns 0 on missing/corrupt."""
    try:
        with open(state_file) as f:
            data = json.load(f)
        return int(data.get("edit_count", 0))
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError, TypeError):
        return 0


def _save_edit_count(state_file: str, count: int) -> None:
    """Write the edit counter to the state file. Silently catches errors."""
    try:
        with open(state_file, "w") as f:
            json.dump({"edit_count": count}, f)
    except OSError:
        pass


def should_skip_throttled(edit_count: int, fast_every: int) -> bool:
    """Decide whether to skip the fast check based on edit count.

    Runs every ``fast_every``-th edit (5, 10, 15, … by default).
    Returns True when the check should be *skipped*.
    """
    if fast_every <= 1:
        return False
    return edit_count % fast_every != 0


def _is_python_import_only(old_string: str, new_string: str) -> bool:
    """Check if edit only adds/modifies Python import statements."""

    def get_non_import_lines(text: str) -> list[str]:
        lines = []
        in_paren_import = False
        backslash_continuation = False

        for line in text.split("\n"):
            stripped = line.strip()

            # Handle backslash continuation from previous line
            if backslash_continuation:
                backslash_continuation = stripped.endswith("\\")
                continue

            # Handle parenthesized import block
            if in_paren_import:
                if ")" in stripped:
                    in_paren_import = False
                continue

            # Check if this is an import statement
            if stripped.startswith(("import ", "from ")):
                # Multi-line parenthesized import
                if " import " in stripped and "(" in stripped and ")" not in stripped:
                    in_paren_import = True
                # Backslash continuation
                elif stripped.endswith("\\"):
                    backslash_continuation = True
                continue

            # Non-import line
            if stripped:
                lines.append(line)

        return lines

    return get_non_import_lines(old_string) == get_non_import_lines(new_string)


def _is_js_import_only(old_string: str, new_string: str) -> bool:
    """Check if edit only adds/modifies JS/TS import statements."""

    def get_non_import_lines(text: str) -> list[str]:
        lines = []
        in_import_block = False
        in_export_block = False

        for line in text.split("\n"):
            stripped = line.strip()

            # Handle multi-line import block
            if in_import_block:
                if "from" in stripped or stripped.endswith(";"):
                    in_import_block = False
                continue

            # Handle multi-line export block
            if in_export_block:
                if stripped.startswith("}") or stripped.endswith("};"):
                    in_export_block = False
                continue

            # Check if this starts an import
            if stripped.startswith("import "):
                if "{" in stripped and "}" not in stripped:
                    in_import_block = True
                continue

            # Only treat re-export blocks as export-only (export { ... } or export type { ... })
            if stripped.startswith(("export {", "export type {")):
                if "}" not in stripped:
                    in_export_block = True
                continue

            # Non-import/export line
            if stripped:
                lines.append(line)

        return lines

    return get_non_import_lines(old_string) == get_non_import_lines(new_string)


def is_import_only_edit(hook_input: dict) -> bool:
    """Check if this edit only modifies import statements.

    Routes to language-specific logic based on file extension.
    """
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if file_path.endswith(".py"):
        return _is_python_import_only(old_string, new_string)

    if any(file_path.endswith(ext) for ext in (".ts", ".tsx", ".js", ".jsx")):
        return _is_js_import_only(old_string, new_string)

    return False


def _is_team_lead_session(session_id: str) -> bool:
    """Check if this session is leading an active agent team.

    Agent teams (https://docs.anthropic.com/en/docs/claude-code/agent-teams)
    store config in ~/.claude/teams/<name>/config.json, which includes
    leadSessionId. When the lead session runs stop checks, it blocks the
    orchestrator from coordinating members. The members' own sessions still
    run their stop hooks independently, so skipping here is safe.
    """
    teams_dir = os.path.expanduser("~/.claude/teams")
    if not os.path.isdir(teams_dir):
        return False
    for entry in os.listdir(teams_dir):
        config_path = os.path.join(teams_dir, entry, "config.json")
        if not os.path.isfile(config_path):
            continue
        try:
            with open(config_path) as f:
                team = json.load(f)
            if team.get("leadSessionId") == session_id:
                return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


def get_changed_files(project_dir: str) -> set[str]:
    """Return the set of changed file paths from git status --porcelain."""
    try:
        result = subprocess.run(
            "git status --porcelain",
            shell=True,
            capture_output=True,
            text=True,
            cwd=project_dir,
        )
    except Exception as e:
        print(f"Error getting git status: {e}", file=sys.stderr)
        sys.exit(BLOCKING_ERROR_CODE)

    if result.returncode != 0:
        print(f"Error getting git status: {result.stderr}", file=sys.stderr)
        sys.exit(BLOCKING_ERROR_CODE)

    files = set()
    for line in result.stdout.split("\n"):
        if line:
            files.add(line[3:])  # Skip XY status codes and space
    return files


def directory_has_changes(changed_files: set[str], directory: str) -> bool:
    """Check if any changed file is under the given directory."""
    prefix = f"{directory}/"
    return any(f.startswith(prefix) for f in changed_files)


def run_check(command: str, cwd: str, action: str, runtime: str) -> tuple[bool, str]:
    """Run a command in the given directory. Returns True on success."""
    _emit(runtime, f"Running `{command}` in {cwd}")

    process = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    output_lines = []
    if process.stdout:
        for line in process.stdout:
            output_lines.append(line)
    process.wait()
    output = "".join(output_lines)

    if process.returncode == 0:
        if output and runtime == RUNTIME_CLAUDE:
            print(output, end="")
        if action == "slow":
            _emit(runtime, "Checks passed.")
        else:
            _emit(runtime, "Fast check completed successfully.")
        return True, ""
    else:
        if output and runtime == RUNTIME_CLAUDE:
            print(output, end="", file=sys.stderr)
        if action == "slow":
            _emit(runtime, "Checks failed. You must fix them.", file=sys.stderr)
        else:
            _emit(runtime, "Fast check failed. You must fix the issues.", file=sys.stderr)

        failure = f"Running `{command}` in {cwd}"
        if output:
            failure = f"{failure}\n{output.rstrip()}"
        return False, failure


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fast/slow checks when files change")
    parser.add_argument("--project-dir", help="Project root directory")
    parser.add_argument(
        "--action",
        required=True,
        choices=["fast", "slow"],
        help="Action to run",
    )
    parser.add_argument(
        "--runtime",
        default=RUNTIME_CLAUDE,
        choices=[RUNTIME_CLAUDE, RUNTIME_CODEX],
        help="Hook runtime output semantics",
    )
    args = parser.parse_args()

    # Read hook input from stdin before resolving Codex's project directory.
    hook_input = None
    session_id = ""
    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            parsed_input = json.loads(stdin_data)
            if isinstance(parsed_input, dict):
                hook_input = parsed_input
                session_id = hook_input.get("session_id", "")
    except (json.JSONDecodeError, Exception):
        pass

    project_dir = args.project_dir
    if not project_dir and args.runtime == RUNTIME_CODEX:
        project_dir = _codex_project_dir(hook_input)
    if not project_dir:
        parser.error("--project-dir is required unless --runtime codex can derive cwd")

    # Read config
    config_file = os.path.join(project_dir, CONFIG_PATH)
    if not os.path.exists(config_file):
        _emit(args.runtime, f"No {CONFIG_PATH} found, skipping")
        sys.exit(SUCCESS_CODE)

    with open(config_file) as f:
        config = json.load(f)

    checks = config.get("checks", [])
    if not checks:
        _emit(args.runtime, f"No checks configured in {CONFIG_PATH}, skipping")
        sys.exit(SUCCESS_CODE)

    if hook_input and hook_input.get("permission_mode") == "plan":
        _emit(args.runtime, "Plan mode active, skipping")
        sys.exit(SUCCESS_CODE)
    if hook_input and args.action == "slow" and _is_team_lead_session(session_id):
        _emit(args.runtime, "Agent team lead session, skipping stop checks")
        sys.exit(SUCCESS_CODE)

    # Skip fast checks for import-only edits
    if args.action == "fast" and hook_input and is_import_only_edit(hook_input):
        _emit(args.runtime, "Import-only edit detected, skipping fast check")
        sys.exit(SUCCESS_CODE)

    # Throttle fast checks — only run every Nth edit
    if args.action == "fast" and session_id:
        fast_every = config.get("fast_every", DEFAULT_FAST_EVERY)
        state_file = _get_state_file_path(session_id)
        edit_count = _load_edit_count(state_file) + 1
        _save_edit_count(state_file, edit_count)
        if should_skip_throttled(edit_count, fast_every):
            _emit(args.runtime, f"Throttled: edit {edit_count} (runs every {fast_every}), skipping fast check")
            sys.exit(SUCCESS_CODE)

    changed_files = get_changed_files(project_dir)
    if not changed_files:
        _emit(args.runtime, "No files changed, skipping")
        sys.exit(SUCCESS_CODE)

    any_failed = False
    failure_outputs = []

    for check in checks:
        command = check.get(args.action)
        if not command:
            continue

        directory = check.get("directory")

        if directory:
            if not directory_has_changes(changed_files, directory):
                _emit(args.runtime, f"No {directory}/ files modified, skipping")
                continue
            cwd = os.path.join(project_dir, directory)
        else:
            # Whole-project check — run at project root on any change
            cwd = project_dir

        passed, failure_output = run_check(command, cwd, args.action, args.runtime)
        if not passed:
            any_failed = True
            failure_outputs.append(failure_output)

    if any_failed:
        if args.runtime == RUNTIME_CODEX:
            print(_codex_failure_feedback(args.action, failure_outputs), end="", file=sys.stderr)
        sys.exit(BLOCKING_ERROR_CODE)

    if args.action == "slow" and not any_failed:
        _emit(args.runtime, "All checks passed. Stop working.")

    # Clean up throttle state file after slow checks
    if args.action == "slow" and session_id:
        with contextlib.suppress(OSError):
            os.remove(_get_state_file_path(session_id))

    sys.exit(SUCCESS_CODE)


if __name__ == "__main__":
    main()
