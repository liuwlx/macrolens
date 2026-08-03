SHELL := /bin/bash

.PHONY: bootstrap dev up down logs migrate seed api-test web-test lint format

bootstrap:
	cp -n .env.example .env || true
	npm install
	python -m venv .venv
	. .venv/bin/activate && pip install -e 'backend[dev]'

up:
	docker compose up --build -d

up-logs:
	docker compose up --build

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m macrolens_api.cli seed

api-test:
	. .venv/bin/activate && pytest backend/tests -q

web-test:
	npm --workspace apps/web run test

lint:
	. .venv/bin/activate && ruff check backend && mypy backend/src
	npm --workspace apps/web run lint

format:
	. .venv/bin/activate && ruff format backend && ruff check --fix backend
	npm --workspace apps/web run format
