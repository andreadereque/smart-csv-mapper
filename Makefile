.PHONY: help dev test lint eval ollama-setup

help: ## List the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

dev: ## Run backend and frontend (added in PR 1 and PR 8)
	@echo "nothing to run yet"

test: ## Run all tests
	@echo "no tests yet"

lint: ## Run all linters and the secret scan
	uvx pre-commit run --all-files

eval: ## Run the evals against the local model (added in PR 10)
	@echo "no evals yet"

ollama-setup: ## Start Ollama and download the default model
	brew services start ollama
	ollama pull qwen2.5:3b
