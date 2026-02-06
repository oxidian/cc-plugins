#!/usr/bin/env python3
"""Run fast or slow checks when files have changed.

Reads project configuration from .claude/ox-hooks.json to determine which
checks to run. Each check config defines fast/slow commands and an
optional directory scope.

Usage:
  python run_if_changed.py --project-dir $CLAUDE_PROJECT_DIR --action fast
  python run_if_changed.py --project-dir $CLAUDE_PROJECT_DIR --action slow
"""

import argparse
import json
import os
import subprocess
import sys

# https://docs.anthropic.com/en/docs/claude-code/hooks#simple%3A-exit-code
BLOCKING_ERROR_CODE = 2
SUCCESS_CODE = 0

CONFIG_PATH = ".claude/ox-hooks.json"


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


def run_check(command: str, cwd: str, action: str) -> bool:
    """Run a command in the given directory. Returns True on success."""
    print(f"Running `{command}` in {cwd}")

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
    process.wait()

    if process.returncode == 0:
        if process.stdout:
            for line in process.stdout:
                print(line, end="")
        if action == "slow":
            print("Checks passed.")
        else:
            print("Fast check completed successfully.")
        return True
    else:
        if process.stdout:
            for line in process.stdout:
                print(line, end="", file=sys.stderr)
        if action == "slow":
            print("Checks failed. You must fix them.", file=sys.stderr)
        else:
            print("Fast check failed. You must fix the issues.", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fast/slow checks when files change")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    parser.add_argument(
        "--action",
        required=True,
        choices=["fast", "slow"],
        help="Action to run",
    )
    args = parser.parse_args()

    # Read config
    config_file = os.path.join(args.project_dir, CONFIG_PATH)
    if not os.path.exists(config_file):
        print(f"No {CONFIG_PATH} found, skipping")
        sys.exit(SUCCESS_CODE)

    with open(config_file) as f:
        config = json.load(f)

    checks = config.get("checks", [])
    if not checks:
        print(f"No checks configured in {CONFIG_PATH}, skipping")
        sys.exit(SUCCESS_CODE)

    # Read hook input from stdin
    hook_input = None
    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            hook_input = json.loads(stdin_data)
            if hook_input.get("permission_mode") == "plan":
                print("Plan mode active, skipping")
                sys.exit(SUCCESS_CODE)
            if args.action == "slow" and _is_team_lead_session(hook_input.get("session_id", "")):
                print("Agent team lead session, skipping stop checks")
                sys.exit(SUCCESS_CODE)
    except (json.JSONDecodeError, Exception):
        pass

    # Skip fast checks for import-only edits
    if args.action == "fast" and hook_input and is_import_only_edit(hook_input):
        print("Import-only edit detected, skipping fast check")
        sys.exit(SUCCESS_CODE)

    changed_files = get_changed_files(args.project_dir)
    if not changed_files:
        print("No files changed, skipping")
        sys.exit(SUCCESS_CODE)

    any_failed = False

    for check in checks:
        command = check.get(args.action)
        if not command:
            continue

        directory = check.get("directory")

        if directory:
            if not directory_has_changes(changed_files, directory):
                print(f"No {directory}/ files modified, skipping")
                continue
            cwd = os.path.join(args.project_dir, directory)
        else:
            # Whole-project check — run at project root on any change
            cwd = args.project_dir

        if not run_check(command, cwd, args.action):
            any_failed = True

    if any_failed:
        sys.exit(BLOCKING_ERROR_CODE)

    if args.action == "slow" and not any_failed:
        print("All checks passed. Stop working.")

    sys.exit(SUCCESS_CODE)


if __name__ == "__main__":
    main()
