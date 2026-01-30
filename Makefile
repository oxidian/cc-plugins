setup:
	@bash scripts/banner.sh
	uv sync --frozen
	uv run pre-commit install

format:
	uv sync --frozen
	uv run ruff check --fix .
	uv run ruff format .
	uv run ty check --error-on-warning .

check:
	uv sync --frozen
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check --error-on-warning .
