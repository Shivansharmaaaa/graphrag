# GraphRAG CTI Platform — local helpers
.PHONY: infra down install api web seed eval eval-check bench test test-integration llm app dbui

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

BENCH_ENV = CTI_BENCH=1 NEO4J_URI=bolt://localhost:17687 MONGO_URI=mongodb://localhost:27018 \
	REDIS_URL=redis://localhost:16379/0 QDRANT_PORT=16333 OLLAMA_URL=http://127.0.0.1:9 \
	DATA_DIR=$(CURDIR)/backend/data/bench

bench:            ## scalability / indexing / load benchmarks on a throwaway stack (~15 min; stop the demo stack first for clean numbers)
	docker compose -p cti-bench -f docker-compose.bench.yml up -d --wait
	cd backend && $(BENCH_ENV) ../.venv/bin/python -m scripts.benchmark $(ARGS); \
	  status=$$?; cd .. && docker compose -p cti-bench -f docker-compose.bench.yml down -v; exit $$status

test:             ## unit tests (no databases needed)
	cd backend && ../.venv/bin/python -m pytest -q

test-integration: ## API tests against the live stores (make infra first); cleans up after itself
	cd backend && ../.venv/bin/python -m pytest -q -m integration

app:              ## everything in containers
	docker compose --profile app up -d --build

dbui:             ## open each NoSQL database in its own console (the stores must be running)
	docker compose --profile dbui up -d mongo-express redis-commander
	@echo "Neo4j    http://localhost:7474            (user neo4j / ctiplatform)"
	@echo "MongoDB  http://localhost:8081            (database cti)"
	@echo "Redis    http://localhost:8082            (keys ioc:*)"
	@echo "Qdrant   http://localhost:6333/dashboard  (collection threat_chunks)"
