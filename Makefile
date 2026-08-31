.PHONY: lint

lint:
	uvx ruff check .
	uv run pyright
