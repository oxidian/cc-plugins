#!/usr/bin/env python3
"""PermissionRequest hook: auto-deny complex Bash commands.

In practice, when Claude attempts complex bash commands there's already a simpler
way to do what it wants. These commands block the agentic loop waiting for user
input, which we don't want.

When Claude Code shows a permission dialog for a Bash command and the
``permission_suggestions`` array is empty (meaning no "Always Allow" option is
available), the command is considered too complex and is denied automatically.
"""

import json
import sys

DENY_MESSAGE = (
    "BLOCKED: Bash command too complex. "
    "Check CLAUDE.md for available dev commands or use a simpler command with fewer pipes."
)


def should_deny(input_data: dict) -> bool:
    """Return True when a Bash PermissionRequest has no 'always allow' options."""
    if input_data.get("tool_name") != "Bash":
        return False
    suggestions = input_data.get("permission_suggestions")
    if suggestions is None:
        return False
    return len(suggestions) == 0


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    if should_deny(input_data):
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": "deny",
                    "message": DENY_MESSAGE,
                },
            }
        }
        json.dump(result, sys.stdout)
        sys.exit(0)

    # Allow the normal permission dialog to proceed
    sys.exit(0)


if __name__ == "__main__":
    main()
