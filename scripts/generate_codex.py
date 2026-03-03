#!/usr/bin/env python3
"""Generate Codex-compatible skills from Claude Code SKILL.md files."""

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"
OUTPUT_DIR = REPO_ROOT / "codex" / "skills"
DEFAULT_PLUGINS = "ox,oxgh"

TOOL_CALL_PATTERN = re.compile(
    r"You have the capability to call multiple tools in a single response\."
    r" .*?Do NOT chain commands with && or ;\..*",
    re.DOTALL,
)

TOOL_CALL_REPLACEMENT = "Execute each step as a separate command. Do NOT chain commands with && or ;."


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body.

    Returns (frontmatter_dict, body) where frontmatter_dict maps keys to values.
    """
    if not content.startswith("---\n"):
        return {}, content

    end = content.index("\n---\n", 4)
    fm_text = content[4:end]
    body = content[end + 5 :]

    result: dict[str, str | bool] = {}
    for line in fm_text.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if value == "true":
                result[key] = True
            elif value == "false":
                result[key] = False
            else:
                result[key] = value
        elif line.endswith(":"):
            result[line[:-1]] = True
    return result, body


def serialize_frontmatter(data: dict) -> str:
    """Convert dict back to YAML frontmatter string."""
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def transform_frontmatter(frontmatter: dict, plugin_name: str, skill_name: str) -> dict:
    """Apply frontmatter rules: remove CC-specific keys, add name."""
    result = {"name": f"{plugin_name}:{skill_name}"}
    if "description" in frontmatter:
        result["description"] = frontmatter["description"]
    return result


def transform_context_injections(body: str) -> str:
    """Transform !`cmd` → `cmd` and insert preamble after ## Context heading."""
    if "!`" not in body:
        return body

    # Replace !`cmd` with `cmd`
    body = body.replace("!`", "`")

    # Insert preamble after ## Context line
    context_pattern = re.compile(r"(## Context\n)")
    match = context_pattern.search(body)
    if match:
        insert_pos = match.end()
        preamble = "\nFirst, run these commands and review their output:\n"
        body = body[:insert_pos] + preamble + body[insert_pos:]

    return body


def transform_plugin_root_refs(body: str) -> str:
    """Replace ${CLAUDE_PLUGIN_ROOT}/scripts/ with scripts/."""
    return body.replace("${CLAUDE_PLUGIN_ROOT}/scripts/", "scripts/")


def transform_tool_call_instructions(body: str) -> str:
    """Replace CC-specific tool call paragraphs with simpler Codex instructions."""
    body = TOOL_CALL_PATTERN.sub(TOOL_CALL_REPLACEMENT, body)

    # Also handle the "Chain independent calls together" variant
    body = re.sub(
        r"You have the capability to call multiple tools in a single response\."
        r" Chain independent calls together\.",
        TOOL_CALL_REPLACEMENT,
        body,
    )

    return body


def transform_body(body: str) -> str:
    """Orchestrate all body transforms."""
    body = transform_context_injections(body)
    body = transform_plugin_root_refs(body)
    body = transform_tool_call_instructions(body)
    return body


def detect_script_deps(body: str, plugin_dir: Path) -> list[Path]:
    """Find referenced scripts in the body and return their source paths."""
    scripts: list[Path] = []
    scripts_dir = plugin_dir / "scripts"
    for match in re.finditer(r"scripts/(\S+\.py)", body):
        script_name = match.group(1)
        script_path = scripts_dir / script_name
        if script_path.exists():
            scripts.append(script_path)
    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in scripts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def resolve_script_paths(content: str, scripts_dir: Path) -> str:
    """Replace relative scripts/foo.py references with absolute paths."""
    return re.sub(r"scripts/(\S+\.py)", lambda m: str(scripts_dir / m.group(1)), content)


def process_skill(plugin_name: str, skill_dir: Path, output_dir: Path) -> None:
    """Transform one skill and write to output_dir."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return

    content = skill_md.read_text()
    frontmatter, body = parse_frontmatter(content)
    skill_name = skill_dir.name

    new_fm = transform_frontmatter(frontmatter, plugin_name, skill_name)
    new_body = transform_body(body)

    out_skill_dir = output_dir / plugin_name / skill_name
    out_skill_dir.mkdir(parents=True, exist_ok=True)

    output = serialize_frontmatter(new_fm) + new_body
    (out_skill_dir / "SKILL.md").write_text(output)

    # Copy script dependencies
    plugin_dir = skill_dir.parent.parent
    script_deps = detect_script_deps(new_body, plugin_dir)
    if script_deps:
        out_scripts_dir = out_skill_dir / "scripts"
        out_scripts_dir.mkdir(parents=True, exist_ok=True)
        for script_path in script_deps:
            shutil.copy2(script_path, out_scripts_dir / script_path.name)


def generate(plugins: list[str]) -> None:
    """Generate all Codex skills into OUTPUT_DIR."""
    # Clean output dir for selected plugins
    for plugin_name in plugins:
        plugin_out = OUTPUT_DIR / plugin_name
        if plugin_out.exists():
            shutil.rmtree(plugin_out)

    for plugin_name in plugins:
        skills_dir = PLUGINS_DIR / plugin_name / "skills"
        if not skills_dir.exists():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir():
                process_skill(plugin_name, skill_dir, OUTPUT_DIR)


def check(plugins: list[str]) -> int:
    """Verify generated output matches source. Returns 0 if in sync, 1 if not."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_output = Path(tmpdir) / "codex" / "skills"
        tmp_output.mkdir(parents=True)

        for plugin_name in plugins:
            skills_dir = PLUGINS_DIR / plugin_name / "skills"
            if not skills_dir.exists():
                continue
            for skill_dir in sorted(skills_dir.iterdir()):
                if skill_dir.is_dir():
                    process_skill(plugin_name, skill_dir, tmp_output)

        # Compare
        mismatches: list[str] = []
        for plugin_name in plugins:
            tmp_plugin = tmp_output / plugin_name
            out_plugin = OUTPUT_DIR / plugin_name
            if not tmp_plugin.exists():
                continue
            if not out_plugin.exists():
                mismatches.append(f"{plugin_name}/: missing entirely")
                continue
            for tmp_file in sorted(tmp_plugin.rglob("*")):
                if tmp_file.is_dir():
                    continue
                rel = tmp_file.relative_to(tmp_output)
                out_file = OUTPUT_DIR / rel
                if not out_file.exists():
                    mismatches.append(f"{rel}: missing")
                elif tmp_file.read_text() != out_file.read_text():
                    mismatches.append(f"{rel}: out of date")

            # Check for extra files in output
            for out_file in sorted(out_plugin.rglob("*")):
                if out_file.is_dir():
                    continue
                rel = out_file.relative_to(OUTPUT_DIR)
                tmp_file = tmp_output / rel
                if not tmp_file.exists():
                    mismatches.append(f"{rel}: unexpected file")

        if mismatches:
            print("Codex skills out of sync with source:")
            for m in mismatches:
                print(f"  {m}")
            print("\nRun 'make codex' to regenerate")
            return 1
        print("Codex skills are in sync")
        return 0


def install(dest: Path, plugins: list[str]) -> None:
    """Copy skill directories into dest (standalone, no dependency on this clone)."""
    for plugin_name in plugins:
        plugin_out = OUTPUT_DIR / plugin_name
        if not plugin_out.exists():
            continue
        for skill_dir in sorted(plugin_out.iterdir()):
            if not skill_dir.is_dir():
                continue
            namespaced = f"{plugin_name}:{skill_dir.name}"
            target = dest / namespaced
            if target.exists():
                if target.is_symlink():
                    target.unlink()
                else:
                    shutil.rmtree(target)
            shutil.copytree(skill_dir, target)
            skill_md = target / "SKILL.md"
            if skill_md.exists() and (target / "scripts").is_dir():
                content = skill_md.read_text()
                skill_md.write_text(resolve_script_paths(content, target / "scripts"))
            print(f"Copied {namespaced} → {target}")


def link(dest: Path, plugins: list[str]) -> None:
    """Create per-skill symlinks from dest → this repo's codex/skills/."""
    dest.mkdir(parents=True, exist_ok=True)
    for plugin_name in plugins:
        plugin_out = OUTPUT_DIR / plugin_name
        if not plugin_out.exists():
            continue
        for skill_dir in sorted(plugin_out.iterdir()):
            if not skill_dir.is_dir():
                continue
            namespaced = f"{plugin_name}:{skill_dir.name}"
            target = dest / namespaced
            if target.exists() or target.is_symlink():
                if target.is_symlink() or target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)
            scripts_subdir = skill_dir / "scripts"
            if scripts_subdir.is_dir():
                target.mkdir(parents=True)
                skill_md = skill_dir / "SKILL.md"
                content = skill_md.read_text()
                (target / "SKILL.md").write_text(resolve_script_paths(content, scripts_subdir.resolve()))
                (target / "scripts").symlink_to(scripts_subdir.resolve())
            else:
                target.symlink_to(skill_dir.resolve())
            print(f"Linked {namespaced} → {skill_dir.resolve()}")


def parse_plugins(value: str) -> list[str]:
    """Parse comma-separated plugin names."""
    return [p.strip() for p in value.split(",") if p.strip()]


def all_plugins() -> list[str]:
    """Return all plugin names that have a skills/ directory."""
    return sorted(d.name for d in PLUGINS_DIR.iterdir() if d.is_dir() and (d / "skills").exists())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Codex-compatible skills")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated output is in sync (for CI)",
    )
    parser.add_argument(
        "--install",
        metavar="DEST",
        help="Copy skills into DEST directory",
    )
    parser.add_argument(
        "--link",
        metavar="DEST",
        help="Create per-skill symlinks in DEST directory",
    )
    parser.add_argument(
        "--plugins",
        default=None,
        help=f"Comma-separated plugin names (default for install/link: {DEFAULT_PLUGINS})",
    )
    args = parser.parse_args()

    if args.plugins:
        plugins = parse_plugins(args.plugins)
    elif args.install or args.link:
        plugins = parse_plugins(DEFAULT_PLUGINS)
    else:
        plugins = all_plugins()

    if args.check:
        return check(plugins)

    if args.install:
        generate(plugins)
        install(Path(args.install), plugins)
        return 0

    if args.link:
        generate(plugins)
        link(Path(args.link), plugins)
        return 0

    # Default: generate
    generate(plugins)
    print(f"Generated Codex skills for: {', '.join(plugins)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
