#!/usr/bin/env bash
set -euo pipefail

repo_url="${CODEX_PLUGINS_REPO_URL:-https://github.com/oxidian/cc-plugins.git}"
repo_ref="${CODEX_PLUGINS_REPO_REF:-main}"
bootstrap_dir="${CODEX_PLUGINS_BOOTSTRAP_DIR:-.codex/cc-plugins}"
plugins="${CODEX_PLUGINS:-ox,oxgh}"

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

REPO_ROOT="$repo_root"

if [ -f "$repo_root/scripts/utils.sh" ]; then
  # Reuse the repo's setup output style when available.
  source "$repo_root/scripts/utils.sh"
else
  GREEN='\033[32m'
  RED='\033[31m'
  RESET='\033[0m'

  run_step() {
    local description="$1"
    shift
    local tmp_stdout tmp_stderr
    tmp_stdout="$(mktemp)"
    tmp_stderr="$(mktemp)"

    if "$@" >"$tmp_stdout" 2>"$tmp_stderr"; then
      printf '%b %s\n' "${GREEN}✓${RESET}" "$description"
    else
      printf '%b %s\n' "${RED}✗${RESET}" "$description"
      cat "$tmp_stdout"
      cat "$tmp_stderr"
      rm -f "$tmp_stdout" "$tmp_stderr"
      exit 1
    fi

    rm -f "$tmp_stdout" "$tmp_stderr"
  }
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "warning: codex is not installed or not on PATH; skipping Codex plugin installation" >&2
  exit 0
fi

install_codex_plugins() {
  mkdir -p "$(dirname "$bootstrap_dir")" || return

  if [ -d "$bootstrap_dir/.git" ]; then
    git -C "$bootstrap_dir" remote set-url origin "$repo_url" || return
  else
    if [ -e "$bootstrap_dir" ]; then
      echo "$bootstrap_dir exists but is not a git checkout" >&2
      return 1
    fi
    git clone --quiet --filter=blob:none "$repo_url" "$bootstrap_dir" || return
  fi

  git -C "$bootstrap_dir" fetch --quiet --depth 1 origin "$repo_ref" || return
  git -C "$bootstrap_dir" checkout --quiet --detach FETCH_HEAD || return

  python3 "$bootstrap_dir/scripts/install_codex_plugins.py" \
    --cwd "$repo_root" \
    --plugins "$plugins" \
    --quiet || return
}

run_step "Installing Codex plugins" install_codex_plugins
