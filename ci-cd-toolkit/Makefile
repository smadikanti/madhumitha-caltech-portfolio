.DEFAULT_GOAL := help

IMAGE_NAME   ?= ci-cd-toolkit
IMAGE_TAG    ?= latest
REGISTRY     ?= ghcr.io
DOCKER_IMAGE  = $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
COMPOSE       = docker compose

.PHONY: help lint format test test-cov build run stop clean shell deploy logs version

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1m%-15s %s\033[0m\n\n", "Target", "Description"} \
		/^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Code Quality ────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check app/

format: ## Auto-format with ruff
	ruff format app/
	ruff check --fix app/

# ── Testing ─────────────────────────────────────────────────

test: ## Run tests
	python -m pytest app/tests/ -v

test-cov: ## Run tests with coverage
	python -m pytest app/tests/ --cov=app --cov-report=term-missing --cov-report=html

# ── Docker ──────────────────────────────────────────────────

build: ## Build Docker image
	docker build -t $(DOCKER_IMAGE) .

run: ## Start local environment (docker-compose)
	$(COMPOSE) up -d --build

stop: ## Stop local environment
	$(COMPOSE) down

logs: ## Tail application logs
	$(COMPOSE) logs -f app

shell: ## Open shell in running app container
	$(COMPOSE) exec app /bin/sh

clean: ## Remove containers, volumes, and build artifacts
	$(COMPOSE) down -v --remove-orphans
	docker image rm $(DOCKER_IMAGE) 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage .ruff_cache .mypy_cache

# ── Deployment ──────────────────────────────────────────────

deploy: ## Deploy to environment (ENV=dev|staging|prod)
ifndef ENV
	$(error ENV is required. Usage: make deploy ENV=staging)
endif
	bash scripts/deploy.sh $(ENV) $(IMAGE_TAG)

rollback: ## Rollback environment (ENV=dev|staging|prod)
ifndef ENV
	$(error ENV is required. Usage: make rollback ENV=staging)
endif
	bash scripts/rollback.sh $(ENV)

# ── Versioning ──────────────────────────────────────────────

version: ## Bump version (BUMP=major|minor|patch)
ifndef BUMP
	$(error BUMP is required. Usage: make version BUMP=patch)
endif
	bash scripts/version.sh $(BUMP)

release: ## Bump, tag, and push (BUMP=major|minor|patch)
ifndef BUMP
	$(error BUMP is required. Usage: make release BUMP=patch)
endif
	bash scripts/version.sh $(BUMP) --push

# ── Setup ───────────────────────────────────────────────────

setup: ## Install dev dependencies and pre-commit hooks
	pip install -r app/requirements.txt
	pip install ruff pytest pytest-cov pre-commit
	pre-commit install
