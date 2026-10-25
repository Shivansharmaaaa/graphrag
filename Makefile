# GraphRAG CTI Platform — local helpers
.PHONY: infra down install api web seed eval eval-check test test-integration llm app

infra:            ## start Neo4j, MongoDB, Redis, Qdrant
	docker compose up -d

down:
	docker compose down

install:          ## python venv + frontend deps
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

api:              ## FastAPI on :8000 (auto-seeds empty stores on first start)
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

web:              ## analyst console on :5173
	cd frontend && npm run dev

seed:             ## (re)load the initial corpus into all four stores
	cd backend && ../.venv/bin/python -m app.seed

llm:              ## pull the local model (Ollama must be running)
	ollama pull llama3.2:3b

eval:             ## Review-III style evaluation: gold paths, SLOs, citation coverage
	cd backend && ../.venv/bin/python -m scripts.evaluate

eval-check:       ## same, but exit non-zero if a correctness gate fails (used by CI)
	cd backend && ../.venv/bin/python -m scripts.evaluate --check

test:             ## unit tests (no databases needed)
	cd backend && ../.venv/bin/python -m pytest -q

test-integration: ## API tests against the live stores (make infra first); cleans up after itself
	cd backend && ../.venv/bin/python -m pytest -q -m integration

app:              ## everything in containers
	docker compose --profile app up -d --build
