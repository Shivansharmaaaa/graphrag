# Review III — demo runbook and viva preparation

A 6–8 minute live demo of the CTI Workstation, what to say at each step, what to do when something goes wrong, and short answers to the questions examiners are most likely to ask. The numbers quoted here come from `review3/performance/` (runs of 2026-10-25).

---

## 1. Before the demo

**30 minutes before**

```bash
docker compose --profile app up -d --build     # stores + API + console on http://localhost:5173
make dbui                                      # read-only consoles: MongoDB :8081, Redis :8082
ollama pull llama3.2:3b                        # already pulled? this is a no-op
make test && make test-integration             # 18 + 16 tests, ~10 s
```

- Close heavy applications; the Docker VM has 2 vCPUs shared by every engine.
- Open http://localhost:5173 in a browser window about 1440 px wide, so the evidence panel sits beside the answer.
- Keep a terminal open in the project folder for the enforcement-API calls (step 7).

**5 minutes before**

```bash
make seed                                                      # fresh TTLs: the 90 s / 120 s / 300 s IOCs restart now
curl -s localhost:11434/api/generate -d '{"model":"llama3.2:3b","keep_alive":"30m"}' >/dev/null   # load the model
```

- Sign in as **analyst**, ask one example question to warm every store, and check that all five sidebar dots are green.
- Have the slide deck open at slide 23 ("Six minutes, four use cases").

---

## 2. Demo script

**Start with the databases themselves** (about 3 minutes, details and queries in [DATABASE_TOUR.md](DATABASE_TOUR.md)): Neo4j Browser at http://localhost:7474 (`CALL db.schema.visualization()`, then the APT28 shared-infrastructure query), mongo-express at http://localhost:8081 (cti → reports → rpt-002 and rpt-004), Redis Commander at http://localhost:8082 (ioc → ip → 185.86.77.12 and its TTL), and the Qdrant dashboard at http://localhost:6333/dashboard (threat_chunks → Points, Visualize). *"These are four real database servers; the application sits on top of them."*

Then the application:

| # | Time | Do | Expect | Say |
|---|---|---|---|---|
| 1 | 0:00 | GraphRAG console → click **Which threat actors share command-and-control infrastructure…** | `llm` answer in ~10 s; APT28 and Sandworm via 185.86.77.12; chips G/C/R/I | "Four stores answered this. Each chip is a graph edge, a passage, a report or an IOC state." |
| 2 | 0:45 | Click a **G** chip, then the **IOC state** tab | the cited edge lights up; IPs show live with TTL | "The answer can't say anything the stores don't contain — and it tells us whether each IP is still blocked." |
| 3 | 1:30 | Click **Why is Mimikatz a weak attribution signal…** | five actors; amber ⚠ commodity-hub caution | "The graph knows Mimikatz is a hub — five unrelated actors use it — so the answer must warn against attributing on it." |
| 4 | 2:15 | Click **Find activity similar to spearphishing…** → **Chunks** tab | DNC passages, similarity map | "That one is a similarity question, so Qdrant leads and the graph expands from the actors it finds." |
| 5 | 3:00 | **IOC blocklist** | three short-TTL IOCs counting down; one may already be in *Recently expired* | "Redis enforces expiry per key. When the TTL hits zero it stops being blocked…" → click **show historical graph presence** → "…but the graph still remembers it. History and enforcement are allowed to disagree." |
| 6 | 3:45 | **Sign out → sign in as junior** (GREEN) → **Report browser**, then open `/reports/rpt-001` | AMBER reports hidden with a count; rpt-001 withheld (403) | "TLP is enforced inside every store query, including vector search and the GraphRAG context — not after the answer is written." |
| 7 | 4:30 | Terminal: `curl -H "X-API-Key: edr-consumer-key" "localhost:5173/api/enforce/check?type=ip&value=185.86.77.12"` | `{"blocked": true, "ttl_remaining": …}` | "This is what a firewall sees: Redis only, O(1). If Redis is down it answers 503 with blocked:true — fail closed." |
| 8 | 5:00 | Sign in as **lead** → **Ingest → STIX 2.1 bundle** → `samples/stix_apt28_bundle.json`, tick **publish indicators**, **Run ingest job** | four green steps: neo4j → mongodb → qdrant → redis | "One job fans out to all four stores, logged step by step, retryable from the step that failed." |
| 9 | 5:45 | **Audit & replay** → newest entry → **Replay against the stores** | hops n/n, chunks, documents, IOC state changes | "Any answer can be re-verified later against the live stores." |
| 10 | 6:30 | **Operations** | all stores up, latency against SLOs, integrity OK | "Health, per-store latency against our targets and the cross-store integrity rules, live." Then switch to the performance slides. |

After the demo, run `make seed` again if you need a clean corpus (step 8 added a report).

### Variant: hosted databases and real data

To demonstrate on the vendors' cloud services with real threat intelligence (setup in `docs/cloud-setup.md`):

```bash
make cloud-check                                   # all four lines: OK … hosted
make cloud-import-feeds                            # only if the feeds are older than a few days (TTLs 1–7 days)
docker compose --profile app stop                  # free ports 8000 and 5173
TRUST_FORWARDED_FOR=true make cloud-api            # terminal 1
make web                                           # terminal 2
```

| Do | Expect | Say |
|---|---|---|
| **Operations** | four cloud hostnames; 2,118 nodes, 249 reports, ~515 live IOCs | "Same code, now on AuraDB, Atlas, Redis Cloud and Qdrant Cloud, holding MITRE ATT&CK and two live IP feeds." |
| Ask *Which groups are attributed to the SolarWinds Compromise campaign and what malware was used?* | APT29, SUNBURST, GoldMax, SUNSPOT …, cited | "ATT&CK's campaign merged onto our own SolarWinds node, so graph and documents line up." |
| Terminal: `curl -i -H 'X-Forwarded-For: 50.16.16.211' localhost:8000/api/reports` | `403 … is on the IOC blocklist` | "That address is a QakBot C2 server from abuse.ch. Any request from it is refused…" |
| **IOC blocklist** → *Requests blocked by the API* | the refusal with its log-expiry time | "…and logged in Atlas with a TTL index, so the log cleans itself up after 7 days." |

Allow for internet latency: GraphRAG takes 10–20 s on the free tiers. In Atlas, the current network's IP must be on the access list (Security → Network Access).

---

## 3. If something goes wrong

| Problem | Recovery (keep talking) |
|---|---|
| Answer takes > 20 s or the `llm` dot is red | Untick **use local LLM** and ask again: the retrieve-only answer is instant and still fully cited. "This is the NFR8 degradation path." |
| A short-TTL IOC already expired before step 5 | Good — it is in *Recently expired*; go straight to **show historical graph presence**. |
| The model's answer is refused or shows `retrieve-only (llm answer failed grounding)` | Point it out: "the gate caught an under-cited draft and replaced it with evidence sentences — that is the safety net." |
| A store dot is red | `docker compose ps`; `docker compose up -d <store>`; Neo4j takes ~30 s. Continue on another page meanwhile. |
| Browser shows the login page unexpectedly | The 8-hour session expired or the API restarted; sign in again. |
| Port 5173 / 8000 conflict | `docker compose --profile app stop` then `docker compose --profile app up -d`. |
| `make cloud-check` fails for MongoDB with an SSL/TLS error | Atlas does not know this network: Atlas → Security → Network Access → Add current IP; or switch to the local stack. |
| Everything is down | Present from the screenshots in `review3/screenshots/` and the slides; the report has the full results. |

---

## 4. Likely questions and short answers

**Why four databases instead of one?**
Each workload has a different native operator: multi-hop paths (graph), schema-variable documents, O(1) lookups with per-key expiry (key–value), approximate k-NN with filters (vector). Forcing them into one engine means application-side joins, report bodies in graph nodes, or polling for expiry. Section 9 shows each store staying in its millisecond budget at 200× scale.

**Why not PostgreSQL with pgvector and a JSONB column?**
It can store all four shapes, but multi-hop traversal becomes recursive joins whose cost grows with table size, and TTL expiry needs a sweeper job. Our Neo4j 2-hop p95 stays between 5 and 11 ms from 87 to 15,012 nodes because traversal is local (index-free adjacency). The project's point is choosing the right model per workload.

**How do you keep four stores consistent without distributed transactions?**
Ingest is a job with a fixed step order (Neo4j → MongoDB → Qdrant → Redis), each step idempotent and logged in `ingest_jobs`; a failed job resumes from the first unfinished step. Qdrant refuses to index a document whose Report node is missing, GraphRAG refuses orphan chunks, and three hard integrity rules are checked on demand and by the evaluation gate.

**How do you stop the LLM from hallucinating?**
The model only renders evidence it is given. Every sentence must carry a citation id that exists in the context pack; uncited sentences are removed; below 50% coverage the answer is refused and replaced by deterministic evidence sentences. The model never retrieves or writes data. In the final run all six questions recalled their gold evidence; one draft was caught by the gate.

**Why is the coverage threshold 0.5?**
It balances fluency and safety: models often add a connective sentence without a tag. Below half, the answer is mostly unsupported, so we refuse. It is configurable (`MIN_CITATION_COVERAGE`).

**Why llama3.2:3b and not llama3.1:8b?**
The 15 s p95 target. With the prompt budget, llama3.1 measures 21–27 s and llama3.2:3b 9.5–12.4 s on this laptop, both with 100% gold recall. The 8B model writes fuller prose; switching is one setting (`OLLAMA_MODEL`).

**What made the LLM path faster?**
Profiling: 17 s of a 24 s llama3.1 call was prompt evaluation of a ~5,000-token context. The prompt budget (top 30 facts without MENTIONED_IN, 6 documents × 300 characters, 12 IOC states) halves it; an output cap and keep-alive do the rest. The UI and audit still get the full evidence.

**Is synthetic scaling data valid?**
It is a stress test of the code paths, not of answer quality. Clones go through the production seed loader, share ATT&CK techniques and commodity tools (so hubs grow realistically) and get cross-clone edges. Index experiments use independent random data so caching cannot flatter them. We state these threats to validity in Section 9.1.

**What did the benchmark find?**
Four defects invisible on the seed corpus: entity linking was one regex per gazetteer entry (379 ms → 0.06 ms with an inverted index); a global query was unbounded and fetched nodes one at a time with a label-less MATCH, a full scan each (retrieval p95 at 200×: 14.7 s → 185 ms); ingest re-joined the whole graph (1.5 → 31.6 reports/s); and a Qdrant client shared across threads caused HTTP 500s under load (now one per thread, 0 errors).

**How do you know the new entity linker is correct?**
A unit test runs the original regex linker as a reference and asserts identical output on tricky inputs — subdomains, hyphen and underscore boundaries, multi-word aliases, refanged IOCs. Candidates from the index are always confirmed with the original word-boundary rule.

**Your collection is tiny — does HNSW even matter?**
At 25 chunks (5,000 at 200×) Qdrant searches exactly, which is optimal at that size. The HNSW experiment shows what happens as the corpus grows: at 100k points HNSW is ~2 ms against ~4 ms for exact with recall@10 0.999 (ef 64); with a TLP filter it needs ef 128 to keep recall at 0.998.

**How is TLP enforced in vector search?**
As a Qdrant payload filter (`tlp ∈ allowed levels`) inside the k-NN query, so restricted chunks are never candidates. MongoDB uses a `$in` filter and the graph channel drops Report nodes above clearance. The answer is labelled with the highest TLP it cites.

**What is the hub budget?**
Traversals may end at, but never pass through, a node with more than 12 relationships (`MAX_NEIGHBOURS_PER_NODE`). It keeps Mimikatz or Cobalt Strike from pulling in the whole graph and caps evidence at 60 edges at every scale. Malware used by five or more actors is flagged as a commodity hub (`HUB_DEGREE_THRESHOLD`).

**What happens if Redis goes down?**
The enforcement API returns 503 with `blocked: true` (fail closed — a consumer should block). The analyst read path keeps working; IOC state shows "unknown". An integration test simulates exactly this.

**How does the STIX mapping work?**
SDOs map to labels (intrusion-set/threat-actor → ThreatActor, tool/malware → Malware, attack-pattern → Technique by ATT&CK id); objects merge into existing nodes by name or alias; relationship types map to the graph vocabulary (attributed-to is reversed into ATTRIBUTED_TO_CAMPAIGN); TLP comes from marking definitions; indicator `valid_until` becomes the Redis TTL.

**How does replay work?**
Each answer stores the ids of its hops, chunks, documents and IOC states. Replay checks each edge still exists in Neo4j, each point still maps to the same report in Qdrant, each document exists in MongoDB with a Report node, and compares IOC state now with then.

**How is this different from OpenCTI or MISP?**
MISP disseminates events; OpenCTI is a graph-backed product. Neither treats TTL enforcement, narrative similarity and cited question answering as co-equal planes, and neither offers per-sentence citations with replay. That is gaps G2–G5 from Review I.

**How would you take this to production?**
Several Uvicorn workers or replicas behind a load balancer (one worker peaks at ~1,500 enforcement checks/s on 2 vCPUs), Neo4j and MongoDB clustering, Redis replication, secrets from a vault, SSO for analysts, a TAXII connector for real feeds. None needs a design change.

**What about the CAP theorem?**
Each store makes its own trade-off; the platform tolerates the resulting short windows by ordering ingest steps, retrying idempotently and refusing to cite evidence that is not present in all the stores it needs.

**Why TF-IDF embeddings?**
Fully offline, deterministic (fixed random state) and small enough for a laptop, which suits reproducibility. `EMBEDDER=ollama` with `nomic-embed-text` is supported; rebuild the vector index after switching.

**How do you test all this?**
16 unit tests, 15 integration tests against live stores (self-cleaning), an evaluation gate that fails on any missed gold edge or report, and CI that runs them on fresh containers on every push. `make bench` reproduces Section 9.
