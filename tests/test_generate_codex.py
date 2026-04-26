"""Tests for generate_codex.py."""

import importlib.util
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

# Load the module dynamically since it's not in a proper package
_script_path = Path(__file__).parent.parent / "scripts" / "generate_codex.py"
_spec = importlib.util.spec_from_file_location("generate_codex", _script_path)
assert _spec is not None
assert _spec.loader is not None
generate_codex: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["generate_codex"] = generate_codex
_spec.loader.exec_module(generate_codex)

parse_frontmatter = generate_codex.parse_frontmatter
serialize_frontmatter = generate_codex.serialize_frontmatter
transform_frontmatter = generate_codex.transform_frontmatter
transform_context_injections = generate_codex.transform_context_injections
transform_plugin_root_refs = generate_codex.transform_plugin_root_refs
transform_tool_call_instructions = generate_codex.transform_tool_call_instructions
transform_body = generate_codex.transform_body
detect_script_deps = generate_codex.detect_script_deps
process_skill = generate_codex.process_skill
resolve_script_paths = generate_codex.resolve_script_paths
generate_plugin_package = generate_codex.generate_plugin_package
write_marketplace = generate_codex.write_marketplace
install = generate_codex.install
link = generate_codex.link

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


class TestParseFrontmatter:
    def test_basic(self) -> None:
        content = "---\nallowed-tools: Bash(git:*)\ndescription: Do stuff\n---\nBody here"
        fm, body = parse_frontmatter(content)
        assert fm == {"allowed-tools": "Bash(git:*)", "description": "Do stuff"}
        assert body == "Body here"

    def test_no_frontmatter(self) -> None:
        content = "Just a body"
        fm, body = parse_frontmatter(content)
        assert fm == {}
        assert body == "Just a body"

    def test_boolean_values(self) -> None:
        content = "---\ndisable-model-invocation: true\n---\nBody"
        fm, body = parse_frontmatter(content)
        assert fm["disable-model-invocation"] is True
        assert body == "Body"

    def test_preserves_body_newlines(self) -> None:
        content = "---\nkey: val\n---\n\nLine 1\nLine 2\n"
        _fm, body = parse_frontmatter(content)
        assert body == "\nLine 1\nLine 2\n"


class TestSerializeFrontmatter:
    def test_basic(self) -> None:
        data = {"name": "ox:commit", "description": "Do stuff"}
        result = serialize_frontmatter(data)
        assert result == "---\nname: ox:commit\ndescription: Do stuff\n---\n"

    def test_boolean(self) -> None:
        data = {"flag": True}
        result = serialize_frontmatter(data)
        assert "flag: true" in result


class TestTransformFrontmatter:
    def test_removes_allowed_tools(self) -> None:
        fm = {"allowed-tools": "Bash(git:*)", "description": "Do stuff"}
        result = transform_frontmatter(fm, "ox", "commit")
        assert "allowed-tools" not in result

    def test_removes_disable_model_invocation(self) -> None:
        fm = {"allowed-tools": "Bash(git:*)", "description": "Do stuff", "disable-model-invocation": True}
        result = transform_frontmatter(fm, "oxgh", "shipit")
        assert "disable-model-invocation" not in result

    def test_adds_namespaced_name(self) -> None:
        fm = {"description": "Do stuff"}
        result = transform_frontmatter(fm, "ox", "commit")
        assert result["name"] == "ox:commit"

    def test_keeps_description(self) -> None:
        fm = {"description": "Do stuff"}
        result = transform_frontmatter(fm, "ox", "commit")
        assert result["description"] == "Do stuff"

    def test_name_first(self) -> None:
        fm = {"description": "Do stuff"}
        result = transform_frontmatter(fm, "ox", "commit")
        keys = list(result.keys())
        assert keys[0] == "name"


class TestTransformContextInjections:
    def test_strips_bang_prefix(self) -> None:
        body = "- Status: !`git status`\n- Diff: !`git diff`\n"
        result = transform_context_injections(body)
        assert "!`" not in result
        assert "`git status`" in result
        assert "`git diff`" in result

    def test_inserts_preamble(self) -> None:
        body = "## Context\n- Status: !`git status`\n"
        result = transform_context_injections(body)
        assert "First, run these commands and review their output:" in result
        # Preamble should be between heading and first item
        lines = result.splitlines()
        ctx_idx = next(i for i, line in enumerate(lines) if line == "## Context")
        preamble_idx = next(i for i, line in enumerate(lines) if "First, run these commands" in line)
        status_idx = next(i for i, line in enumerate(lines) if "`git status`" in line)
        assert ctx_idx < preamble_idx < status_idx

    def test_no_change_without_bang(self) -> None:
        body = "## Context\n- Status: `git status`\n"
        result = transform_context_injections(body)
        assert result == body

    def test_no_preamble_without_context_heading(self) -> None:
        body = "Some text !`git status`\n"
        result = transform_context_injections(body)
        assert "`git status`" in result
        assert "First, run these commands" not in result


class TestTransformPluginRootRefs:
    def test_replaces_plugin_root(self) -> None:
        body = "Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py`"
        result = transform_plugin_root_refs(body)
        assert "${CLAUDE_PLUGIN_ROOT}" not in result
        assert "scripts/wait_for_ai_review.py" in result

    def test_no_change_without_ref(self) -> None:
        body = "Just some text"
        result = transform_plugin_root_refs(body)
        assert result == body


class TestTransformToolCallInstructions:
    def test_replaces_full_paragraph(self) -> None:
        body = textwrap.dedent("""\
            5. You have the capability to call multiple tools in a single response. You MUST do all of the above in a single message using separate tool calls for each command. Do NOT chain commands with && or ;. Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls.
        """)
        result = transform_tool_call_instructions(body)
        assert "Execute each step as a separate command." in result
        assert "Do NOT chain commands with && or ;" in result
        assert "You have the capability" not in result

    def test_replaces_short_variant(self) -> None:
        body = "3. You have the capability to call multiple tools in a single response. You MUST do the above in a single message using separate tool calls for each command. Do NOT chain commands with && or ;. Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls."
        result = transform_tool_call_instructions(body)
        assert "Execute each step as a separate command." in result
        assert "You have the capability" not in result

    def test_replaces_chain_variant(self) -> None:
        body = "5. You have the capability to call multiple tools in a single response. Chain independent calls together. Do not send any other text or messages besides these tool calls."
        result = transform_tool_call_instructions(body)
        assert "Execute each step as a separate command." in result

    def test_no_change_without_pattern(self) -> None:
        body = "Just some instructions"
        result = transform_tool_call_instructions(body)
        assert result == body


class TestTransformBody:
    def test_all_transforms_applied(self) -> None:
        body = textwrap.dedent("""\
            ## Context
            - Status: !`git status`

            ## Task
            1. Do thing
            2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/foo.py`
            3. You have the capability to call multiple tools in a single response. You MUST do the above in a single message using separate tool calls for each command. Do NOT chain commands with && or ;. Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls.
        """)
        result = transform_body(body)
        assert "!`" not in result
        assert "First, run these commands" in result
        assert "${CLAUDE_PLUGIN_ROOT}" not in result
        assert "Execute each step as a separate command." in result


class TestDetectScriptDeps:
    def test_finds_script(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugin"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "foo.py").write_text("# script")

        body = "Run `python3 scripts/foo.py 42`"
        result = detect_script_deps(body, plugin_dir)
        assert len(result) == 1
        assert result[0].name == "foo.py"

    def test_deduplicates(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugin"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "foo.py").write_text("# script")

        body = "Run `scripts/foo.py` then `scripts/foo.py` again"
        result = detect_script_deps(body, plugin_dir)
        assert len(result) == 1

    def test_ignores_missing(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugin"
        (plugin_dir / "scripts").mkdir(parents=True)

        body = "Run `scripts/nonexistent.py`"
        result = detect_script_deps(body, plugin_dir)
        assert len(result) == 0


class TestProcessSkill:
    def test_creates_output(self, tmp_path: Path) -> None:
        # Set up source skill
        skill_dir = tmp_path / "src" / "skills" / "commit"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "allowed-tools: Bash(git:*)\n"
            "description: Commit changes\n"
            "---\n"
            "\n"
            "## Context\n"
            "- Status: !`git status`\n"
        )

        output_dir = tmp_path / "out"
        process_skill("ox", skill_dir, output_dir)

        result = (output_dir / "ox" / "commit" / "SKILL.md").read_text()
        assert "name: ox:commit" in result
        assert "description: Commit changes" in result
        assert "allowed-tools" not in result
        assert "!`" not in result
        assert "First, run these commands" in result

    def test_copies_script_deps(self, tmp_path: Path) -> None:
        # Set up plugin with script
        plugin_dir = tmp_path / "src"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "wait_for_ai_review.py").write_text("# review script")

        skill_dir = plugin_dir / "skills" / "wait-for-review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py:*)\n"
            "description: Wait for review\n"
            "---\n"
            "\n"
            "Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py 42`\n"
        )

        output_dir = tmp_path / "out"
        process_skill("oxgh", skill_dir, output_dir)

        out_script = output_dir / "oxgh" / "wait-for-review" / "scripts" / "wait_for_ai_review.py"
        assert out_script.exists()
        assert out_script.read_text() == "# review script"

    def test_can_write_plugin_local_skill(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "src" / "skills" / "open-pr"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "allowed-tools: Bash(gh pr create:*)\n"
            "description: Open PR\n"
            "---\n"
            "\n"
            "## Context\n"
            "- Status: !`git status`\n"
        )

        output_dir = tmp_path / "plugin" / "skills"
        process_skill("oxgh", skill_dir, output_dir, namespaced=False, include_plugin_dir=False)

        result = (output_dir / "open-pr" / "SKILL.md").read_text()
        assert "name: open-pr" in result
        assert "name: oxgh:open-pr" not in result
        assert "allowed-tools" not in result
        assert "!`" not in result


class TestPluginPackage:
    def test_generates_manifest_and_local_skills(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "oxgh"
        (plugin_dir / ".claude-plugin").mkdir(parents=True)
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            "{\n"
            '  "name": "oxgh",\n'
            '  "description": "GitHub workflow skills using gh CLI",\n'
            '  "version": "0.1.4",\n'
            '  "author": {"name": "Oxidian"}\n'
            "}\n"
        )
        skill_dir = plugin_dir / "skills" / "open-pr"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nallowed-tools: Bash(gh pr create:*)\ndescription: Open PR\n---\n\nCreate a PR.\n"
        )
        monkeypatch.setattr(generate_codex, "PLUGINS_DIR", plugins_dir)

        output_dir = tmp_path / "codex" / "plugins"
        generate_plugin_package("oxgh", output_dir)

        manifest = (output_dir / "oxgh" / ".codex-plugin" / "plugin.json").read_text()
        skill = (output_dir / "oxgh" / "skills" / "open-pr" / "SKILL.md").read_text()
        assert '"name": "oxgh"' in manifest
        assert '"skills": "./skills/"' in manifest
        assert "name: open-pr" in skill
        assert "allowed-tools" not in skill

    def test_writes_marketplace(self, tmp_path: Path) -> None:
        marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"

        write_marketplace(["ox", "oxgh"], marketplace)

        result = marketplace.read_text()
        assert '"name": "oxidian"' in result
        assert '"path": "./codex/plugins/ox"' in result
        assert '"path": "./codex/plugins/oxgh"' in result
        assert '"installation": "AVAILABLE"' in result
        assert '"authentication": "ON_INSTALL"' in result


class TestEndToEnd:
    """Test processing actual SKILL.md files from the repo."""

    def test_commit_skill(self, tmp_path: Path) -> None:
        skill_dir = PLUGINS_DIR / "ox" / "skills" / "commit"
        process_skill("ox", skill_dir, tmp_path)

        result = (tmp_path / "ox" / "commit" / "SKILL.md").read_text()
        assert "name: ox:commit" in result
        assert "description: Commit changes with a clean commit message" in result
        assert "allowed-tools" not in result
        assert "!`" not in result
        assert "First, run these commands" in result
        assert "`git status`" in result
        assert "Execute each step as a separate command." in result

    def test_wait_for_review_skill(self, tmp_path: Path) -> None:
        skill_dir = PLUGINS_DIR / "oxgh" / "skills" / "wait-for-review"
        process_skill("oxgh", skill_dir, tmp_path)

        result = (tmp_path / "oxgh" / "wait-for-review" / "SKILL.md").read_text()
        assert "name: oxgh:wait-for-review" in result
        assert "${CLAUDE_PLUGIN_ROOT}" not in result
        assert "scripts/wait_for_ai_review.py" in result
        assert "disable-model-invocation" not in result

        # Script should be copied
        script = tmp_path / "oxgh" / "wait-for-review" / "scripts" / "wait_for_ai_review.py"
        assert script.exists()

    def test_shipit_skill(self, tmp_path: Path) -> None:
        skill_dir = PLUGINS_DIR / "oxgh" / "skills" / "shipit"
        process_skill("oxgh", skill_dir, tmp_path)

        result = (tmp_path / "oxgh" / "shipit" / "SKILL.md").read_text()
        assert "name: oxgh:shipit" in result
        assert "disable-model-invocation" not in result
        assert "allowed-tools" not in result

    def test_issue_skill_preserves_code_blocks(self, tmp_path: Path) -> None:
        skill_dir = PLUGINS_DIR / "oxgh" / "skills" / "issue"
        process_skill("oxgh", skill_dir, tmp_path)

        result = (tmp_path / "oxgh" / "issue" / "SKILL.md").read_text()
        assert "```bash" in result
        assert "gh api" in result

    def test_triage_skill(self, tmp_path: Path) -> None:
        skill_dir = PLUGINS_DIR / "oxgh" / "skills" / "triage"
        process_skill("oxgh", skill_dir, tmp_path)

        result = (tmp_path / "oxgh" / "triage" / "SKILL.md").read_text()
        assert "name: oxgh:triage" in result
        assert "Execute each step as a separate command." in result


class TestResolveScriptPaths:
    def test_replaces_relative_with_absolute(self) -> None:
        content = "Run `python3 scripts/wait_for_ai_review.py 42`"
        scripts_dir = Path("/opt/plugins/oxgh/scripts")
        result = resolve_script_paths(content, scripts_dir)
        assert result == "Run `python3 /opt/plugins/oxgh/scripts/wait_for_ai_review.py 42`"

    def test_replaces_multiple_scripts(self) -> None:
        content = "Run `scripts/a.py` then `scripts/b.py`"
        scripts_dir = Path("/abs")
        result = resolve_script_paths(content, scripts_dir)
        assert "/abs/a.py" in result
        assert "/abs/b.py" in result

    def test_no_change_without_scripts(self) -> None:
        content = "Just some text"
        scripts_dir = Path("/abs")
        result = resolve_script_paths(content, scripts_dir)
        assert result == content


class TestInstall:
    def _make_codex_skill(self, codex_dir: Path, plugin: str, skill: str, content: str) -> None:
        skill_dir = codex_dir / plugin / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)

    def test_resolves_script_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        codex_dir = tmp_path / "codex"
        self._make_codex_skill(
            codex_dir,
            "oxgh",
            "wait-for-review",
            "---\nname: oxgh:wait-for-review\n---\nRun `python3 scripts/wait.py 42`\n",
        )
        scripts_dir = codex_dir / "oxgh" / "wait-for-review" / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "wait.py").write_text("# script")

        monkeypatch.setattr(generate_codex, "OUTPUT_DIR", codex_dir)

        dest = tmp_path / "dest"
        dest.mkdir()
        install(dest, ["oxgh"])

        installed = (dest / "oxgh:wait-for-review" / "SKILL.md").read_text()
        abs_path = str(dest / "oxgh:wait-for-review" / "scripts" / "wait.py")
        assert abs_path in installed
        # No bare relative reference (every occurrence should be absolute)
        assert installed.count("scripts/wait.py") == installed.count(abs_path)

    def test_no_resolution_without_scripts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        codex_dir = tmp_path / "codex"
        self._make_codex_skill(codex_dir, "ox", "commit", "---\nname: ox:commit\n---\nJust text\n")

        monkeypatch.setattr(generate_codex, "OUTPUT_DIR", codex_dir)

        dest = tmp_path / "dest"
        dest.mkdir()
        install(dest, ["ox"])

        installed = (dest / "ox:commit" / "SKILL.md").read_text()
        assert installed == "---\nname: ox:commit\n---\nJust text\n"


class TestLink:
    def _make_codex_skill(self, codex_dir: Path, plugin: str, skill: str, content: str) -> None:
        skill_dir = codex_dir / plugin / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)

    def test_resolves_script_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        codex_dir = tmp_path / "codex"
        self._make_codex_skill(
            codex_dir,
            "oxgh",
            "wait-for-review",
            "---\nname: oxgh:wait-for-review\n---\nRun `python3 scripts/wait.py 42`\n",
        )
        scripts_dir = codex_dir / "oxgh" / "wait-for-review" / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "wait.py").write_text("# script")

        monkeypatch.setattr(generate_codex, "OUTPUT_DIR", codex_dir)

        dest = tmp_path / "dest"
        dest.mkdir()
        link(dest, ["oxgh"])

        target = dest / "oxgh:wait-for-review"
        # Should be a real directory (not a symlink to the whole skill dir)
        assert target.is_dir()
        assert not target.is_symlink()

        # SKILL.md should have absolute paths
        linked = (target / "SKILL.md").read_text()
        abs_path = str(codex_dir / "oxgh" / "wait-for-review" / "scripts" / "wait.py")
        assert abs_path in linked
        assert linked.count("scripts/wait.py") == linked.count(abs_path)

        # scripts/ should be a symlink to the source scripts dir
        linked_scripts = target / "scripts"
        assert linked_scripts.is_symlink()
        assert linked_scripts.resolve() == scripts_dir.resolve()

    def test_simple_skill_still_symlinked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        codex_dir = tmp_path / "codex"
        self._make_codex_skill(codex_dir, "ox", "commit", "---\nname: ox:commit\n---\nJust text\n")

        monkeypatch.setattr(generate_codex, "OUTPUT_DIR", codex_dir)

        dest = tmp_path / "dest"
        dest.mkdir()
        link(dest, ["ox"])

        target = dest / "ox:commit"
        assert target.is_symlink()
