#!/usr/bin/env python3
"""PermissionRequest hook: auto-deny complex Bash commands.

In practice, when Claude attempts complex bash commands there's already a simpler
way to do what it wants. These commands block the agentic loop waiting for user
input, which we don't want.

When Claude Code shows a permission dialog for a Bash command and the
``permission_suggestions`` field is missing or empty (meaning no "Always Allow"
option is available), the command is considered too complex and is denied
automatically.

Plain ``cd`` commands are an exception — they never have permission_suggestions
but are simple navigation commands, so they are allowed through to the normal
permission dialog. Chained ``cd`` commands (e.g. ``cd /path && make build``) are
denied with guidance to run the ``cd`` separately.
"""

import json
import re
import sys

DENY_MESSAGE = (
    "BLOCKED: Bash command too complex. "
    "Check CLAUDE.md for available dev commands or use a simpler command with fewer pipes."
)

CD_DENY_MESSAGE = (
    "BLOCKED: Run the cd command separately first, then run your actual command.\nSuggested cd: {cd_part}"
)

_SHELL_CHAIN = re.compile(r"[;&|`]|\$\(")


def _is_cd_only(command: str) -> bool:
    """Return True if the command is just ``cd`` with no chaining."""
    stripped = command.strip()
    if stripped != "cd" and not stripped.startswith(("cd ", "cd\t")):
        return False
    return not _SHELL_CHAIN.search(stripped)


def _extract_cd(command: str) -> str:
    """Extract the cd portion from a chained command like ``cd /path && ...``."""
    m = re.match(r"(cd\s+\S+)", command.strip())
    return m.group(1) if m else "cd"


def should_deny(input_data: dict) -> str | None:
    """Return a deny message, or None to allow."""
    if input_data.get("tool_name") != "Bash":
        return None
    suggestions = input_data.get("permission_suggestions")
    if suggestions:
        return None
    command = input_data.get("tool_input", {}).get("command", "")
    if _is_cd_only(command):
        return None
    if command.strip().startswith(("cd ", "cd\t")):
        return CD_DENY_MESSAGE.format(cd_part=_extract_cd(command))
    return DENY_MESSAGE


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    message = should_deny(input_data)
    if message:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": "deny",
                    "message": message,
                },
            }
        }
        json.dump(result, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()
