"""Tests for Codex template files."""

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BOOTSTRAP_TEMPLATES = [
    REPO_ROOT / "templates" / "codex" / "github" / "scripts" / "bootstrap-codex-plugins.sh",
    REPO_ROOT / "templates" / "codex" / "gitlab" / "scripts" / "bootstrap-codex-plugins.sh",
]


def test_codex_runtime_directory_is_ignored_not_tracked() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text()

    assert ".codex/" in gitignore.splitlines()
    assert not (REPO_ROOT / ".codex").is_file()


def test_bootstrap_templates_preserve_command_failures() -> None:
    required_commands = [
        'mkdir -p "$(dirname "$bootstrap_dir")" || return',
        'git -C "$bootstrap_dir" remote set-url origin "$repo_url" || return',
        'git clone --quiet --filter=blob:none "$repo_url" "$bootstrap_dir" || return',
        'git -C "$bootstrap_dir" fetch --quiet --depth 1 origin "$repo_ref" || return',
        'git -C "$bootstrap_dir" checkout --quiet --detach FETCH_HEAD || return',
        "--quiet || return",
    ]

    for template in BOOTSTRAP_TEMPLATES:
        content = template.read_text()
        for command in required_commands:
            assert command in content, f"{template} does not guard `{command}`"


def test_bootstrap_templates_skip_successfully_when_codex_is_missing(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    for command in ["cat", "git", "mktemp", "rm"]:
        command_path = shutil.which(command)
        assert command_path is not None, f"{command} is required for this test"
        (bin_dir / command).symlink_to(command_path)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    bash_path = shutil.which("bash")
    assert bash_path is not None, "bash is required for this test"

    for template in BOOTSTRAP_TEMPLATES:
        result = subprocess.run(
            [bash_path, str(template)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "warning: codex is not installed or not on PATH" in result.stderr


def test_readme_uses_namespaced_codex_plugin_skill_names() -> None:
    content = (REPO_ROOT / "README.md").read_text()

    assert "$open-pr" not in content
    assert "$issue" not in content
    assert "$oxgh:open-pr" in content
    assert "$oxgl:open-mr" in content
