"""Tests for generate_codex.py."""

import importlib.util
import sys
import textwrap
from pathlib import Path
from types import ModuleType

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
        data = {"name": "commit", "description": "Do stuff"}
        result = serialize_frontmatter(data)
        assert result == "---\nname: commit\ndescription: Do stuff\n---\n"

    def test_boolean(self) -> None:
        data = {"flag": True}
        result = serialize_frontmatter(data)
        assert "flag: true" in result


class TestTransformFrontmatter:
    def test_removes_allowed_tools(self) -> None:
        fm = {"allowed-tools": "Bash(git:*)", "description": "Do stuff"}
        result = transform_frontmatter(fm, "commit")
        assert "allowed-tools" not in result

    def test_removes_disable_model_invocation(self) -> None:
        fm = {"allowed-tools": "Bash(git:*)", "description": "Do stuff", "disable-model-invocation": True}
        result = transform_frontmatter(fm, "shipit")
        assert "disable-model-invocation" not in result

    def test_adds_name(self) -> None:
        fm = {"description": "Do stuff"}
        result = transform_frontmatter(fm, "commit")
        assert result["name"] == "commit"

    def test_keeps_description(self) -> None:
        fm = {"description": "Do stuff"}
        result = transform_frontmatter(fm, "commit")
        assert result["description"] == "Do stuff"

    def test_name_first(self) -> None:
        fm = {"description": "Do stuff"}
        result = transform_frontmatter(fm, "commit")
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
        assert "name: commit" in result
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


class TestEndToEnd:
    """Test processing actual SKILL.md files from the repo."""

    def test_commit_skill(self, tmp_path: Path) -> None:
        skill_dir = PLUGINS_DIR / "ox" / "skills" / "commit"
        process_skill("ox", skill_dir, tmp_path)

        result = (tmp_path / "ox" / "commit" / "SKILL.md").read_text()
        assert "name: commit" in result
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
        assert "name: wait-for-review" in result
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
        assert "name: shipit" in result
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
        assert "name: triage" in result
        assert "Execute each step as a separate command." in result
