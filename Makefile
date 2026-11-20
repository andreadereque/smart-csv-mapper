.PHONY: help dev dev-backend test test-backend lint eval ollama-setup

help: ## List the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

dev: dev-backend ## Run the app (frontend added in PR 8)

dev-backend: ## Run the API on http://localhost:8000 (docs at /docs)
	cd backend && uv run uvicorn smart_csv_mapper.main:create_app --factory --reload --port 8000

test: test-backend ## Run all tests

test-backend: ## Lint, type-check and test the backend
	cd backend && uv run ruff check . && uv run mypy src tests && uv run pytest

lint: ## Run all linters and the secret scan
	uvx pre-commit run --all-files

eval: ## Run the evals against the local model (added in PR 10)
	@echo "no evals yet"

ollama-setup: ## Start Ollama and download the default model
	brew services start ollama
	ollama pull qwen2.5:3b
