#!/usr/bin/env python3
"""Format JSON files in the repository."""

import argparse
import json
import sys
from pathlib import Path

EXCLUDE_DIRS = {".venv", ".git", "node_modules", "__pycache__"}


def format_json(path: Path, check: bool) -> bool:
    try:
        content = path.read_text()
        data = json.loads(content)
        formatted = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if content != formatted:
            if check:
                print(f"Would reformat {path}")
                return False
            path.write_text(formatted)
        return True
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: {path}: {e}", file=sys.stderr)
        return False


def find_json_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.json"):
        if not any(part in EXCLUDE_DIRS for part in path.parts):
            files.append(path)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Format JSON files")
    parser.add_argument("--check", action="store_true", help="Check only, don't modify")
    args = parser.parse_args()

    root = Path.cwd()
    files = find_json_files(root)

    results = [format_json(f, args.check) for f in files]
    success = all(results)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
