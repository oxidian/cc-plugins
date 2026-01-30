setup:
	@bash scripts/banner.sh
	uv sync --frozen
	uv run pre-commit install

dev:
	claude --plugin-dir ./plugins/ox --plugin-dir ./plugins/oxgh --plugin-dir ./plugins/oxgl

format:
	uv sync --frozen
	uv run ruff check --fix .
	uv run ruff format .
	uv run python scripts/format_json.py
	uv run ty check --error-on-warning .

check:
	uv sync --frozen
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/format_json.py --check
	uv run ty check --error-on-warning .

bump:
	uv run python scripts/bump.py $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
