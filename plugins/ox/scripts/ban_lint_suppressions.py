#!/usr/bin/env python3
import json
import sys


def check_for_suppressions(content: str) -> list[str]:
    """Check if content contains lint/type checker suppressions."""
    issues = []

    banned_comments = ["# type: ignore", "# noqa", "# pyright: ignore"]

    for banned in banned_comments:
        if banned in content:
            issues.append(f"BLOCKED: Code contains '{banned}' comment")

    return issues


def validate_edit(tool_input: dict) -> list[str]:
    """Validate Edit tool for suppressions in new_string."""
    new_string = tool_input.get("new_string", "")
    return check_for_suppressions(new_string)


def validate_write(tool_input: dict) -> list[str]:
    """Validate Write tool for suppressions in content."""
    content = tool_input.get("content", "")
    return check_for_suppressions(content)


try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})

issues = []
if tool_name == "Edit":
    issues = validate_edit(tool_input)
elif tool_name == "Write":
    issues = validate_write(tool_input)

if issues:
    print("\n".join(issues), file=sys.stderr)
    print(
        "\nStop and explain to the user why you think this lint/type checker suppression is necessary.",
        file=sys.stderr,
    )
    # Exit code 2 blocks tool call and shows stderr to Claude
    sys.exit(2)

# If we reach here, no suppressions found
sys.exit(0)
