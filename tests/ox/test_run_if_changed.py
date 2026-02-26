"""Tests for run_if_changed.py import detection logic."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

# Load the module dynamically since it's not in a proper package
_script_path = Path(__file__).parent.parent.parent / "plugins" / "ox" / "scripts" / "run_if_changed.py"
_spec = importlib.util.spec_from_file_location("run_if_changed", _script_path)
assert _spec is not None
assert _spec.loader is not None
run_if_changed: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["run_if_changed"] = run_if_changed
_spec.loader.exec_module(run_if_changed)

_is_python_import_only = run_if_changed._is_python_import_only
_is_js_import_only = run_if_changed._is_js_import_only
is_import_only_edit = run_if_changed.is_import_only_edit
should_skip_throttled = run_if_changed.should_skip_throttled
_get_state_file_path = run_if_changed._get_state_file_path
_load_edit_count = run_if_changed._load_edit_count
_save_edit_count = run_if_changed._save_edit_count


class TestPythonImportOnly:
    """Tests for _is_python_import_only()."""

    def test_single_line_import_add(self) -> None:
        """Adding a single-line import is detected."""
        old = "import os\n\ndef foo(): pass"
        new = "import os\nimport sys\n\ndef foo(): pass"
        assert _is_python_import_only(old, new) is True

    def test_multiline_paren_import_add(self) -> None:
        """Adding items to a parenthesized import block is detected."""
        old = "from app.models import (\n    BudgetType,\n    Milestone,\n)\n\ndef foo(): pass"
        new = "from app.models import (\n    BudgetType,\n    Milestone,\n    PaymentMilestone,\n    Role,\n)\n\ndef foo(): pass"
        assert _is_python_import_only(old, new) is True

    def test_backslash_continuation_import(self) -> None:
        """Adding to backslash-continued imports is detected."""
        old = "from module import A, \\\n    B\n\ndef foo(): pass"
        new = "from module import A, \\\n    B, \\\n    C\n\ndef foo(): pass"
        assert _is_python_import_only(old, new) is True

    def test_mixed_edit_not_detected(self) -> None:
        """Edits that touch both imports and code are NOT import-only."""
        old = "import os\n\ncode = 1"
        new = "import os\nimport sys\n\ncode = 2"
        assert _is_python_import_only(old, new) is False

    def test_code_only_edit(self) -> None:
        """Edits that only touch code are NOT import-only."""
        old = "import os\n\ncode = 1"
        new = "import os\n\ncode = 2"
        assert _is_python_import_only(old, new) is False

    def test_multiline_string_with_from_paren_not_import_only(self) -> None:
        """Multiline strings with 'from (' are NOT import-only."""
        old = 'sql = """\nfrom (\n    select * from users\n)\n"""'
        new = 'sql = """\nfrom (\n    select * from users where id = 1\n)\n"""'
        assert _is_python_import_only(old, new) is False

    def test_from_without_import_keyword_not_import_only(self) -> None:
        """Lines starting with 'from ' but lacking 'import' are NOT import-only."""
        old = "x = 1"
        new = "from (\n    select\n)\nx = 1"
        assert _is_python_import_only(old, new) is False


class TestJsImportOnly:
    """Tests for _is_js_import_only()."""

    def test_multiline_named_import(self) -> None:
        """Adding to multi-line named imports is detected."""
        old = "import {\n  A,\n  B,\n} from 'mod'\n\nconst x = 1"
        new = "import {\n  A,\n  B,\n  C,\n} from 'mod'\n\nconst x = 1"
        assert _is_js_import_only(old, new) is True

    def test_multiline_export(self) -> None:
        """Adding to multi-line exports is detected."""
        old = "export {\n  A,\n  B,\n}\n\nconst x = 1"
        new = "export {\n  A,\n  B,\n  C,\n}\n\nconst x = 1"
        assert _is_js_import_only(old, new) is True

    def test_export_const_object_not_import_only(self) -> None:
        """Editing exported object literal is NOT import-only."""
        old = "export const config = {\n  foo: 1,\n}"
        new = "export const config = {\n  foo: 2,\n}"
        assert _is_js_import_only(old, new) is False

    def test_export_default_object_not_import_only(self) -> None:
        """Editing default exported object is NOT import-only."""
        old = "export default {\n  name: 'old',\n}"
        new = "export default {\n  name: 'new',\n}"
        assert _is_js_import_only(old, new) is False


class TestIsImportOnlyEdit:
    """Tests for is_import_only_edit() routing logic."""

    def test_routes_to_python(self) -> None:
        """Python files use Python detection."""
        hook_input = {
            "tool_input": {
                "file_path": "/path/to/file.py",
                "old_string": "import os",
                "new_string": "import os\nimport sys",
            }
        }
        assert is_import_only_edit(hook_input) is True

    def test_routes_to_js(self) -> None:
        """JS/TS files use JS detection."""
        for ext in [".ts", ".tsx", ".js", ".jsx"]:
            hook_input = {
                "tool_input": {
                    "file_path": f"/path/to/file{ext}",
                    "old_string": "import { A } from 'mod'",
                    "new_string": "import { A, B } from 'mod'",
                }
            }
            assert is_import_only_edit(hook_input) is True

    def test_other_extensions_return_false(self) -> None:
        """Non-Python/JS files return False."""
        hook_input = {
            "tool_input": {
                "file_path": "/path/to/file.go",
                "old_string": "import os",
                "new_string": "import os\nimport sys",
            }
        }
        assert is_import_only_edit(hook_input) is False


class TestShouldSkipThrottled:
    """Tests for should_skip_throttled() pure logic."""

    def test_fast_every_1_never_skips(self) -> None:
        for count in [1, 2, 5, 100]:
            assert should_skip_throttled(count, 1) is False

    def test_fast_every_zero_never_skips(self) -> None:
        for count in [1, 2, 5]:
            assert should_skip_throttled(count, 0) is False

    def test_fast_every_negative_never_skips(self) -> None:
        for count in [1, 2, 5]:
            assert should_skip_throttled(count, -1) is False

    def test_first_edit_always_runs(self) -> None:
        for fast_every in [1, 3, 5, 10]:
            assert should_skip_throttled(1, fast_every) is False

    def test_every_nth_edit_runs(self) -> None:
        assert should_skip_throttled(5, 5) is False
        assert should_skip_throttled(10, 5) is False
        assert should_skip_throttled(15, 5) is False

    def test_intermediate_edits_skip(self) -> None:
        assert should_skip_throttled(2, 5) is True
        assert should_skip_throttled(3, 5) is True
        assert should_skip_throttled(4, 5) is True
        assert should_skip_throttled(6, 5) is True


class TestEditCountStateFile:
    """Tests for state file I/O helpers."""

    def test_missing_file_returns_zero(self, tmp_path: Path) -> None:
        assert _load_edit_count(str(tmp_path / "nonexistent.json")) == 0

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        state_file = str(tmp_path / "state.json")
        _save_edit_count(state_file, 7)
        assert _load_edit_count(state_file) == 7

    def test_corrupt_file_returns_zero(self, tmp_path: Path) -> None:
        state_file = tmp_path / "bad.json"
        state_file.write_text("not json{{{")
        assert _load_edit_count(str(state_file)) == 0

    def test_path_includes_session_id(self) -> None:
        path = _get_state_file_path("abc-123")
        assert "abc-123" in path
        assert path.startswith("/tmp/")
