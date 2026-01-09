.PHONY: help install lint run docker-build docker-run docker-schedule clean

UV := $(shell command -v uv 2> /dev/null)

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install          Install dependencies"
	@echo "  lint             Run linter"
	@echo "  run              Run the import script"
	@echo "  docker-build     Build Docker image"
	@echo "  docker-run       Run import in Docker"
	@echo "  docker-schedule  Start scheduler in Docker"
	@echo "  clean            Clean up temporary files"

install:
	@$(UV) sync

lint:
	@$(UV) run ruff format .
	@$(UV) run ruff check . --fix

run:
	@$(UV) run python main.py

docker-build:
	@docker compose build

docker-run:
	@docker compose run --rm run

docker-schedule:
	@docker compose up schedule

clean:
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .ruff_cache

.DEFAULT_GOAL := help
