# make check  : everything CI would run (backend lint + tests, frontend lint + build)
# Needs Postgres reachable at TEST_DATABASE_URL (docker compose up postgres, or any local Postgres).
PY ?= $(if $(wildcard backend/.venv/Scripts/python.exe),backend/.venv/Scripts/python,$(if $(wildcard backend/.venv/bin/python),backend/.venv/bin/python,python))
PY_ABS = $(abspath $(PY))

.PHONY: check backend-check frontend-check test lint migrate seed dev

check: backend-check frontend-check

backend-check: lint test

lint:
	cd backend && $(PY_ABS) -m ruff check app tests scripts

test:
	cd backend && $(PY_ABS) -m pytest

frontend-check:
	cd frontend && npm run lint && npm run build

migrate:
	cd backend && $(PY_ABS) -m alembic upgrade head

seed:
	cd backend && $(PY_ABS) -m app.seed

dev:
	docker compose up --build
