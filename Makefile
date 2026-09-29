# Makefile — convenience targets for the Incident Memory Command Center
# Requires: Python 3.11+, Node.js 20+, GNU make or nmake.
# On Windows without make, use the equivalent bash/pwsh scripts instead.

PYTHON   := .venv/bin/python
PIP      := .venv/bin/pip
PYTEST   := .venv/bin/pytest
RUFF     := .venv/bin/ruff

# ─── setup ───────────────────────────────────────────────────────────────────
.PHONY: setup
setup:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt -r backend/requirements-dev.txt
	$(PIP) install ruff pip-audit
	cd frontend && npm ci --legacy-peer-deps

# ─── dev ─────────────────────────────────────────────────────────────────────
.PHONY: dev
dev: build-frontend
	$(PYTHON) -m uvicorn app.main:app \
	    --app-dir backend --host 127.0.0.1 --port 8000 --reload

# ─── build ───────────────────────────────────────────────────────────────────
.PHONY: build build-frontend
build: build-frontend
	@echo "Backend has no compile step. Run 'make docker-build' for the container image."

build-frontend:
	cd frontend && node build.mjs

# ─── test ────────────────────────────────────────────────────────────────────
.PHONY: test test-backend test-frontend
test: test-backend test-frontend

test-backend:
	cd backend && $(PYTEST) tests/ -q -m "not live"

test-frontend:
	cd frontend && npm run test:run

# ─── lint / audit ─────────────────────────────────────────────────────────────
.PHONY: lint audit
lint:
	$(RUFF) check backend/app/ backend/tests/
	$(RUFF) format backend/app/ backend/tests/ --check

audit:
	$(PIP) install pip-audit
	$(VENV)/bin/pip-audit -r backend/requirements.txt
	cd frontend && npm audit --audit-level=high

# ─── docker ──────────────────────────────────────────────────────────────────
.PHONY: docker-build docker-up docker-down
docker-build:
	docker build -t incident-memory-command-center .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
