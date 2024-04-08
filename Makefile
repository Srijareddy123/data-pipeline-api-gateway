.PHONY: help install test lint format type-check \
        build up down logs seed migrate shell clean health vehicles diagnostics

PYTHON  := python
PIP     := pip
COMPOSE := docker compose
API_URL := http://localhost:8000/api/v1

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Local dev ─────────────────────────────────────────────────────────────────

install:  ## Install all dependencies (including dev extras)
	$(PIP) install -e ".[dev]"

test:  ## Run tests with coverage
	$(PYTHON) -m pytest

test-fast:  ## Run tests without coverage
	$(PYTHON) -m pytest -x --no-cov -q

lint:  ## Lint with ruff
	$(PYTHON) -m ruff check src tests scripts

format:  ## Format with black
	$(PYTHON) -m black src tests scripts

type-check:  ## Type-check with mypy
	$(PYTHON) -m mypy src

# ── Docker ────────────────────────────────────────────────────────────────────

build:  ## Build Docker image
	$(COMPOSE) build

up:  ## Start postgres, redis, run migrations, start API
	$(COMPOSE) up -d postgres redis
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d api

down:  ## Stop all containers
	$(COMPOSE) down

logs:  ## Tail API logs
	$(COMPOSE) logs -f api

shell:  ## Shell into the API container
	$(COMPOSE) exec api bash

migrate:  ## Run Alembic migrations
	$(COMPOSE) run --rm migrate

seed:  ## Seed the database with sample vehicle and diagnostic data
	$(COMPOSE) --profile seed run --rm seed

# ── One-shot first run ────────────────────────────────────────────────────────

setup: build  ## Build, start, migrate, seed, start API
	$(COMPOSE) up -d postgres redis
	@echo "Waiting for postgres..."
	@sleep 5
	$(COMPOSE) run --rm migrate
	$(COMPOSE) --profile seed run --rm seed
	$(COMPOSE) up -d api
	@echo "Waiting for API..."
	@sleep 5
	$(MAKE) health

# ── Runtime ───────────────────────────────────────────────────────────────────

health:  ## Check API health
	@curl -s $(API_URL)/health | python -m json.tool

vehicles:  ## List first page of vehicles
	@curl -s "$(API_URL)/vehicles?page=1&page_size=5" | python -m json.tool

diagnostics:  ## List recent diagnostic events
	@curl -s "$(API_URL)/diagnostics?page=1&page_size=5" | python -m json.tool

faults:  ## Get fault code summary
	@curl -s "$(API_URL)/diagnostics/fault-summary" | python -m json.tool

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:  ## Remove containers, volumes, and caches
	$(COMPOSE) down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f .coverage coverage.xml
	rm -rf htmlcov .pytest_cache .mypy_cache .ruff_cache
