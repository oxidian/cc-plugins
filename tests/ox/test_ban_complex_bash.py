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
_is_cd_only = ban_complex_bash._is_cd_only
DENY_MESSAGE = ban_complex_bash.DENY_MESSAGE


class TestShouldDeny:
    """Tests for should_deny()."""

    def test_denies_bash_with_empty_suggestions(self) -> None:
        """Bash command with no 'always allow' options is denied."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat foo | grep bar | sed 's/x/y/' | awk '{print $1}'"},
            "permission_suggestions": [],
        }
        assert should_deny(input_data) is not None

    def test_allows_bash_with_suggestions(self) -> None:
        """Bash command with 'always allow' options is allowed."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "permission_suggestions": [{"allow_command": "git status"}],
        }
        assert should_deny(input_data) is None

    def test_allows_non_bash_with_empty_suggestions(self) -> None:
        """Non-Bash tool with empty suggestions is allowed."""
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/etc/passwd"},
            "permission_suggestions": [],
        }
        assert should_deny(input_data) is None

    def test_denies_missing_suggestions_field(self) -> None:
        """Missing permission_suggestions field means no 'always allow' — denied."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat foo | grep bar | sed 's/x/y/'"},
        }
        assert should_deny(input_data) is not None

    def test_allows_cd_only(self) -> None:
        """A plain cd command with no suggestions is allowed through."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd /some/path"},
        }
        assert should_deny(input_data) is None

    def test_allows_bare_cd(self) -> None:
        """Bare cd with no arguments is allowed."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd"},
        }
        assert should_deny(input_data) is None

    def test_allows_cd_with_tilde(self) -> None:
        """cd with tilde path is allowed."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd ~/project"},
        }
        assert should_deny(input_data) is None

    def test_denies_cd_chained_with_and(self) -> None:
        """cd chained with && is denied with a message containing the cd part."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd /path && make build"},
        }
        result = should_deny(input_data)
        assert result is not None
        assert "cd /path" in result

    def test_denies_cd_chained_with_semicolon(self) -> None:
        """cd chained with ; is denied with a message containing the cd part."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd /path; ls"},
        }
        result = should_deny(input_data)
        assert result is not None
        assert "cd /path" in result

    def test_denies_non_cd_complex(self) -> None:
        """Non-cd complex command returns the standard DENY_MESSAGE."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat foo | grep bar"},
        }
        assert should_deny(input_data) == DENY_MESSAGE


class TestIsCdOnly:
    """Tests for _is_cd_only()."""

    def test_simple_cd_path(self) -> None:
        assert _is_cd_only("cd /some/path") is True

    def test_bare_cd(self) -> None:
        assert _is_cd_only("cd") is True

    def test_cd_dotdot(self) -> None:
        assert _is_cd_only("cd ..") is True

    def test_cd_with_chaining(self) -> None:
        assert _is_cd_only("cd /path && ls") is False

    def test_cd_with_pipe(self) -> None:
        assert _is_cd_only("cd /path | something") is False

    def test_cd_with_semicolon(self) -> None:
        assert _is_cd_only("cd /path; ls") is False

    def test_not_cd(self) -> None:
        assert _is_cd_only("cat file") is False
