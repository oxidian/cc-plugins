#!/usr/bin/env python3
import json
import re
import sys

# Define validation rules as a list of (regex pattern, message) tuples
VALIDATION_RULES_BASH = [
    (
        r"python3?\s+-c\b",
        "Avoid 'python3 -c' commands for debugging. Run the existing tests with 'uv run pytest $TEST_FILE --vv --log-cli-level=INFO' and add `logger.info` logs to the code if you need to debug.",
    ),
    (
        r"debug.*<< 'EOF'",
        "Avoid creating custom debug files. Run the existing tests with 'uv run pytest $TEST_FILE --vv --log-cli-level=INFO' and add `logger.info` logs to the code if you need to debug.",
    ),
]

VALIDATION_RULES_WRITE = [
    (
        r".*debug.*",
        "Avoid creating custom debug files. Run the existing tests with 'uv run pytest $TEST_FILE --vv --log-cli-level=INFO' and add `logger.info` logs to the code if you need to debug.",
    ),
]


def validate_command(command: str) -> list[str]:
    if not command:
        print("ERROR: no command provided to validate_command", file=sys.stderr)
        sys.exit(1)

    issues = []
    for pattern, message in VALIDATION_RULES_BASH:
        if re.search(pattern, command):
            issues.append(message)
    return issues


def validate_write(tool_input: dict) -> list[str]:
    if not tool_input:
        print("ERROR: no tool_input provided to validate_write", file=sys.stderr)
        sys.exit(1)

    issues = []
    for pattern, message in VALIDATION_RULES_WRITE:
        if re.search(pattern, tool_input["file_path"]):
            issues.append(message)
    return issues


try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
command = tool_input.get("command", "")

if tool_name == "Bash":
    issues = validate_command(command)
elif tool_name == "Write":
    issues = validate_write(tool_input)
else:
    print(f"ERROR: unknown tool_name '{tool_name}', exiting", file=sys.stderr)
    sys.exit(1)

if issues:
    for message in issues:
        print(f"\u2022 {message}", file=sys.stderr)
    # Exit code 2 blocks tool call and shows stderr to Claude
    sys.exit(2)
