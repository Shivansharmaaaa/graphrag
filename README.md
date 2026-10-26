# GraphRAG-Powered Cyber Threat Intelligence Platform — a multi-model NoSQL approach

Working implementation of the Review-I design (Shivansh Sharma 23BCE0254, Himali Sharma 23BCE0317, Aayush Sinha 23BCE0558 · VIT Vellore · guide Dr. Lydia Jane G).

Four NoSQL engines, each used only for what it does best, plus a GraphRAG layer and an analyst console:

| Store | Engine | What it owns (closed operation set) |
|---|---|---|
| Graph | **Neo4j 5** | STIX-like threat knowledge graph; multi-hop path queries (shared C2, shared tooling, common victims) |
| Document | **MongoDB 7** | Schema-variable reports and raw STIX 2.1 bundles; citation targets; users, audit log, ingest log |
| Key–value | **Redis 7** | Hot IOC blocklist `ioc:{type}:{value}` with per-key `EXPIRE`; enforcement lookups |
| Vector | **Qdrant** | Report chunks (cosine / HNSW) with payload filters (actor, TLP, date) |
| LLM | **Ollama** (local) | Renders retrieved evidence into prose. Optional, and no cloud API is needed |

---

## 1. Folder structure

```
nosql/
├── docker-compose.yml          # neo4j, mongo, redis, qdrant (+ profiles: app, llm)
├── docker-compose.bench.yml    # throwaway stores for `make bench` (alternate ports, no volumes)
├── Makefile                    # make infra | install | api | web | seed | eval | test | test-integration | bench
├── .github/workflows/ci.yml    # CI: unit + integration tests + eval gates against ephemeral stores
├── .env.example                # copy to .env
├── samples/
│   └── stix_apt28_bundle.json  # STIX 2.1 bundle for the ingest demo
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py             # FastAPI: TLP-aware API (all endpoints)
│   │   ├── config.py           # settings from .env
│   │   ├── security.py         # JWT auth, roles, TLP policy, consumer API key
│   │   ├── stores/__init__.py  # connections, health, schema (constraints + indexes)
│   │   ├── graph.py            # Neo4j Cypher library (FR2)
│   │   ├── documents.py        # MongoDB report store (FR6, FR11)
│   │   ├── blocklist.py        # Redis enforcement plane (FR3, FR12)
│   │   ├── vectors.py          # Qdrant chunking / upsert / filtered k-NN (FR4)
│   │   ├── embeddings.py       # local embeddings (TF-IDF+SVD or Ollama)
│   │   ├── extract.py          # entity linking + IOC extraction (refangs defanged IOCs)
│   │   ├── ingest.py           # STIX 2.1 + free-text ingest, fan-out job log, retry (FR1)
│   │   ├── graphrag.py         # 4-channel retrieval, local LLM, groundedness gate, audit/replay
│   │   ├── integrity.py        # cross-model integrity rules (Section 8.5)
│   │   ├── metrics.py          # per-store latency + SLOs (FR9, NFR2)
│   │   ├── seed.py             # initial corpus loader (FR8)
│   │   └── data.py             # public-knowledge corpus: actors, campaigns, malware, reports, IOCs
│   ├── scripts/evaluate.py     # gold paths, latency SLOs, citation coverage, freshness, integrity
│   ├── scripts/benchmark.py    # scalability 1×–200×, load, index ablations, HNSW recall (`make bench`)
│   ├── pytest.ini              # `integration` marker (deselected by default)
│   └── tests/
│       ├── test_units.py       # unit tests (no DB needed)
│       └── test_api.py         # integration tests: the real API against the live stores
├── frontend/                   # React + Vite analyst console
├── review1/                    # Review I report (design)
├── reports/progress-report.md  # Review II progress report
└── review3/                    # Review III deliverables: final report, user manual, slides, demo runbook,
                                #   benchmark results, figures, screenshots and the scripts that build them
    ├── package.json, vite.config.js, index.html, Dockerfile, nginx.conf
    └── src/
        ├── main.jsx, App.jsx, api.js, styles.css
        ├── components/  GraphCanvas, SimilarityMap, Ttl, TlpBadge, Json, ErrorBox
        └── pages/       GraphRAG, GraphExplorer, Reports, Blocklist, Search, Ingest, Audit, Ops, Login
```

---

## 2. Run it (macOS / Linux / Windows-WSL)

**Prerequisites:** Docker Desktop, Python 3.10+, Node 18+. Ollama is optional.

```bash
cd nosql
cp .env.example .env

# 1) the four NoSQL stores
docker compose up -d            # wait ~30 s for Neo4j to report healthy:  docker compose ps

# 2) backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
#   On first start it creates constraints and indexes, then seeds all four stores automatically.
#   API docs: http://localhost:8000/docs

# 3) frontend (new terminal)
cd nosql/frontend
npm install
npm run dev                     # http://localhost:5173

# 4) optional: local LLM for fluent answers (without it the platform runs in retrieve-only mode)
#    install from https://ollama.com, then:
ollama pull llama3.2:3b          # default; meets the 15 s GraphRAG SLO (see §6 for llama3.1)
```

**Hosted databases:** to run on MongoDB Atlas, Neo4j AuraDB, Redis Cloud and Qdrant Cloud instead of local containers, follow `docs/cloud-setup.md` (`.env.cloud`, then `make cloud-check`, `make cloud-seed`, `make cloud-api`).

**See the databases themselves:** `make dbui` starts read-only web consoles for MongoDB (http://localhost:8081) and Redis (http://localhost:8082); Neo4j Browser (http://localhost:7474, `neo4j` / `ctiplatform`) and the Qdrant dashboard (http://localhost:6333/dashboard) are built in. `review3/DATABASE_TOUR.md` lists what to open and which queries to run.

If `make` is installed you can use the shortcuts instead: `make infra`, `make install`, `make api`, `make web`, `make seed`, `make test`, `make test-integration`, `make eval`.

### Tests

| Command | Needs | What it checks |
|---|---|---|
| `make test` | nothing | 16 unit tests: TLP policy, hashing, IOC extraction and refanging, entity linking (including equivalence of the indexed linker with the reference linker), STIX mapping, chunking, the groundedness gate |
| `make test-integration` | `make infra` | 15 API tests against the live stores: auth and roles, TLP on lists, search and GraphRAG context, publish → enforce → revoke, fail-closed enforcement, LLM-down fallback, audit replay, ingest fan-out, delete cascade and integrity. Everything a test writes is removed afterwards |
| `make eval` / `make eval-check` | `make infra` (+ Ollama for `llm` mode) | the six Appendix-A questions (gold edges and reports), latency SLOs, expiry probe, integrity. `eval-check` exits non-zero when a correctness gate fails |

| `make bench` | Docker (stop the demo stack first) | scalability from 1× to 200× the corpus, API load at 1–64 clients, Redis to 500k keys, MongoDB and Neo4j index ablations, Qdrant HNSW recall against exact search. Runs on its own throwaway stack and writes `review3/performance/benchmark_results.json` |

CI (`.github/workflows/ci.yml`) runs the first three on every push against fresh Neo4j, MongoDB, Redis and Qdrant service containers, plus the frontend build. CI has no LLM, so GraphRAG is checked in retrieve-only mode.

**Everything in containers:** `docker compose --profile app up -d --build` → console at http://localhost:5173 (add `--profile llm` for an Ollama container, then run `docker exec cti-ollama ollama pull llama3.2:3b` and set `OLLAMA_URL_DOCKER=http://ollama:11434` in `.env`).

### Demo accounts

| user / password | role | TLP clearance | can |
|---|---|---|---|
| `analyst / analyst123` | analyst | AMBER | query everything up to AMBER |
| `junior / junior123` | analyst | GREEN | shows TLP filtering (AMBER reports hidden) |
| `lead / lead123` | lead | RED | + publish or revoke IOCs, ingest reports and STIX |
| `admin / admin123` | admin | RED | + re-seed, rebuild the vector index, delete reports |

Enforcement consumers (firewall, EDR, SIEM) use the header `X-API-Key: edr-consumer-key`:

```bash
curl -H "X-API-Key: edr-consumer-key" "http://localhost:8000/api/enforce/check?type=ip&value=185.86.77.12"
curl -H "X-API-Key: edr-consumer-key" "http://localhost:8000/api/enforce/export?format=txt"
```

---

## 3. Demo script (UC1–UC4 and Appendix A)

1. **GraphRAG console:** click any of the six Appendix-A questions. The answer shows citation chips (`[G#]` graph edge, `[C#]` Qdrant chunk, `[R:id]` MongoDB report, `[I#]` Redis IOC). Click a chip to jump to it in the evidence panel. The graph hops animate, the similarity map plots the chunks, and IOC TTLs tick down.
2. **UC1 (shared infrastructure):** *"Which actors share C2 infrastructure with APT28?"* The traversal finds Sandworm via the VPS `185.86.77.12` and Scattered Spider via `91.219.236.44`, cites `rpt-001`, and shows the live Redis state of both IPs.
3. **UC2 (semantic analogue):** *"Find activity similar to spearphishing against government and political organizations."* Qdrant returns the DNC chunks, the graph expands to APT28/APT29, and MongoDB hydrates the full reports.
4. **UC3 (commodity tool):** *"Why is Mimikatz a weak attribution signal…"* Five actors use it, so the answer carries a commodity-hub caution.
5. **UC4 (expiry):** open **IOC blocklist**. Three seeded IOCs have 90 s / 120 s / 300 s TTLs. Watch them reach zero and move to *Recently expired*. Then click *show historical graph presence* to see that `OBSERVED_AS` / `HAS_IOC` still exist in Neo4j.
6. **TLP:** sign in as `junior`. AMBER reports disappear from lists, search and GraphRAG context, and opening `/reports/rpt-001` returns 403.
7. **Ingest:** sign in as `lead`, go to **Ingest → STIX 2.1 bundle**, upload `samples/stix_apt28_bundle.json`, and tick *publish indicators*. The job log shows neo4j → mongodb → qdrant → redis. Ask *"diplomatic invitation lures against foreign ministries"* and the new report is retrieved.
8. **Audit & replay:** every answer is logged. **Replay** re-verifies each hop, chunk, document and IOC state against the live stores.
9. **Operations:** store health, p50/p95/p99 per store against the NFR2 SLOs, and the Section 8.5 integrity check.
10. **Evaluation:** `make eval` writes `eval_report.json` (gold-path recall, citation coverage, Redis p99, graph 1–3 hop p95, GraphRAG p95, expiry probe, integrity).

---

## 4. Requirement traceability

| Req | Where it is implemented |
|---|---|
| **FR1** Ingest STIX 2.1 and free text, fan-out | `ingest.py` (`plan_from_stix`, `plan_from_text`, `run_job`), `POST /api/ingest/report`, `/api/ingest/stix`, `/api/ingest/stix/upload`, Ingest page |
| **FR2** Multi-hop graph queries | `graph.py` (`shared_infrastructure`, `shared_tooling`, `common_victims`, `neighbourhood` 1–3 hops, `shortest_path`), Graph explorer |
| **FR3** O(1) lookup, per-key TTL, export | `blocklist.py` (`lookup`, `publish` SET EX + `ioc:index` ZSET), `/api/enforce/check`, `/api/enforce/export` |
| **FR4** Semantic search with filters | `vectors.search` (actor / TLP / date payload filters), `POST /api/search/semantic`, Semantic search page |
| **FR5** GraphRAG Q&A on a local LLM | `graphrag.ask`: Qdrant → Neo4j → MongoDB → Redis → Ollama `/api/chat` |
| **FR6** Hydration | `documents.hydrate`, `GET /api/reports/{id}`, Report browser |
| **FR7** Evidence UI | GraphRAG page evidence panel: animated hops, chunks and similarity map, documents, ticking TTLs, latency |
| **FR8** Corpus + ongoing ingest | `data.py` + `seed.py` (auto on first start, `make seed`), plus the ingest pipeline |
| **FR9** Health / SLO | `stores.health`, `metrics.py`, `GET /api/health`, Operations page, sidebar health dots |
| **FR10** Replay / audit | `graphrag.save_audit`, `graphrag.replay`, `/api/audit`, `/api/audit/{id}/replay`, Audit page |
| **FR11** AuthN + TLP | `security.py` (JWT, roles, clearance). TLP is enforced on list, get, search, GraphRAG context and answer label, and on audit visibility |
| **FR12** Publish / revoke IOC | `POST/DELETE /api/blocklist` (lead role). The graph is never rewritten |
| **NFR1** Data residency | Local Ollama LLM, local embeddings (TF-IDF+SVD or Ollama), no cloud calls |
| **NFR2** Latency | Measured per store (`metrics.py`) and checked in `scripts/evaluate.py`. The LLM sees a trimmed evidence pack (`LLM_MAX_*` settings) because prompt evaluation dominates local-LLM latency |
| **NFR3** Store isolation | The enforcement path reads only Redis. A miss never falls back to MongoDB |
| **NFR4** Groundedness | `enforce_grounding`: uncited sentences are removed, and the answer is refused below `MIN_CITATION_COVERAGE` |
| **NFR5** Reproducibility | Pinned deps, docker-compose, versioned schema (`ensure_schema`, `meta.schema`), deterministic seed |
| **NFR6** Ethics | Public-knowledge corpus with lab IOC values, and a system prompt forbidding offensive output |
| **NFR7** Usability | UC1–UC4 all run inside the console. The evidence panel sits beside every answer |
| **NFR8** Availability | GraphRAG degrades to retrieve-only when the LLM or Redis is down. `/api/enforce/*` returns 503 `blocked:true` (fail closed) |
| **Sec 8.5** Integrity | `integrity.py`, `GET /api/admin/integrity`. Report delete cascades to chunks and `MENTIONED_IN` |
| **Risks (9.1)** | Retrieve-only mode, job log + idempotent retry, hub budget (`MAX_NEIGHBOURS_PER_NODE`, `HUB_DEGREE_THRESHOLD`), refusal gate, orphan-chunk refusal |

---

## 5. API summary (full OpenAPI at `/docs`)

`POST /api/auth/login` · `GET /api/health` · `GET /api/meta`
`GET /api/graph/search|overview|node/{id}|shared-infrastructure|shared-tooling|tool-users/{id}|common-victims|path|indicator/{value}`
`GET /api/reports` · `GET|DELETE /api/reports/{id}`
`GET|POST /api/blocklist` · `GET|DELETE /api/blocklist/{type}/{value}` · `GET /api/enforce/check|export`
`POST /api/search/semantic` · `POST /api/graphrag/ask` · `GET /api/audit` · `GET /api/audit/{id}` · `POST /api/audit/{id}/replay`
`POST /api/ingest/report|stix|stix/upload` · `GET /api/ingest/jobs` · `POST /api/ingest/jobs/{id}/retry`
`GET /api/admin/integrity` · `POST /api/admin/seed|reindex`

---

## 6. Design notes and assumptions

* **Embeddings:** the default is a 64-d TF-IDF + truncated-SVD dense embedding. It is fully offline, deterministic and small enough for a laptop. Set `EMBEDDER=ollama` (after `ollama pull nomic-embed-text`) to use a neural local model, then run *Operations → Rebuild vector index*.
* **Qdrant payload:** `tlp` and `date_ts` are added to the Section 8.4 payload so that FR4's TLP and date filters are native payload filters.
* **Seed TTLs:** operational TTLs are hours to days. Three IOCs are intentionally short-lived so UC4 can be demonstrated live. Re-seed to restore them.
* **Indicator nodes:** network IOCs are linked `Infrastructure -[:OBSERVED_AS]-> Indicator` by value, and file hashes `Malware -[:HAS_IOC]-> Indicator`.
* **Users, audit log and ingest log** live in MongoDB. There is no fifth catch-all database.
* If the Qdrant container is not running, the API falls back to Qdrant's embedded local mode so the rest of the platform still works.
* **LLM prompt budget and model choice:** on a laptop, GraphRAG latency is almost all LLM time, and most of that is evaluating the prompt. The full evidence (up to 60 edges, 10 documents) still goes to the UI and the audit log, but the LLM sees a trimmed pack: the top 30 non-`MENTIONED_IN` facts, 6 documents with 300-character excerpts, and 12 IOC states. Output is capped at 320 tokens, and the model is kept loaded for 30 minutes (`LLM_MAX_FACTS`, `LLM_MAX_DOCS`, `LLM_DOC_CHARS`, `LLM_MAX_IOCS`, `LLM_NUM_PREDICT`, `LLM_KEEP_ALIVE`). Citation ids keep their full-pack numbering, so the groundedness gate is unchanged. Measured on the development MacBook (Apple Silicon, Metal), six Appendix-A questions:

  | `OLLAMA_MODEL` | GraphRAG p95 | mean citation coverage | gold recall | notes |
  |---|---|---|---|---|
  | `llama3.2:3b` (3B, default) | ~10–12 s | 0.82–0.92 | 1.0 | meets the 15 s SLO; terser, and one answer fell back to retrieve-only through the gate |
  | `llama3.1` (8B) | ~21–27 s | 0.82 | 1.0 | fuller answers; misses the 15 s SLO on this hardware |

  The default is `llama3.2:3b` so that NFR2 holds on a laptop. On a machine with a faster GPU, or when answer depth matters more than latency, run `ollama pull llama3.1`, set `OLLAMA_MODEL=llama3.1` in `.env`, and restart the API. The LLM health dot needs the exact tag to be pulled: `llama3.2:1b` does not satisfy `llama3.2:3b`.
* **Scalability fixes (Review III):** the benchmark found four defects that only appear on a large corpus. Entity linking now uses an inverted index instead of one regex per gazetteer entry; the all-actors shared-infrastructure query is bounded and missing nodes are fetched in one batched, index-backed lookup (a label-less `MATCH (n {id:…})` scans every node); ingest links `OBSERVED_AS` only for the plan's values; and each API worker thread gets its own Qdrant client, because the REST client is not safe to share under concurrent load. At 200× the corpus, GraphRAG retrieval p95 fell from 14.7 s to 185 ms. Details: `review3/Final_Report_GraphRAG_CTI_Platform.pdf`, Section 9.
* **Isolated data directory:** `DATA_DIR` (default `backend/data`) holds the fitted embedder and the embedded-Qdrant fallback; the benchmark points it elsewhere so it never touches the demo stack's files.
* **Citation forms:** the groundedness gate also accepts the variants local models commonly write, such as `[G1-G4]`, `(G20)`, `[G1, C2]`, `[rpt-001]` and `[R:001]`. Every tag must still match an id in the context pack. `(C2)` is deliberately not treated as a chunk citation, because in CTI prose it means command-and-control.
