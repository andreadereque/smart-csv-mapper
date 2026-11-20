.PHONY: help dev dev-backend dev-frontend test test-backend test-frontend lint eval ollama-setup install

help: ## List the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies (npm 11 needed)
	cd backend && uv sync
	cd frontend && npx -y npm@11 ci

dev: ## Run backend (:8000) and frontend (:5173) together
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend: ## Run the API on http://localhost:8000 (docs at /docs)
	cd backend && uv run uvicorn smart_csv_mapper.main:create_app --factory --reload --port 8000

test: test-backend test-frontend ## Run all tests

dev-frontend: ## Run the UI on http://localhost:5173 (proxies /api to :8000)
	cd frontend && npm run dev

test-frontend: ## Lint, type-check, test and build the frontend
	cd frontend && npm run lint && npm run typecheck && npm test && npm run build

test-backend: ## Lint, type-check and test the backend
	cd backend && uv run ruff check . && uv run mypy src tests && uv run pytest

lint: ## Run all linters and the secret scan
	uvx pre-commit run --all-files

eval: ## Run the evals against the local model (added in PR 10)
	@echo "no evals yet"

ollama-setup: ## Start Ollama and download the default model
	brew services start ollama
	ollama pull qwen2.5:3b
