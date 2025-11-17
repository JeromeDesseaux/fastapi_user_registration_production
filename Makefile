# Makefile for User Registration API
# Production-grade configuration using Gunicorn + Uvicorn workers

# Detect docker-compose command (supports both old and new syntax)
DOCKER_COMPOSE := $(shell if command -v docker-compose > /dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

.PHONY: help build up down restart logs clean test test-unit test-integration test-e2e shell db-shell diagrams format lint quality

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "User Registration API - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-20s %s\n", $$1, $$2}'

build: ## Build Docker images
	$(DOCKER_COMPOSE) build

up: ## Start all services (production mode)
	$(DOCKER_COMPOSE) up -d
	@echo "✓ Services started (production mode)"
	@echo "API: http://localhost:8000"
	@echo "API docs: http://localhost:8000/docs"
	@echo "Mailhog (E2E testing): http://localhost:8025"

down: ## Stop all services
	$(DOCKER_COMPOSE) down

restart: ## Restart all services
	$(DOCKER_COMPOSE) restart

logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f

logs-api: ## Tail logs from API service only
	$(DOCKER_COMPOSE) logs -f api

logs-celery: ## Tail logs from Celery worker only
	$(DOCKER_COMPOSE) logs -f celery-worker

clean: ## Stop services and remove volumes
	$(DOCKER_COMPOSE) down -v

test: ## Run unit + integration tests (fast)
	@echo "Running unit + integration tests..."
	$(DOCKER_COMPOSE) up -d postgres
	@sleep 3
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false $(DOCKER_COMPOSE) run --rm api pytest tests/unit/ tests/integration/ -v --cov=src --cov-report=term-missing
	$(DOCKER_COMPOSE) down

test-unit: ## Run unit tests only
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false $(DOCKER_COMPOSE) run --rm api pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	$(DOCKER_COMPOSE) up -d postgres
	@sleep 3
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false $(DOCKER_COMPOSE) run --rm api pytest tests/integration/ -v
	$(DOCKER_COMPOSE) down

test-e2e: ## Run E2E tests with real Celery + Mailhog
	@echo "Running E2E tests (starting all services)..."
	ENABLE_METRICS=false ENABLE_RATE_LIMITING=false $(DOCKER_COMPOSE) up -d
	@sleep 8
	$(DOCKER_COMPOSE) run --rm -e API_BASE_URL=http://api:8000 api behave tests/e2e/features/user_registration_e2e.feature
	$(DOCKER_COMPOSE) down

shell: ## Open a shell in the API container
	$(DOCKER_COMPOSE) exec api /bin/sh

db-shell: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d user_registration

diagrams: ## Generate PNG diagrams from Mermaid files
	@echo "Generating diagrams..."
	@for file in docs/diagrams/*.mmd; do \
		filename=$$(basename $$file .mmd); \
		docker run --rm -v $(PWD)/docs/diagrams:/data minlag/mermaid-cli -i /data/$$filename.mmd -o /data/$$filename.png -w 2400 -H 2400; \
	done
	@echo "✓ Diagrams generated in docs/diagrams/"

format: ## Format code with ruff
	$(DOCKER_COMPOSE) run --rm api ruff format src/ tests/

lint: ## Lint code with ruff
	$(DOCKER_COMPOSE) run --rm api ruff check src/ tests/

type-check: ## Type check with mypy
	$(DOCKER_COMPOSE) run --rm api mypy src/

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
	@$(DOCKER_COMPOSE) ps

reset-db: ## Reset database schema (WARNING: deletes all data)
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d user_registration -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo "✓ Database schema reset. Restart services with 'make restart'"
