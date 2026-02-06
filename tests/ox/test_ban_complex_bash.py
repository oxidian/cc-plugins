"""Tests for ban_complex_bash.py PermissionRequest hook."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

# Load the module dynamically since it's not in a proper package
_script_path = Path(__file__).parent.parent.parent / "plugins" / "ox" / "scripts" / "ban_complex_bash.py"
_spec = importlib.util.spec_from_file_location("ban_complex_bash", _script_path)
assert _spec is not None
assert _spec.loader is not None
ban_complex_bash: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["ban_complex_bash"] = ban_complex_bash
_spec.loader.exec_module(ban_complex_bash)

should_deny = ban_complex_bash.should_deny


class TestShouldDeny:
    """Tests for should_deny()."""

    def test_denies_bash_with_empty_suggestions(self) -> None:
        """Bash command with no 'always allow' options is denied."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat foo | grep bar | sed 's/x/y/' | awk '{print $1}'"},
            "permission_suggestions": [],
        }
        assert should_deny(input_data) is True

    def test_allows_bash_with_suggestions(self) -> None:
        """Bash command with 'always allow' options is allowed."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "permission_suggestions": [{"allow_command": "git status"}],
        }
        assert should_deny(input_data) is False

    def test_allows_non_bash_with_empty_suggestions(self) -> None:
        """Non-Bash tool with empty suggestions is allowed."""
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/etc/passwd"},
            "permission_suggestions": [],
        }
        assert should_deny(input_data) is False

    def test_allows_missing_suggestions_field(self) -> None:
        """Missing permission_suggestions field defaults to allow (safe default)."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat foo | grep bar | sed 's/x/y/'"},
        }
        assert should_deny(input_data) is False
