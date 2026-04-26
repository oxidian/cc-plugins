CODEX_INSTALL_PLUGINS := ox,oxgh
CODEX_DEV_PLUGINS := ox,oxgh,oxgl

.PHONY: setup dev dev-codex format check codex install-codex link-codex bump bump-check

setup:
	@bash scripts/banner.sh
	uv sync --frozen
	uv run pre-commit install

dev:
	claude --plugin-dir ./plugins/ox --plugin-dir ./plugins/oxgh --plugin-dir ./plugins/oxgl

dev-codex:
	uv run python scripts/generate_codex.py --link .agents/skills --plugins $(or $(PLUGINS),$(CODEX_DEV_PLUGINS))
	codex

format:
	uv sync --frozen
	uv run ruff check --fix .
	uv run ruff format .
	uv run python scripts/format_json.py
	uv run ty check --error-on-warning .
	uv run python scripts/generate_codex.py

check:
	uv sync --frozen
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/format_json.py --check
	uv run ty check --error-on-warning .
	uv run pytest tests/
	uv run python scripts/generate_codex.py --check

codex:
	uv run python scripts/generate_codex.py

install-codex:
	uv run python scripts/generate_codex.py --install $(or $(DEST),$(HOME)/.codex/skills) --plugins $(or $(PLUGINS),$(CODEX_INSTALL_PLUGINS))

link-codex:
	uv run python scripts/generate_codex.py --link $(or $(DEST),$(HOME)/.codex/skills) --plugins $(or $(PLUGINS),$(CODEX_INSTALL_PLUGINS))

bump:
	uv run python scripts/bump.py $(filter-out $@,$(MAKECMDGOALS))
	# Version bumps update plugin manifests that are copied into Codex plugin packages.
	uv run python scripts/generate_codex.py

bump-check:
	uv run python scripts/bump.py --check

%:
	@:
