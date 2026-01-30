#!/usr/bin/env python3
import json
import re
import sys


def validate_bash_command(command: str, cwd: str) -> str:
    """Check if bash command has redundant cd to backend or frontend."""
    if not command:
        return ""

    # Check for 'cd backend' pattern
    if re.match(r"^\s*cd\s+backend\b", command) and cwd.endswith("/backend"):
        # Strip the redundant cd part
        clean_command = re.sub(r"^\s*cd\s+backend\s*&&\s*", "", command)
        clean_command = re.sub(r"^\s*cd\s+backend\s*$", "", clean_command)
        return f"""
BLOCKED: You are already in the backend directory ({cwd}).
Remove the 'cd backend' prefix.

Command should be: {clean_command}
"""

    # Check for 'cd frontend' pattern
    if re.match(r"^\s*cd\s+frontend\b", command) and cwd.endswith("/frontend"):
        # Strip the redundant cd part
        clean_command = re.sub(r"^\s*cd\s+frontend\s*&&\s*", "", command)
        clean_command = re.sub(r"^\s*cd\s+frontend\s*$", "", clean_command)
        return f"""
BLOCKED: You are already in the frontend directory ({cwd}).
Remove the 'cd frontend' prefix.

Command should be: {clean_command}
"""

    return ""


try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
cwd = input_data.get("cwd", "")
command = tool_input.get("command", "")

if tool_name != "Bash":
    # Only applies to Bash commands
    sys.exit(0)

error_message = validate_bash_command(command, cwd)

if error_message:
    print(error_message, file=sys.stderr)
    # Exit code 2 blocks tool call and shows stderr to Claude
    sys.exit(2)

# If we reach here, the command is allowed
sys.exit(0)
