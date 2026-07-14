"""Tests for run_if_changed.py import detection logic."""

import importlib.util
import json
import shlex
import subprocess
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


def _command_for_script(script: Path) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"


def _command_for_script_with_args(script: Path, *args: Path | str) -> str:
    quoted_args = " ".join(shlex.quote(str(arg)) for arg in args)
    return f"{_command_for_script(script)} {quoted_args}"


def _init_changed_repo(tmp_path: Path, command: str) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "ox-hooks.json").write_text(
        json.dumps({"checks": [{"fast": command, "slow": command}], "fast_every": 1}) + "\n"
    )
    (tmp_path / "changed.txt").write_text("changed\n")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    return subdir


def _init_branch_changed_repo(tmp_path: Path, command: str, *, base_ref: str = "origin/main") -> Path:
    subprocess.run(
        ["git", "init", "--initial-branch", "main"], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    (tmp_path / ".claude").mkdir()
    config = {"checks": [{"fast": command, "slow": command}], "fast_every": 1}
    if base_ref != "origin/main":
        config["base_ref"] = base_ref
    (tmp_path / ".claude" / "ox-hooks.json").write_text(json.dumps(config) + "\n")
    (tmp_path / "tracked.txt").write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test User", "-c", "user.email=test@example.com", "commit", "-m", "base"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "tracked.txt").write_text("branch\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test User", "-c", "user.email=test@example.com", "commit", "-m", "branch change"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    return subdir


def _run_codex_hook(
    cwd: Path,
    action: str,
    *,
    permission_mode: str = "default",
    extra_payload: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = {
        "session_id": f"test-{action}",
        "cwd": str(cwd),
        "hook_event_name": "Stop" if action == "slow" else "PostToolUse",
        "permission_mode": permission_mode,
    }
    if extra_payload:
        payload.update(extra_payload)
    return subprocess.run(
        [sys.executable, str(_script_path), "--runtime", "codex", "--action", action],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


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

    def test_first_edit_skipped_when_throttled(self) -> None:
        for fast_every in [3, 5, 10]:
            assert should_skip_throttled(1, fast_every) is True

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


class TestCodexRuntime:
    """Tests for Codex hook output semantics."""

    def test_success_has_no_output_and_derives_project_dir_from_cwd(self, tmp_path: Path) -> None:
        check_script = tmp_path / "check.py"
        check_script.write_text("print('ok')\n")
        subdir = _init_changed_repo(tmp_path, _command_for_script(check_script))

        result = _run_codex_hook(subdir, "slow")

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_reentrant_stop_skips_before_config_parsing(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "ox-hooks.json").write_text("{not json\n")
        (tmp_path / "changed.txt").write_text("changed\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = _run_codex_hook(subdir, "slow", extra_payload={"stop_hook_active": True})

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_failure_exits_two_with_feedback_on_stderr(self, tmp_path: Path) -> None:
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nprint('bad check output')\nsys.exit(1)\n")
        subdir = _init_changed_repo(tmp_path, _command_for_script(check_script))

        result = _run_codex_hook(subdir, "slow")

        assert result.returncode == 2
        assert result.stdout == ""
        assert "Final checks failed. Fix these issues before finishing." in result.stderr
        assert "bad check output" in result.stderr

    def test_plan_mode_slow_skips_failing_checks(self, tmp_path: Path) -> None:
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nprint('bad check output')\nsys.exit(1)\n")
        subdir = _init_changed_repo(tmp_path, _command_for_script(check_script))

        result = _run_codex_hook(subdir, "slow", permission_mode="plan")

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_plan_mode_slow_skips_before_config_parsing(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "ox-hooks.json").write_text("{not json\n")
        (tmp_path / "changed.txt").write_text("changed\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = _run_codex_hook(subdir, "slow", permission_mode="plan")

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_plan_mode_slow_skips_direct_collaboration_mode_kind(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "ox-hooks.json").write_text("{not json\n")
        (tmp_path / "changed.txt").write_text("changed\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = _run_codex_hook(
            subdir,
            "slow",
            extra_payload={
                "permission_mode": "default",
                "collaboration_mode_kind": "plan",
            },
        )

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_plan_mode_slow_skips_direct_collaboration_mode_object(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "ox-hooks.json").write_text("{not json\n")
        (tmp_path / "changed.txt").write_text("changed\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = _run_codex_hook(
            subdir,
            "slow",
            extra_payload={
                "permission_mode": "default",
                "collaboration_mode": {"mode": "plan"},
            },
        )

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_plan_mode_slow_skips_when_matching_transcript_turn_is_plan(self, tmp_path: Path) -> None:
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nprint('bad check output')\nsys.exit(1)\n")
        subdir = _init_changed_repo(tmp_path, _command_for_script(check_script))
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            "\n".join(
                [
                    json.dumps({"turn_id": "other", "collaboration_mode_kind": "default"}),
                    json.dumps({"turn_id": "turn-1", "collaboration_mode_kind": "plan"}),
                ]
            )
            + "\n"
        )

        result = _run_codex_hook(
            subdir,
            "slow",
            extra_payload={
                "permission_mode": "default",
                "transcript_path": str(transcript),
                "turn_id": "turn-1",
            },
        )

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_non_plan_transcript_turn_runs_slow_checks(self, tmp_path: Path) -> None:
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nprint('bad check output')\nsys.exit(1)\n")
        subdir = _init_changed_repo(tmp_path, _command_for_script(check_script))
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(json.dumps({"turn_id": "turn-1", "collaboration_mode": {"mode": "default"}}) + "\n")

        result = _run_codex_hook(
            subdir,
            "slow",
            extra_payload={
                "permission_mode": "default",
                "transcript_path": str(transcript),
                "turn_id": "turn-1",
            },
        )

        assert result.returncode == 2
        assert "Final checks failed. Fix these issues before finishing." in result.stderr
        assert "bad check output" in result.stderr

    def test_slow_runs_for_committed_branch_changes(self, tmp_path: Path) -> None:
        marker = tmp_path / "marker.txt"
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('ran')\n")
        subdir = _init_branch_changed_repo(tmp_path, _command_for_script_with_args(check_script, marker))

        result = _run_codex_hook(subdir, "slow")

        assert result.returncode == 0
        assert marker.read_text() == "ran"

    def test_fast_skips_for_committed_branch_changes(self, tmp_path: Path) -> None:
        marker = tmp_path / "marker.txt"
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('ran')\n")
        subdir = _init_branch_changed_repo(tmp_path, _command_for_script_with_args(check_script, marker))

        result = _run_codex_hook(subdir, "fast")

        assert result.returncode == 0
        assert not marker.exists()

    def test_slow_uses_custom_base_ref(self, tmp_path: Path) -> None:
        marker = tmp_path / "marker.txt"
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('ran')\n")
        subdir = _init_branch_changed_repo(
            tmp_path,
            _command_for_script_with_args(check_script, marker),
            base_ref="origin/release",
        )
        subprocess.run(["git", "update-ref", "refs/remotes/origin/release", "origin/main"], cwd=tmp_path, check=True)
        subprocess.run(["git", "update-ref", "-d", "refs/remotes/origin/main"], cwd=tmp_path, check=True)

        result = _run_codex_hook(subdir, "slow")

        assert result.returncode == 0
        assert marker.read_text() == "ran"

    def test_slow_scopes_committed_branch_changes_to_matching_directory(self, tmp_path: Path) -> None:
        subprocess.run(
            ["git", "init", "--initial-branch", "main"], cwd=tmp_path, check=True, capture_output=True, text=True
        )
        backend = tmp_path / "backend"
        frontend = tmp_path / "frontend"
        backend.mkdir()
        frontend.mkdir()
        (backend / "file.txt").write_text("base\n")
        (frontend / "file.txt").write_text("base\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.name=Test User", "-c", "user.email=test@example.com", "commit", "-m", "base"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=tmp_path, check=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True, text=True)
        (backend / "file.txt").write_text("branch\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test User",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "backend change",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        marker = tmp_path / "marker.txt"
        check_script = tmp_path / "check.py"
        check_script.write_text(
            "import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(Path.cwd().name)\n"
        )
        (tmp_path / ".claude").mkdir()
        command = _command_for_script_with_args(check_script, marker)
        (tmp_path / ".claude" / "ox-hooks.json").write_text(
            json.dumps(
                {
                    "checks": [
                        {"directory": "backend", "slow": command},
                        {"directory": "frontend", "slow": command},
                    ]
                }
            )
            + "\n"
        )

        result = _run_codex_hook(frontend, "slow")

        assert result.returncode == 0
        assert marker.read_text() == "backend"

    def test_slow_ignores_missing_base_ref(self, tmp_path: Path) -> None:
        marker = tmp_path / "marker.txt"
        check_script = tmp_path / "check.py"
        check_script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('ran')\n")
        subdir = _init_branch_changed_repo(tmp_path, _command_for_script_with_args(check_script, marker))
        subprocess.run(["git", "update-ref", "-d", "refs/remotes/origin/main"], cwd=tmp_path, check=True)

        result = _run_codex_hook(subdir, "slow")

        assert result.returncode == 0
        assert not marker.exists()
