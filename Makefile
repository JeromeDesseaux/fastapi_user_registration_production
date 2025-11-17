# Makefile for User Registration API
# Production-grade configuration using Gunicorn + Uvicorn workers

.PHONY: help build up down restart logs clean test test-unit test-integration test-e2e shell db-shell diagrams format lint quality

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "User Registration API - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-20s %s\n", $$1, $$2}'

build: ## Build Docker images
	docker-compose build

up: ## Start all services (production mode)
	docker-compose up -d
	@echo "✓ Services started (production mode)"
	@echo "API: http://localhost:8000"
	@echo "API docs: http://localhost:8000/docs"
	@echo "Mailhog (E2E testing): http://localhost:8025"

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Tail logs from all services
	docker-compose logs -f

logs-api: ## Tail logs from API service only
	docker-compose logs -f api

logs-celery: ## Tail logs from Celery worker only
	docker-compose logs -f celery-worker

clean: ## Stop services and remove volumes
	docker-compose down -v

test: ## Run unit + integration tests (fast)
	@echo "Running unit + integration tests..."
	docker-compose up -d postgres
	@sleep 3
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false docker-compose run --rm api pytest tests/unit/ tests/integration/ -v --cov=src --cov-report=term-missing
	docker-compose down

test-unit: ## Run unit tests only
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false docker-compose run --rm api pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	docker-compose up -d postgres
	@sleep 3
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false docker-compose run --rm api pytest tests/integration/ -v
	docker-compose down

test-e2e: ## Run E2E tests with real Celery + Mailhog
	@echo "Running E2E tests (starting all services)..."
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false docker-compose up -d
	@sleep 8
	docker-compose run --rm -e API_BASE_URL=http://api:8000 api behave tests/e2e/features/user_registration_e2e.feature
	docker-compose down

shell: ## Open a shell in the API container
	docker-compose exec api /bin/sh

db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U postgres -d user_registration

diagrams: ## Generate PNG diagrams from Mermaid files
	@echo "Generating diagrams..."
	@for file in docs/diagrams/*.mmd; do \
		filename=$$(basename $$file .mmd); \
		docker run --rm -v $(PWD)/docs/diagrams:/data minlag/mermaid-cli -i /data/$$filename.mmd -o /data/$$filename.png -w 2400 -H 2400; \
	done
	@echo "✓ Diagrams generated in docs/diagrams/"

format: ## Format code with ruff
	docker-compose run --rm api ruff format src/ tests/

lint: ## Lint code with ruff
	docker-compose run --rm api ruff check src/ tests/

type-check: ## Type check with mypy
	docker-compose run --rm api mypy src/

quality: ## Run all quality checks (format + lint + type-check)
	@echo "Running quality checks..."
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) type-check
	@echo "✓ Quality checks complete"

install: ## First-time setup (build + start)
	@echo "Setting up project..."
	$(MAKE) build
	$(MAKE) up
	@echo ""
	@echo "✓ Setup complete"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"
	@echo "Run tests: make test"

status: ## Show status of all services
	@docker-compose ps
