#!/usr/bin/env python3
"""Auto-detect and bump plugin versions based on changed files."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PLUGINS = {"ox", "oxgh", "oxgl"}


def get_changed_plugins() -> set[str]:
    subprocess.run(["git", "fetch", "origin", "main"], capture_output=True)
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True,
        text=True,
    )
    changed = set()
    for line in result.stdout.splitlines():
        if line.startswith("plugins/"):
            parts = line.split("/")
            if len(parts) >= 2 and parts[1] in PLUGINS:
                changed.add(parts[1])
    return changed


def version_changed(plugin: str) -> bool:
    """Check if plugin.json version differs from origin/main."""
    result = subprocess.run(
        ["git", "show", f"origin/main:plugins/{plugin}/.claude-plugin/plugin.json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return True  # New plugin, no base version
    old_data = json.loads(result.stdout)
    new_data = json.loads(Path(f"plugins/{plugin}/.claude-plugin/plugin.json").read_text())
    return old_data["version"] != new_data["version"]


def bump_version(version: str, bump_type: str) -> str:
    parts = [int(p) for p in version.split(".")]
    if bump_type == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    elif bump_type == "minor":
        parts[1] += 1
        parts[2] = 0
    else:  # patch
        parts[2] += 1
    return ".".join(str(p) for p in parts)


def bump_plugin(plugin: str, bump_type: str) -> tuple[str, str]:
    path = Path(f"plugins/{plugin}/.claude-plugin/plugin.json")
    data = json.loads(path.read_text())
    old_version = data["version"]
    new_version = bump_version(old_version, bump_type)
    data["version"] = new_version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return old_version, new_version


def check_versions() -> int:
    """Verify changed plugins have version bumps. Returns 0 if all pass, 1 if any fail."""
    changed = get_changed_plugins()
    if not changed:
        print("No plugin changes detected")
        return 0

    failed = []
    for plugin in sorted(changed):
        if version_changed(plugin):
            print(f"✓ {plugin}: version bumped")
        else:
            print(f"✗ {plugin}: version not bumped")
            failed.append(plugin)

    if failed:
        print(f"\nRun 'make bump' to bump versions for: {', '.join(failed)}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump plugin versions")
    parser.add_argument(
        "type", nargs="?", default="patch", choices=["major", "minor", "patch"], help="Version bump type"
    )
    parser.add_argument("--check", action="store_true", help="Check if versions were bumped (for CI)")
    args = parser.parse_args()

    if args.check:
        return check_versions()

    changed = get_changed_plugins()
    if not changed:
        print("No plugin changes detected")
        return 0

    for plugin in sorted(changed):
        old, new = bump_plugin(plugin, args.type)
        print(f"{plugin}: {old} → {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
