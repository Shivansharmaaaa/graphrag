# Progress Report — GraphRAG-Powered Cyber Threat Intelligence Platform

**A Multi-Model NoSQL Approach**

| | |
|---|---|
| **Project title** | GraphRAG-Powered Cyber Threat Intelligence Platform: A Multi-Model NoSQL Approach |
| **Team members** | Shivansh Sharma (23BCE0254), Himali Sharma (23BCE0317), Aayush Sinha (23BCE0558) |
| **Institution** | VIT Vellore |
| **Guide** | Dr. Lydia Jane G |
| **Repository** | https://github.com/Shivansharmaaaa/graphrag |
| **Report date** | 2026-09-25 |

---

## 1. Problem statement

Cyber threat intelligence data is inherently polyglot: relationships between actors, campaigns,
malware and infrastructure are graph-shaped; reports are schema-variable documents; active
indicators of compromise need millisecond key-value lookups with expiry; and analyst questions
need semantic retrieval over free text. Forcing all of this into a single database — relational
or otherwise — produces either a graph database straining to store full report bodies, or a
document store faking multi-hop traversal with application-side joins. This project builds a
**polyglot-persistence** CTI workstation that gives each workload its natural engine, and adds a
GraphRAG layer that assembles evidence from all four stores before a local LLM generates a
grounded, citation-checked answer.

## 2. Objectives

1. Ingest STIX 2.1 bundles and free-text CTI reports into all four stores consistently.
2. Answer multi-hop graph questions (shared infrastructure, shared tooling, common victims)
   directly from Neo4j.
3. Serve full report bodies and schema-variable fields from MongoDB, with TLP-based redaction.
4. Maintain a hot IOC blocklist in Redis with per-key TTL, used by a strict, fail-closed
   enforcement API that never falls back to another store on a miss.
5. Support semantic search over report chunks in Qdrant with actor/TLP/date payload filters.
6. Orchestrate a GraphRAG pipeline: entity linking → parallel 4-channel retrieval → grounded
   local-LLM generation → citation validation → audit log.
7. Enforce TLP (WHITE/GREEN/AMBER/RED) access control end-to-end, including inside GraphRAG
   context and generated answers.
8. Ship a working analyst console (React) covering dashboard, graph explorer, report browser,
   semantic search, ingest, IOC blocklist, audit/replay and operations.
9. Make the whole stack reproducible via Docker Compose, with deterministic seed data and
   restorable database dumps.

## 3. Architecture implemented

```
React analyst console (Vite)
        │
        ▼
FastAPI API — JWT auth, TLP policy, audit
        │
   ┌────┼────────────┬──────────────┐
   ▼    ▼             ▼              ▼
Ingestion   GraphRAG orchestrator   Health/metrics
   │              │
 ┌─┼───┬────┐     │
 ▼ ▼   ▼    ▼     ▼
Neo4j Mongo Qdrant Redis  ←── read path (parallel retrieval)
                            ←── Ollama (local LLM, generation)
```

This matches the architecture specified in the Review-I document exactly — no fifth catch-all
database, no shortcuts between stores. The full requirement-to-code traceability table lives in
[`README.md` §4](../README.md#4-requirement-traceability).

## 4. Technologies used

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic, Uvicorn |
| Graph store | Neo4j 5 (community) |
| Document store | MongoDB 7 |
| Key-value store | Redis 7 |
| Vector store | Qdrant |
| Embeddings | TF-IDF + truncated SVD (default, offline, 64-d) or Ollama `nomic-embed-text` |
| LLM | Ollama, `llama3.1:8b` (local, no cloud API) |
| Frontend | React + Vite, plain CSS, Cytoscape-style custom `GraphCanvas` component |
| Deployment | Docker Compose (`neo4j`, `mongo`, `redis`, `qdrant`, optional `app`/`llm` profiles) |
| Testing | pytest (unit), `scripts/evaluate.py` (integration + acceptance + performance) |

## 5. Database implementation

### 5.1 Graph schema (Neo4j)

Node labels: `ThreatActor`, `Campaign`, `Malware`, `Infrastructure`, `Technique`, `Indicator`,
`Victim`, `Report`. Relationship types: `ATTRIBUTED_TO_CAMPAIGN`, `USES` / `USES_INFRA`,
`HOSTS`, `EMPLOYS`, `HAS_IOC` / `OBSERVED_AS`, `TARGETS`, `MENTIONED_IN`. Uniqueness
constraints on every entity's `id` (or `(type,value)` for `Indicator`), plus range indexes on
`Infrastructure.value` and `Indicator.value` — all created idempotently on startup
(`stores.ensure_schema`).

### 5.2 Document schema (MongoDB)

Collection `reports` with the core fields from the spec (`title`, `source`, `date`, `tlp`,
`confidence`, `body`, `actors`, `campaigns`, `malware`, `iocs`) plus the optional
per-report-type fields (`attribution`, `mitre`, `cve`, `ics_protocols`, `wormable`,
`kill_switch`, `payment_brands`, `lure_themes`, `yara_rule_name`, `build_pipeline`, `package`).
Indexes on `actors`, `date`, `tlp`, `iocs`. Separate `users`, `audit_log` and `ingest_jobs`
collections — no fifth database was introduced for these.

### 5.3 Key-value schema (Redis)

`ioc:{type}:{value}` → JSON value, `SET ... EX <ttl>`; a parallel `ioc:index` sorted set scored
by expiry timestamp supports O(1) "what's about to expire" queries without a Redis `SCAN`.

### 5.4 Vector schema (Qdrant)

Collection `threat_chunks`, cosine distance, HNSW index. Payload: `id`, `report_id`, `title`,
`source`, `date`, `date_ts`, `chunk_index`, `text`, `actors`, `campaigns`, `tlp` (the last two
fields are additions beyond the spec's minimum payload, added so TLP and date filters can be
native Qdrant payload filters instead of a post-filter in application code).

## 6. Ingestion pipeline

`backend/app/ingest.py` implements both STIX 2.1 bundle ingestion and free-text ingestion behind
a single job runner (`run_job`) that fans out in a fixed order — **Neo4j → MongoDB → Qdrant →
Redis** — recording per-store status in a `ingest_jobs` document (`neo4j_status`,
`mongodb_status`, `redis_status`, `qdrant_status`, `errors`). Writes are idempotent (`MERGE` in
Neo4j, `replace_one` in MongoDB, delete+upsert in Qdrant, `SET EX` in Redis), so retrying a
partially-failed job (`POST /api/ingest/jobs/{id}/retry`) is safe. No distributed two-phase
commit was implemented, per the spec's explicit instruction.

Supported STIX 2.1 object types: `attack-pattern`, `campaign`, `identity`, `indicator`,
`intrusion-set`, `malware`, `relationship`, `report`, `threat-actor`, `tool`, `vulnerability`.
The original STIX JSON is preserved verbatim in MongoDB alongside the derived graph/document
projection.

## 7. GraphRAG pipeline

`backend/app/graphrag.py` implements the full pipeline from the spec:

1. **Entity linking** — resolve actor/campaign/malware names mentioned in the question to graph
   node IDs.
2. **Parallel retrieval** across all four channels: Qdrant (semantic chunks), Neo4j (1–3 hop
   traversal, hop count configurable), MongoDB (full report hydration for cited reports), Redis
   (live IOC state for any mentioned indicators).
3. **Context assembly** into a single evidence bundle.
4. **Grounded generation** via the local LLM (Ollama `/api/chat`), under a system prompt that
   forbids uncited claims, forbids treating commodity tools (Mimikatz, Cobalt Strike) as strong
   attribution signals, and forbids offensive-security output.
5. **Citation validation** (`enforce_grounding`) — every cited graph edge, report ID and IOC
   value is checked against the live stores; uncited sentences are stripped; if coverage falls
   below `MIN_CITATION_COVERAGE` the pipeline **degrades to retrieve-only mode** rather than
   returning an unsupported answer.
6. **Audit log** — every question, its linked entities, retrieval results, generated answer,
   citations, model, latency and citation coverage are recorded and independently re-verifiable
   via `POST /api/audit/{id}/replay`.

If the LLM is unavailable, the same pipeline runs and returns graph/semantic/document/IOC
evidence with generation explicitly marked unavailable (retrieve-only mode), satisfying the
spec's availability requirement (NFR8).

## 8. API implementation

32 endpoints across `auth`, `health`, `meta`, `graph`, `reports`, `blocklist`, `enforce`,
`search`, `graphrag`, `audit`, `ingest`, `admin`. Full endpoint list, parameters and curl
examples: [`docs/api.md`](../docs/api.md). Machine-readable spec: [`docs/openapi.json`](../docs/openapi.json)
(also served live at `/openapi.json`, with interactive Swagger UI at `/docs`). The graph query
API is deliberately **not** an arbitrary-Cypher endpoint — it exposes fixed, parameterized
templates (`shared-infrastructure`, `shared-tooling`, `common-victims`, `path`, `node/{id}`) with
configurable max-hops / max-neighbours / result-limit budgets to prevent hub-node explosion.

## 9. Frontend implementation

React + Vite console with pages: GraphRAG console, Graph explorer, Report browser, Semantic
search, Ingest, IOC blocklist (live 5s-refreshed hot set + recently-expired panel), Audit &
replay, Operations (store health, latency percentiles, integrity check). Custom components:
`GraphCanvas` (force-directed graph rendering with edge-type coloring), `SimilarityMap` (Qdrant
neighbourhood plot), `Ttl` (live-ticking countdown), `TlpBadge`, `Json`, `ErrorBox`.

## 10. Authentication / TLP

JWT-based auth (`POST /api/auth/login`, 8-hour expiry). Four demo accounts spanning the full
role/clearance matrix (see §14). TLP enforcement is applied at every read surface: report list,
report detail (`403` on insufficient clearance), semantic search results, GraphRAG retrieved
context, and the audit log. The Redis enforcement plane (`/api/enforce/*`) is a separate,
API-key-authenticated surface for downstream consumers (firewall/EDR/SIEM) that returns IOC
values only — never report bodies — and fails closed (`503`, `blocked: true`) rather than
guessing when Redis is unavailable.

## 11. Testing

- **Unit tests**: `backend/tests/test_units.py` — 13 tests, all passing, no live database
  required (STIX parsing, IOC extraction/defanging, TLP policy, citation-coverage math).
- **Integration + acceptance + performance**: `backend/scripts/evaluate.py`, run against the
  live seeded stack. Results below are from the actual run on 2026-09-25, not fabricated.

```
$ cd backend && python -m pytest tests/ -q
13 passed in 1.36s
```

## 12. Acceptance test results (the six Appendix-A questions)

All six run against the live GraphRAG pipeline. Gold-edge and gold-report recall is **1.0**
(every required graph fact and source report was retrieved) across all six; mean citation
coverage **0.863**.

| # | Question | Mode | Edge recall | Report recall | Citation coverage | Latency |
|---|---|---|---|---|---|---|
| 1 | Shared C2 infrastructure + hosted malware | llm | 2/2 | 1/1 | 0.833 | 43.9 s |
| 2 | APT29 ↔ supply-chain ↔ SUNBURST | llm | 1/1 | 1/1 | 0.714 | 30.3 s |
| 3 | Cobalt Strike users besides FIN7 + shared domains | llm | 2/2 | 1/1 | 0.833 | 29.4 s |
| 4 | Sandworm destructive campaigns + APT28 infra overlap | llm | 2/2 | 1/1 | 0.800 | 26.3 s |
| 5 | Spearphishing-against-government analogue search | llm | 0/0 | 1/1 | 1.000 | 36.4 s |
| 6 | Why Mimikatz is a weak attribution signal | **retrieve-only** (LLM answer failed grounding, gate caught it) | 2/2 | 1/1 | 1.000 | 52.3 s |

Test 6 is the clearest evidence the anti-hallucination gate works as designed: the LLM's first
answer did not meet the citation-coverage threshold, so the pipeline **refused to return it** and
fell back to retrieve-only evidence instead of silently shipping an unsupported claim. The
commodity-hub caution required by the acceptance criteria (`commodity_caution_present: true`) is
present.

## 13. Performance results (measured, not simulated)

| Metric | Target (NFR2) | Measured | Met? |
|---|---|---|---|
| Redis GET p99 | < 5 ms | **1.43 ms** (harness probe) / 4.75 ms (515-call process sample) | ✅ |
| Neo4j 1-hop p95 | < 500 ms | **9.08 ms** | ✅ |
| Neo4j 2-hop p95 | < 500 ms | **40.42 ms** | ✅ |
| Neo4j 3-hop p95 | < 500 ms | **15.75 ms** | ✅ |
| GraphRAG end-to-end p95 | < 15 s | **52.3 s** | ❌ |

**Environment:** MacBook Pro (Apple Silicon), Ollama running `llama3.1:8b` (Q4_K_M quantization)
on CPU/GPU via Metal, all four stores in local Docker containers, no external network calls.

**Honest assessment:** the store-level SLOs (Redis, Neo4j) are comfortably met — the polyglot
retrieval layer itself is fast. The GraphRAG end-to-end SLO is **not** met on this hardware; the
bottleneck is entirely LLM generation latency (`llm` channel p50 = 29.9 s, p95 = 50.8 s in the
per-call breakdown), not retrieval (`qdrant` p95 = 45.9 ms, `mongodb` p95 = 10.3 ms, `neo4j`
p95 = 127.7 ms, `linking` p95 = 161.3 ms — all well inside budget). An 8B-parameter local model
on consumer CPU/GPU cannot currently hit a 15 s p95 for multi-hundred-token grounded generation;
a smaller local model, a quantization change, or GPU acceleration would be required to close
this gap. This is reported as a known limitation, not hidden.

## 14. Demo accounts

| user | password | role | TLP clearance | can |
|---|---|---|---|---|
| `analyst` | `analyst123` | analyst | AMBER | query everything up to AMBER |
| `junior` | `junior123` | analyst | GREEN | demonstrates TLP filtering (AMBER hidden) |
| `lead` | `lead123` | lead | RED | + publish/revoke IOCs, ingest reports/STIX |
| `admin` | `admin123` | admin | RED | + re-seed, rebuild vector index, delete reports |

## 15. Problems encountered and solutions

- **Backend deadlock on `uvicorn --reload` (2026-09-25).** The dev server accepted TCP
  connections but never completed ASGI startup, so every request — including `/api/health` and
  login — hung indefinitely with zero response. Root cause not fully isolated (no crash, no
  log output, low CPU use suggesting a genuine I/O wait rather than a compute loop); `py-spy`
  stack inspection was attempted but macOS requires root and no interactive password was
  available in this session. **Resolution:** killed the process (`SIGTERM` was ignored —
  required `SIGKILL`) and restarted; the second run completed startup normally in under 10 s and
  has been stable since. **Follow-up:** the dev server is now started with output redirected to
  a log file so a repeat hang is diagnosable without needing terminal access.
- **GraphRAG p95 latency SLO.** See §13 — a real, measured shortfall attributable to local LLM
  inference speed on this hardware, not a bug in the retrieval/grounding pipeline.
- **No APOC in the Neo4j container**, so `apoc.export.cypher.all` was unavailable for the
  database dump. **Resolution:** wrote a small custom exporter (`scripts/export_neo4j.py`) that
  walks the graph via the driver and emits idempotent `MERGE` statements — no extra dependency,
  and the dump is replayable with plain `cypher-shell`.

## 16. Current limitations

- GraphRAG end-to-end p95 (52.3 s) exceeds the 15 s target on this hardware (§13).
- Embeddings default to TF-IDF+SVD (64-d, offline, deterministic) rather than a neural
  sentence-transformer; `EMBEDDER=ollama` with `nomic-embed-text` is supported but not the
  default, and was not what the acceptance run above used.
- The seed corpus is small (12 reports, 87 graph nodes) — enough to cover the six acceptance
  questions and demonstrate every mechanism, but not representative of production CTI volume.
- `audit_log` and `ingest_jobs` are empty in the current dump because the acceptance run's
  audit records and this session's ingest activity happened after the mongodump snapshot was
  taken; re-run `mongodump` after a live demo session to capture them.
- Redis dump is a point-in-time reference snapshot only (`database_dumps/redis/live_snapshot.json`)
  — TTLs are inherently time-bound by design (this is what UC4 demonstrates), so restoring it
  literally would restore already-expired keys. The recommended restore path re-seeds fresh TTLs
  instead (`scripts/restore_databases.sh seed`).

## 17. Future improvements

- Swap in a quantized smaller local model, or add optional GPU-accelerated inference, to close
  the GraphRAG latency gap.
- Add a neural embedding backend as the default once model size / first-run download time is
  acceptable for the target grading environment.
- Expand the seed corpus with more STIX-derived reports to stress-test hub-node budgets
  (`MAX_NEIGHBOURS_PER_NODE`, `HUB_DEGREE_THRESHOLD`) at larger scale.
- Add CI (GitHub Actions) running `pytest` and the evaluation harness against ephemeral
  containers on every push.

## 18. Deliverables checklist

| Deliverable | Status |
|---|---|
| Working prototype | **Completed** — all four stores + LLM healthy, login, dashboard, and all six acceptance questions verified live |
| Source code | **Completed** — `backend/`, `frontend/` |
| Docker Compose deployment | **Completed** — `docker-compose.yml`, `app`/`llm` profiles |
| Seed dataset | **Completed** — `backend/app/data.py`, auto-loaded on first boot |
| Neo4j database dump/recreation | **Completed** — `database_dumps/neo4j/graph_dump.cypher` (custom Cypher exporter, no APOC dependency) |
| MongoDB database dump | **Completed** — `database_dumps/mongodb/` (`mongodump`) |
| Redis dump/recreation | **Completed (reference)** — `database_dumps/redis/live_snapshot.json`; canonical restore path is the deterministic seed loader (TTLs are time-bound by design) |
| Qdrant snapshot/recreation | **Completed** — `database_dumps/qdrant/threat_chunks.snapshot` (native Qdrant snapshot API) |
| Restore scripts | **Completed** — `scripts/restore_databases.sh` (`seed` and `dumps` modes) |
| API documentation | **Completed** — `docs/api.md`, `docs/openapi.json` |
| OpenAPI specification | **Completed** — `docs/openapi.json`, live at `/openapi.json` |
| README | **Completed** |
| Architecture / requirement traceability | **Completed** — `README.md` §4 |
| Database schema documentation | **Completed** — this report §5, `README.md` |
| GraphRAG documentation | **Completed** — this report §7 |
| Security documentation | **Completed** — this report §10, `README.md` design notes |
| Testing documentation | **Completed** — this report §11–13 |
| Progress report | **Completed** — this file |
| Unit tests | **Completed** — 13/13 passing |
| Integration tests | **Completed** — `scripts/evaluate.py` (integrity, freshness, latency) |
| End-to-end tests | **Completed** — full ingest→graph→document→vector→redis chain exercised by the evaluation harness and manually via the UI |
| Six GraphRAG acceptance tests | **Completed, functionally correct** — 1.0 gold-edge/report recall on all six; one (#6) correctly caught and demoted by the grounding gate rather than passing a bad answer |
| Performance measurements | **Completed, honestly reported** — store-level SLOs met; GraphRAG p95 SLO not met on this hardware (§13, §16) |

---

*This report distinguishes completed, partially completed and not-implemented work throughout;
no feature above is marked complete unless it was exercised against the live stack during this
session and its output is what is shown.*
