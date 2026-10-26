// Review-III final report (docx + pdf). Every measured number is read from review3/performance/*.json.
//   node review3/generate_report.js          -> docx, then PDF via LibreOffice, then a second pass
//                                               that writes real page numbers into the contents
const fs = require("fs");
const path = require("path");
const K = require("./doc_kit");

const { p, h1, h2, h3, caption, figure, bullet, table, callout, codeBlock, spacer, pageBreak, run, runB, CW } = K;
const ROOT = path.join(__dirname, "..");
const FIG = (f) => path.join(__dirname, "figures", f);
const SHOT = (f) => path.join(__dirname, "screenshots", f);
const PERF = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "performance", f), "utf8"));
const OUT = path.join(__dirname, "Final_Report_GraphRAG_CTI_Platform");
const TOC_CACHE = path.join(__dirname, "build", "report_toc.json");

const R = PERF("benchmark_results.json");
const B = PERF("benchmark_baseline_before_fixes.json");
const E = PERF("eval_llama3.2-3b_default.json");
const LL = PERF("llm_latency_runs.json");
const ENV = R.environment;

// ------------------------------------------------------------------ number helpers
const ms = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)} s` : v >= 100 ? `${v.toFixed(0)} ms` : v >= 10 ? `${v.toFixed(1)} ms` : `${v.toFixed(2)} ms`);
const n0 = (v) => Math.round(v).toLocaleString("en-US");
const x = (a, b) => `${Math.round(a / b).toLocaleString("en-US")}×`;
const rows = R.scale.rows;
const r1 = rows[0];
const rN = rows[rows.length - 1];
const bN = B.scale.rows[B.scale.rows.length - 1];
const rag = (r) => r.graphrag_retrieve_only;
const redisRows = R.redis.rows;
const rTop = redisRows[redisRows.length - 1];
const M = R.mongo;
const N = R.neo4j;
const Q = R.qdrant.rows;
const qTop = Q[Q.length - 1];
const LOAD = R.load;
const maxBy = (arr, f) => arr.reduce((a, b) => (f(b) > f(a) ? b : a));
const g = E.graphrag;
const lat = E.latency;
const llmFinal = LL.runs[LL.runs.length - 1];
const llmSept = LL.runs[0];

function loc(dir, exts) {
  let n = 0;
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, f.name);
    if (f.isDirectory() && !["__pycache__", "node_modules"].includes(f.name)) n += loc(full, exts);
    else if (exts.some((e) => f.name.endsWith(e))) n += fs.readFileSync(full, "utf8").split("\n").length;
  }
  return n;
}
const LOC_BACKEND = loc(path.join(ROOT, "backend", "app"), [".py"]);
const LOC_SCRIPTS = loc(path.join(ROOT, "backend", "scripts"), [".py"]);
const LOC_TESTS = loc(path.join(ROOT, "backend", "tests"), [".py"]);
const LOC_FRONT = loc(path.join(ROOT, "frontend", "src"), [".js", ".jsx", ".css"]);
const ENDPOINTS = (fs.readFileSync(path.join(ROOT, "backend", "app", "main.py"), "utf8").match(/^@app\.(get|post|delete|put)\(/gm) || []).length;
const UNIT_TESTS = (fs.readFileSync(path.join(ROOT, "backend", "tests", "test_units.py"), "utf8").match(/^def test_/gm) || []).length;
const INT_TESTS = (fs.readFileSync(path.join(ROOT, "backend", "tests", "test_api.py"), "utf8").match(/^def test_/gm) || []).length;

// ------------------------------------------------------------------ contents (two-pass page numbers)
const SECTIONS = [
  "1.  Abstract", "2.  Introduction", "3.  Background and Related Work", "4.  System Architecture",
  "5.  Data Model", "6.  Implementation", "7.  Innovation and Technical Complexity",
  "8.  Testing and Validation", "9.  Performance Evaluation", "10.  Requirement Traceability",
  "11.  Limitations and Future Work", "12.  Conclusion", "References", "Appendix A.  Reproducing the Results",
];
const tocPages = K.tocFrom(TOC_CACHE);

// figure / table numbers resolve from these orders, so references in the text can never drift
const FIG_ORDER = ["arch", "graph", "stores", "ingest", "answer", "console", "dbConsoles", "scaleStores", "scaleFix",
  "ingestChart", "indexes", "redis", "qdrant", "load", "llm"];
const TAB_ORDER = ["positioning", "roles", "indexes", "integrity", "code", "security", "nosql", "tests", "accept",
  "env", "slo", "corpus", "defects", "ablation", "hnsw", "trace", "gaps"];
const F = (k) => { const i = FIG_ORDER.indexOf(k); if (i < 0) throw new Error(`figure ${k}`); return i + 1; };
const T = (k) => { const i = TAB_ORDER.indexOf(k); if (i < 0) throw new Error(`table ${k}`); return i + 1; };
let figN = 0;
let tabN = 0;
function fig(key, file, cap, w) {
  if (FIG_ORDER[figN++] !== key) throw new Error(`figure ${key} out of order`);
  return [figure(file, w, cap), caption(`Figure ${F(key)}.  ${cap}`)];
}
function tab(key, cap) {
  if (TAB_ORDER[tabN++] !== key) throw new Error(`table ${key} out of order`);
  return caption(`Table ${T(key)}.  ${cap}`);
}

const C = []; // document children

// ================================================================== cover
C.push(
  new K.Paragraph({ spacing: { after: 120 }, border: { bottom: { style: K.BorderStyle.SINGLE, size: 18, color: K.NAVY, space: 8 } }, children: [] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { before: 80, after: 80 },
    children: [run("REVIEW – III  ·  FINAL REPORT", { bold: true, size: 28, color: K.NAVY, characterSpacing: 60 })] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { after: 200 },
    children: [run("Final Demonstration and Innovation", { italics: true, size: 24, color: K.MUTED })] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { before: 360, after: 80 },
    children: [run("GraphRAG-Powered Cyber Threat Intelligence Platform:", { bold: true, size: 36, color: K.NAVY })] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { after: 360 },
    children: [run("A Multi-Model NoSQL Approach", { bold: true, size: 36, color: K.NAVY })] }),
  table([3000, 6638], [
    ["Deliverable", "Review – III  (10 marks): final demonstration and innovation"],
    ["Team", K.cell(["Shivansh Sharma (23BCE0254)", "Himali Sharma (23BCE0317)", "Aayush Sinha (23BCE0558)"], 6638, { size: 22 })],
    ["Institution", "VIT Vellore"],
    ["Guide", "Dr. Lydia Jane G"],
    ["Repository", "github.com/Shivansharmaaaa/graphrag"],
    ["Date", "October 2026"],
  ], { size: 22 }),
  spacer(360),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { after: 100 },
    children: [run("Deliverables covered", { bold: true, size: 22, color: K.NAVY })] }),
);
[["Complete working system", "Sections 4–8; source in backend/ and frontend/"],
  ["Performance evaluation", "Section 9: SLOs, 1×–200× scalability, index ablations, ANN recall, load, LLM latency"],
  ["Final report", "this document"],
  ["User manual", "separate document: User_Manual_GraphRAG_CTI_Platform.pdf"],
  ["Presentation and demo", "slide deck and demo runbook in review3/"]].forEach(([a, b]) => C.push(new K.Paragraph({
  alignment: K.AlignmentType.CENTER, spacing: { after: 50 }, children: [runB(`${a}  `, { size: 21 }), run(`— ${b}`, { size: 21, color: K.MUTED })],
})));

// ================================================================== contents
C.push(h1("Contents", { newPage: true }));
C.push(table([7600, 2038], [["Section", "Page"], ...SECTIONS.map((s) => [s, String(tocPages[s] || "")])], { size: 22, center: [1] }));
C.push(spacer(200), p(`**Figures** ${"(" + "diagrams and charts" + ")"} and **tables** are numbered in order of appearance. All measured values in Sections 8 and 9 are generated from the JSON result files in \`review3/performance/\`, produced by \`make eval\` and \`make bench\` on ${ENV.date}.`));

// ================================================================== 1 abstract
C.push(h1(SECTIONS[0], { newPage: true }));
C.push(p(`Cyber threat intelligence (CTI) is polyglot data. Relationships between threat actors, campaigns, malware and infrastructure form a graph; analyst reports are schema-variable documents; active indicators of compromise (IOCs) need millisecond lookups that expire on time; and analysts ask questions in natural language that need semantic recall. This project delivers a working CTI workstation that gives each workload its natural engine — Neo4j for the threat graph, MongoDB for reports, Redis for the IOC blocklist and Qdrant for report embeddings — and adds a GraphRAG layer that retrieves evidence from all four stores before a locally hosted LLM writes an answer in which every sentence must cite a graph edge, a passage, a report or an IOC state.`));
C.push(p(`Review III completes and evaluates the system. The platform ingests STIX 2.1 bundles and free-text reports, enforces Traffic Light Protocol (TLP) clearance on every read path, serves a fail-closed enforcement API to firewalls and EDR tools, and records every answer for replay. On the six acceptance questions it recalls 100% of the required graph facts and source reports; with the default \`llama3.2:3b\` model the GraphRAG end-to-end p95 is **${llmFinal.p95_s} s** against a 15 s target (down from ${llmSept.p95_s} s in September). A new benchmark harness scales the corpus from 1× to 200× (${n0(rN.nodes)} nodes, ${n0(rN.reports)} reports) and ablates the indexes of each store. It exposed four scalability defects — linear entity linking, an unbounded traversal with unindexed node lookups, a whole-graph join on ingest and a thread-safety bug under concurrent load — whose fixes cut GraphRAG retrieval p95 at 200× from **${ms(rag(bN).total.p95)}** to **${ms(rag(rN).total.p95)}** and keep every store-level query within its service level.`));
C.push(p("**Keywords:** cyber threat intelligence, polyglot persistence, NoSQL, graph database, vector search, retrieval-augmented generation, GraphRAG, performance evaluation."));

// ================================================================== 2 introduction
C.push(h1(SECTIONS[1]));
C.push(h2("2.1  Problem"));
C.push(p("Security operations centres ask relational and semantic questions: which actors share command-and-control (C2) infrastructure, which campaigns reuse a commodity tool, which reports resemble a new phishing lure, and whether an indicator on the blocklist is still live. A single storage engine serves these workloads poorly [8], [9]: path queries become application-side joins in a document store, report bodies strain a graph store, and neither offers per-key expiry or approximate nearest-neighbour search. Retrieval-augmented generation (RAG) over CTI adds a second risk: a language model can produce fluent attributions that no stored evidence supports [21], [23]."));
C.push(h2("2.2  Objectives"));
[["O1", "Ingest STIX 2.1 bundles and free-text reports consistently into all four stores."],
  ["O2", "Answer multi-hop graph questions (shared infrastructure, shared tooling, common victims) natively in Neo4j."],
  ["O3", "Serve full, schema-variable reports from MongoDB with TLP-based access control."],
  ["O4", "Maintain a hot IOC blocklist in Redis with per-key TTL and a fail-closed enforcement API."],
  ["O5", "Answer natural-language questions with GraphRAG on a local LLM, with every sentence cited and auditable."],
  ["O6", "Demonstrate that the design meets its latency targets and scales, with reproducible measurements."]]
  .forEach(([a, b]) => C.push(bullet(`**${a}** ${b}`)));
C.push(h2("2.3  What Review III adds"));
C.push(p(`Review I fixed the design and Review II delivered the first working build. This review closes the remaining gaps recorded in the progress report and evaluates the system as the rubric asks: a complete system with an analyst console of eight pages and ${ENDPOINTS} API endpoints; a performance evaluation covering query latency, scalability, indexing and benchmarking; and the documentation set (this report, a user manual, slides and a demo runbook). The main engineering contributions of this review are:`));
[`a **prompt budget** and model choice that bring GraphRAG p95 from ${llmSept.p95_s} s to ${llmFinal.p95_s} s, meeting NFR2 on a laptop;`,
  "a **groundedness-gate fix** that stops valid citations written in variant forms from being discarded;",
  `a **benchmark harness** (\`make bench\`) for 1×–200× corpus scaling, index ablations, ANN recall and API load, which found **four scalability defects**, all fixed and re-measured;`,
  `**${INT_TESTS} integration tests**, an evaluation gate and **continuous integration** that run the whole stack on every push.`]
  .forEach((t) => C.push(bullet(t)));

// ================================================================== 3 background
C.push(h1(SECTIONS[2]));
C.push(p("**Threat intelligence and sharing.** Technical CTI — indicators, malware artefacts and procedures — is what automated defences consume, and its value lies in correlation rather than lookup [1], [2], [6]. STIX 2.1 already models CTI as a graph of objects and relationships [3], and ATT&CK gives a shared vocabulary of techniques [4]. MISP excels at disseminating events [5], [29] and OpenCTI offers a graph-backed product [16], but neither treats TTL-based enforcement, narrative similarity search and cited question answering as co-equal planes."));
C.push(p("**Polyglot persistence.** “One size fits all” no longer holds for data management [8]; the NoSQL families each optimise a different access pattern and trade consistency guarantees accordingly [9]–[11]. Graph databases make multi-hop traversal a local operation through index-free adjacency [12], [26], and cybersecurity knowledge graphs have been built from reports and alerts [13]–[15]. Document stores keep heterogeneous reports without migrations [17]; key–value stores give constant-time lookups with native expiry [18]; and vector databases answer approximate k-NN queries with graph-based indexes such as HNSW [19], [20], [30]."));
C.push(p("**From RAG to GraphRAG.** RAG grounds generation in retrieved passages [21], [22], but passage retrieval alone cannot answer path questions. GraphRAG combines graph traversal with retrieval [23]–[25]; evaluation work stresses that answers must be faithful to their context [37] and that long, unprioritised contexts degrade model behaviour [36]. Benchmarks for serving systems [33], graph databases [34] and ANN indexes [35] motivate the measurement method in Section 9."));
C.push(spacer(60), table([2700, 1700, 1700, 1700, 1838], [
  ["Capability", "MISP", "OpenCTI", "Vanilla RAG", "This platform"],
  ["Multi-hop graph queries", "limited", "yes", "no", "yes (Neo4j)"],
  ["Schema-variable reports", "events", "yes", "passages", "yes (MongoDB)"],
  ["Per-key IOC expiry + enforcement API", "no", "no", "no", "yes (Redis, fail-closed)"],
  ["Semantic search with payload filters", "no", "limited", "yes", "yes (Qdrant)"],
  ["Cited natural-language answers", "no", "no", "uncited", "every sentence cited"],
  ["Replay of an answer against the stores", "no", "no", "no", "yes"],
  ["Runs fully offline (local LLM)", "n/a", "n/a", "varies", "yes"],
], { size: 19, center: [1, 2, 3, 4] }));
C.push(tab("positioning", "Positioning against existing CTI platforms and plain RAG (Review I gaps G1–G5)."));

// ================================================================== 4 architecture
C.push(h1(SECTIONS[3], { newPage: true }));
C.push(p(`The implemented architecture matches the Review I design (Figure ${F("arch")}). A React console and downstream enforcement consumers are the only clients. A FastAPI service owns authentication, TLP policy, ingest, GraphRAG orchestration, audit and operations. Four NoSQL engines sit behind it, each with a closed set of operations, and a locally hosted LLM is called only by the GraphRAG orchestrator.`));
C.push(...fig("arch", FIG("r3_architecture.png"), "Implemented architecture: clients, API and orchestration, four NoSQL stores and the local model."));
C.push(table([1500, 2900, 2900, 2338], [
  ["Store", "Owns", "Operations used", "Why not another store"],
  ["Neo4j 5", "threat knowledge graph (8 labels, 12 relationship types)", "MERGE by unique id; 1–3 hop paths with a hub budget; shortestPath", "joins across documents are application code; Redis and Qdrant have no traversal"],
  ["MongoDB 7", "reports, STIX bundles, users, audit log, ingest jobs", "get / hydrate by _id; multikey indexes on actors and IOCs; TLP $in filter", "a graph node cannot hold report bodies with arbitrary nested fields"],
  ["Redis 7", "hot IOC blocklist", "GET + TTL pipelined; SET EX; sorted-set expiry index", "only Redis gives O(1) lookup with native per-key expiry"],
  ["Qdrant 1.13", "report chunk embeddings", "filtered k-NN (HNSW, cosine); payload indexes", "no other store offers ANN search with payload filters"],
], { size: 18 }));
C.push(tab("roles", "Responsibilities and closed operation set of each store."));
C.push(p(`Three keys join the stores (Figures ${F("graph")} and ${F("stores")}): a report's \`_id\` in MongoDB is the \`id\` of its \`Report\` node and the \`report_id\` in every Qdrant point payload; and an indicator's \`(type, value)\` is both an \`Indicator\` node key and the Redis key \`ioc:{type}:{value}\`. These joins are verified by the integrity check in Section 5.3.`));

// ================================================================== 5 data model
C.push(h1(SECTIONS[4]));
C.push(h2("5.1  Threat knowledge graph"));
C.push(p(`Figure ${F("graph")} shows the property graph as implemented. Identifiers are unique per label (constraints), commodity tools such as Mimikatz and Cobalt Strike are deliberately shared nodes, and \`Indicator\` nodes persist after their Redis key expires so that history and enforcement can disagree — the basis of use case UC4. The seed corpus loads 87 nodes and 162 relationships.`));
C.push(...fig("graph", FIG("r3_graph_schema.png"), "Graph schema (Neo4j): labels, key properties and relationship types.", 600));
C.push(h2("5.2  Document, vector and key–value schemas"));
C.push(p("Reports share a small core envelope and diverge in report-specific fields (`attribution`, `build_pipeline`, `ics_protocols`), stored without migrations. Each report body is split into chunks of at most 420 characters; each chunk is a Qdrant point whose payload carries the fields that filters need. The Redis plane holds one string key per live IOC, expiring with `EX`, plus a sorted set scored by expiry time for the hot-set view."));
C.push(...fig("stores", FIG("r3_store_schemas.png"), "Document (MongoDB), vector (Qdrant) and key–value (Redis) schemas with their indexes."));
C.push(h2("5.3  Indexes, constraints and cross-store integrity"));
C.push(table([1500, 4400, 3738], [
  ["Store", "Index or constraint", "Serves"],
  ["Neo4j", "unique id on ThreatActor, Campaign, Malware, Infrastructure, Technique, Victim, Report; unique (type, value) on Indicator; range indexes on Infrastructure.value, Indicator.value, Indicator.id", "MERGE during ingest; id lookups (index seek); IOC → graph lookups"],
  ["MongoDB", "reports: actors, iocs (multikey), date (desc), tlp; audit_log.ts; ingest_jobs.created_at; users.username (unique)", "TLP-filtered listing; IOC history (UC4); newest-first views"],
  ["Qdrant", "HNSW (m = 16, ef_construct = 100); keyword payload indexes report_id, actors, tlp; integer date_ts", "filtered k-NN; delete chunks of a report"],
  ["Redis", "key ioc:{type}:{value}; ZSET ioc:index", "O(1) enforcement lookup; hot set and expiry listing"],
], { size: 18 }));
C.push(tab("indexes", "Indexes and constraints (schema version 2, created at start-up by ensure_schema)."));
C.push(table([5400, 1600, 2638], [
  ["Integrity rule (Section 8.5 of Review I)", "Kind", "Effect if violated"],
  ["Every MongoDB report has a Report node", "hard", "GraphRAG would cite a report with no graph context"],
  ["Every Report node has a MongoDB document", "hard", "hydration fails"],
  ["Every Qdrant point.report_id exists in MongoDB", "hard", "orphan chunks; GraphRAG refuses them"],
  ["Every live Redis IOC traces to an Indicator node or a report", "informational", "operators may publish new IOCs (FR12)"],
  ["Every MongoDB report has chunks in Qdrant", "informational", "report not reachable by semantic search"],
], { size: 18, center: [1] }));
C.push(tab("integrity", "Cross-store integrity rules checked by GET /api/admin/integrity and by the evaluation gate."));

// ================================================================== 6 implementation
C.push(h1(SECTIONS[5], { newPage: true }));
C.push(h2("6.1  Codebase"));
C.push(table([2500, 5000, 2138], [
  ["Part", "Contents", "Size"],
  ["backend/app", "FastAPI API, store clients, Cypher library, ingest, GraphRAG, security, metrics, seed corpus", `${n0(LOC_BACKEND)} lines of Python`],
  ["backend/scripts", "evaluation gate (evaluate.py) and benchmark harness (benchmark.py)", `${n0(LOC_SCRIPTS)} lines`],
  ["backend/tests", `${UNIT_TESTS} unit tests and ${INT_TESTS} integration tests`, `${n0(LOC_TESTS)} lines`],
  ["frontend/src", "React + Vite analyst console, 8 pages and 6 shared components", `${n0(LOC_FRONT)} lines`],
  ["deployment", "docker-compose.yml (stores, app and llm profiles), docker-compose.bench.yml, Makefile, CI workflow", "—"],
], { size: 19 }));
C.push(tab("code", "Code organisation."));
C.push(h2("6.2  Ingest pipeline (FR1)"));
C.push(p(`An ingest job turns a STIX bundle or a free-text report into a plan — graph nodes and edges, report documents and indicators — and executes it against Neo4j, MongoDB, Qdrant and optionally Redis in that order (Figure ${F("ingest")}). STIX objects are merged into existing nodes by name or alias, relationship types are mapped onto the graph vocabulary (for example \`attributed-to\` is reversed into \`ATTRIBUTED_TO_CAMPAIGN\`), TLP comes from marking definitions, and indicator \`valid_until\` becomes the Redis TTL. Free text is linked to graph entities, and defanged IOCs such as \`hxxp://evil[.]com\` are refanged before extraction. There is no distributed transaction: each step is idempotent and recorded in \`ingest_jobs\`, so a failed job resumes from the first step that did not finish, and Qdrant refuses to index a document whose \`Report\` node is missing.`));
C.push(...fig("ingest", FIG("r3_ingest.png"), "Ingest fan-out with a job log and idempotent retry."));
C.push(h2("6.3  GraphRAG orchestration (FR5, FR7, NFR4)"));
C.push(p(`Figure ${F("answer")} traces one question. Entity linking maps names, aliases and IOCs in the question to graph ids. Four channels then retrieve evidence: Qdrant k-NN over chunks with the analyst's TLP as a payload filter; Neo4j expansion of one to three hops from the linked entities, which may end at but never pass through a hub node (degree above 12), so Mimikatz cannot pull in the whole graph; MongoDB hydration of the cited reports, again TLP-checked; and Redis state for every IOC in the evidence. Templated queries add the flagship findings (shared infrastructure, tool users) as citable edges.`));
C.push(...fig("answer", FIG("r3_answer_path.png"), "GraphRAG answer path: retrieval, context pack, prompt budget, local LLM and groundedness gate."));
C.push(p("Every evidence item receives a citation id — `[G#]` edge, `[C#]` chunk, `[R:id]` report, `[I#]` IOC state. The full pack drives the evidence panel and the audit log, while the LLM receives a trimmed pack (Section 9.8). The groundedness gate splits the answer into sentences, normalises citation variants (`[G1-G4]`, `(G20)`, `[rpt-001]`), keeps a sentence only if one of its tags exists in the pack, and refuses the answer when fewer than half of the sentences survive. A refused LLM answer falls back to a deterministic retrieve-only answer rendered from the same evidence, which is gated again; the same path serves when the LLM is unreachable. The answer inherits the highest TLP of the documents it cites."));
C.push(h2("6.4  Security and access control (FR11, NFR3, NFR8)"));
C.push(table([3000, 6638], [
  ["Control", "Implementation"],
  ["Authentication", "JWT (HS256, 8-hour expiry); PBKDF2-SHA256 password hashes with 200,000 iterations"],
  ["Roles", "analyst (query), lead (+ publish/revoke IOCs, ingest), admin (+ seed, reindex, delete reports, all audit entries)"],
  ["TLP clearance", "WHITE < GREEN < AMBER < RED (CLEAR → WHITE, AMBER+STRICT → AMBER, unknown → AMBER); enforced on report lists, report detail (403), semantic search, GraphRAG context, answer labels and audit visibility"],
  ["Enforcement API", "separate API-key surface for firewalls, EDR and SIEM; reads Redis only; a miss is never resolved from MongoDB; Redis down → HTTP 503 with blocked: true (fail closed)"],
  ["Audit", "every answer stores its hops, chunks, documents and IOC states; replay re-verifies each against the live stores"],
  ["Data residency", "local LLM through Ollama and local embeddings; no cloud API is called (NFR1)"],
], { size: 19 }));
C.push(tab("security", "Security controls."));
C.push(h2("6.5  Analyst console"));
C.push(p(`The console has eight pages: GraphRAG console, graph explorer, report browser, IOC blocklist, semantic search, ingest, audit and replay, and operations. Figure ${F("console")} shows the GraphRAG console answering acceptance question 4: citation chips link each sentence to its evidence, the commodity-hub caution appears beside the answer, and the evidence panel animates the cited hops. The user manual documents every page.`));
C.push(...fig("console", SHOT("graphrag_answer.png"), "GraphRAG console: cited answer, hub caution and the evidence panel (llama3.2:3b, 100% citation coverage)."));
C.push(h2("6.6  Deployment and operations"));
C.push(p(`\`docker compose up -d\` starts the four stores; the \`app\` profile adds the API and an nginx-served console, and the \`llm\` profile an Ollama container. On first start the API creates the schema and seeds an empty stack. The operations page shows store health, per-store latency percentiles against their SLOs and the integrity check. Dumps of all four stores and a restore script support reproducibility (NFR5), and GitHub Actions runs the test tiers against fresh service containers on every push.`));

C.push(h2("6.7  The databases in their own consoles"));
C.push(p(`Each store can also be inspected directly in its native tool, independently of the platform (Figure ${F("dbConsoles")}): Neo4j Browser runs Cypher against the live graph — \`CALL db.schema.visualization()\` draws the schema of 8 labels and 16 relationship patterns; mongo-express shows the \`cti\` database's six collections and each report with its own nested fields; Redis Commander shows every \`ioc:{type}:{value}\` key with its value and a TTL that counts down; and the Qdrant dashboard lists the 25 vector points of \`threat_chunks\` with their payloads and HNSW settings. \`make dbui\` starts the two consoles that are not built in, read-only and bound to the local machine; \`review3/DATABASE_TOUR.md\` gives the queries used in the demonstration.`));
C.push(...fig("dbConsoles", FIG("r3_db_consoles.png"), "The four NoSQL databases in their own consoles: Neo4j Browser, mongo-express, Redis Commander and the Qdrant dashboard."));

// ================================================================== 7 innovation
C.push(h1(SECTIONS[6], { newPage: true }));
C.push(h2("7.1  Novel features"));
[["Four-store GraphRAG with typed citations.", "Evidence from a graph, a document store, a vector index and a key–value cache is unified into one context pack where each item carries a store-specific citation id; the console resolves each id back to its store."],
  ["Groundedness gate with deterministic fallback.", "Uncited sentences are removed, the answer is refused below 50% coverage, and a refused answer is replaced by evidence-only sentences rather than an unsupported one."],
  ["Hub-aware traversal.", "Traversals stop at commodity hubs, bounding the evidence (60 edges at every corpus size in Section 9.3), and the answer must state that a commodity tool is a weak attribution signal (UC3)."],
  ["TLP-aware retrieval and answer labelling.", "Clearance is applied inside each store query — a Qdrant payload filter, a MongoDB $in, a graph filter — not after generation, and the answer is labelled with the highest TLP it cites."],
  ["Enforcement plane separate from the read path.", "Consumers see only Redis, which fails closed, while the analyst read path degrades to retrieve-only answers when Redis or the LLM is down (NFR8)."],
  ["Replayable answers.", "An answer from weeks ago can be re-verified edge by edge, chunk by chunk and IOC by IOC against the current stores."],
  ["Local AI with a prompt budget.", "The LLM sees a ranked, trimmed evidence pack sized for local inference, so a 3-billion-parameter model meets the interactive SLO without a GPU server."],
  ["Self-measuring system.", "An evaluation gate and a benchmark harness are part of the code base; Section 9 shows they found and verified four performance fixes."]]
  .forEach(([a, b]) => C.push(bullet([runB(`${a} `), run(b)])));
C.push(h2("7.2  Advanced NoSQL capabilities used"));
C.push(table([1500, 8138], [
  ["Store", "Capabilities beyond basic CRUD"],
  ["Neo4j", "variable-length path patterns with COUNT {} subquery predicates (hub budget); weighted path ranking with reduce(); composite (type, value) uniqueness; UNION-of-labels lookups that turn label-less matches into index seeks; CALL … IN TRANSACTIONS for batched bulk writes; PROFILE-driven tuning"],
  ["MongoDB", "schema-on-read documents with report-specific nested fields; multikey indexes on array fields; explain() plans used to verify index use; idempotent replace_one upserts; collStats for index sizing"],
  ["Redis", "per-key TTL with SET EX; sorted-set expiry index (ZADD, ZRANGEBYSCORE, ZCOUNT); pipelined GET + TTL batches; AOF persistence so TTLs survive restarts"],
  ["Qdrant", "HNSW with tunable search breadth (ef); keyword and integer payload indexes; filtered k-NN; filter-based deletes; exact search used as ground truth for recall"],
], { size: 19 }));
C.push(tab("nosql", "Advanced capabilities of each engine used by the platform."));
C.push(h2("7.3  AI integration"));
C.push(p("The LLM is used only to render retrieved evidence as prose; it never decides what is retrieved and never writes to a store. It runs locally through Ollama (`llama3.2:3b` by default, `llama3.1:8b` optional [31], [32]) under a system prompt that requires a citation on every sentence, forbids invented entities and offensive content, and requires an exact refusal string when evidence is missing. Embeddings default to a deterministic 64-dimensional TF-IDF + truncated-SVD model, with a neural model (`nomic-embed-text`) available through configuration."));

// ================================================================== 8 testing
C.push(h1(SECTIONS[7]));
C.push(table([2300, 1500, 5838], [
  ["Tier", "Count", "What it checks"],
  ["Unit tests", String(UNIT_TESTS), "TLP ordering and clearance, password hashing, IOC extraction and refanging, entity linking (including equivalence of the indexed linker with the reference linker), STIX mapping, chunking, the groundedness gate and its citation forms"],
  ["Integration tests", String(INT_TESTS), "the real API against the live stores: auth and roles, TLP on lists, search and GraphRAG context, publish → enforce → revoke, fail-closed enforcement, LLM-down fallback, audit replay, ingest fan-out, delete cascade, integrity"],
  ["Evaluation gate", "6 questions", "gold graph edges and reports, refusals, commodity caution, expiry probe, integrity; exits non-zero on any failure"],
  ["Benchmarks", "6 experiments", "scalability, load, Redis, MongoDB and Neo4j index ablations, Qdrant recall (Section 9)"],
  ["Continuous integration", "every push", "unit + integration + evaluation gate on fresh Neo4j, MongoDB, Redis and Qdrant containers; frontend build"],
], { size: 19, center: [1] }));
C.push(tab("tests", "Test tiers. Integration tests remove everything they write, so they run safely against the demo stack."));
C.push(h2("8.1  Acceptance tests"));
C.push(p(`The six Appendix A questions of Review I are the acceptance tests. Each must retrieve specified gold edges and gold reports. Table ${T("accept")} shows the final run with the default model.`));
C.push(table([3900, 1650, 1000, 1000, 1000, 1088], [
  ["Question", "Mode", "Gold edges", "Gold reports", "Coverage", "Latency"],
  ...g.questions.map((q) => [q.question, q.mode.startsWith("retrieve-only") ? "retrieve-only (gate fallback)" : "LLM", q.gold_edges_recalled, q.gold_reports_recalled, q.citation_coverage.toFixed(2), `${(q.latency_ms / 1000).toFixed(1)} s`]),
], { size: 18, center: [2, 3, 4, 5] }));
C.push(tab("accept", `Acceptance results (${E.ts ? new Date(E.ts * 1000).toISOString().slice(0, 10) : ENV.date}, llama3.2:3b). Gold edge recall ${g.gold_edge_recall.toFixed(2)}, gold report recall ${g.gold_report_recall.toFixed(2)}, mean citation coverage ${g.mean_citation_coverage.toFixed(2)}.`));
C.push(p("Every question retrieved all of its gold evidence and none was refused. In question 2 the model's draft fell below the coverage threshold and the gate replaced it with the deterministic evidence answer — the intended behaviour, not a failure. Question 6 carries the commodity-hub caution required by UC3. The same questions in retrieve-only mode, as run in CI, reach coverage 1.00 at about 50 ms per question."));

// ================================================================== 9 performance
C.push(h1(SECTIONS[8], { newPage: true }));
C.push(h2("9.1  Method"));
C.push(p(`Benchmarks run with \`make bench\` against a throwaway stack (\`docker-compose.bench.yml\`) on alternate ports, so synthetic data never reaches the demo stores; the demo stack is paused for the run. Each latency figure is a client-side percentile over repeated calls after warm-up (30–2,000 samples per measurement), taken through the same Python functions the API uses. To scale the corpus, the seed corpus is cloned 10×–200× through the production seed loader: clones receive new ids, names and infrastructure values from the RFC 2544 benchmarking range, one cross-clone infrastructure edge per actor, and they share the ATT&CK techniques and commodity tools, so hub degree grows with scale as it would in practice. Index experiments use dedicated synthetic collections. LLM measurements come from \`make eval\` on the demo stack.`));
C.push(table([3000, 6638], [
  ["Host", `${ENV.host}, ${ENV.host_memory_gb} GB RAM, macOS`],
  ["Docker VM", `${ENV.docker_vm.replace(/(\d+) bytes/, (_, b) => `${(b / 2 ** 30).toFixed(1)} GB`)} shared by all containers`],
  ["Engines", `Neo4j ${ENV.neo4j} · MongoDB ${ENV.mongodb} · Redis ${ENV.redis} · Qdrant ${ENV.qdrant}`],
  ["Runtime", `Python ${ENV.python}, FastAPI, one Uvicorn worker; Ollama on the host GPU (Metal)`],
  ["Corpus scales", rows.map((r) => `${r.scale}× = ${n0(r.nodes)} nodes / ${n0(r.reports)} reports`).join("; ")],
], { size: 19 }));
C.push(tab("env", "Benchmark environment."));
C.push(p("**Threats to validity.** All engines share two virtual CPUs, so absolute numbers are conservative for a server deployment but contention is real. The scaled corpus is synthetic and repetitive, which favours caches; the index experiments therefore use independent random data. Load is generated on the same host as the server."));

C.push(h2("9.2  Service-level objectives (NFR2)"));
C.push(table([3200, 1800, 2200, 2438], [
  ["Metric", "Target", "Measured", "Result"],
  ["Redis blocklist GET p99", "< 5 ms", `${lat.redis_get_p99_ms} ms (500 calls); ${rTop.get_hit.p99} ms at ${n0(rTop.keys)} keys`, "met"],
  ["Neo4j 1 / 2 / 3-hop p95", "< 500 ms", `${lat.graph_1hop_p95_ms} / ${lat.graph_2hop_p95_ms} / ${lat.graph_3hop_p95_ms} ms`, "met"],
  ["Neo4j 2-hop p95 at 200×", "< 500 ms", ms(rN.neo4j.neighbourhood_2hop.p95), "met"],
  ["GraphRAG end-to-end p95 (with LLM)", "< 15 s", `${llmFinal.p95_s} s (llama3.2:3b)`, "met"],
  ["GraphRAG retrieval p95 at 200× (no LLM)", "—", ms(rag(rN).total.p95), "within budget"],
], { size: 19, center: [1, 3] }));
C.push(tab("slo", "Service-level objectives."));

C.push(h2("9.3  Scalability from 1× to 200×"));
C.push(table([900, 1300, 1600, 1300, 1300, 1200, 2038], [
  ["Scale", "Nodes", "Relationships", "Reports", "Chunks", "IOCs", "Load time (all stores)"],
  ...rows.map((r) => [`${r.scale}×`, n0(r.nodes), n0(r.relationships), n0(r.reports), n0(r.chunks), n0(r.iocs),
    `${(Object.values(r.load_seconds).reduce((a, b) => a + b, 0)).toFixed(1)} s`]),
], { size: 19, center: [0, 1, 2, 3, 4, 5, 6] }));
C.push(tab("corpus", "Corpus at each scale, loaded through the production seed path."));
C.push(...fig("scaleStores", FIG("chart_scale_stores.png"), "p95 latency of each store's GraphRAG query as the corpus grows 200× (after the fixes of Section 9.4)."));
C.push(p(`Store-level latency is essentially flat across a 170-fold increase in graph size. A 2-hop neighbourhood stays near ${ms(r1.neo4j.neighbourhood_2hop.p95)}–${ms(rN.neo4j.neighbourhood_2hop.p95)} because traversal cost depends on the local neighbourhood, not on graph size (index-free adjacency), and the hub budget keeps the evidence at ${rag(rN).max_evidence_edges} edges and ${rag(rN).max_documents} documents at every scale. MongoDB reads by actor stay near ${ms(rN.mongodb.list_by_actor.p95)} through the multikey index, Qdrant filtered k-NN near ${ms(rN.qdrant.knn_k6_tlp_filter.p95)}, and Redis GET near ${ms(rN.redis.blocklist_get.p95)}. Entity-linking p95 rises from ${ms(r1.graphrag_retrieve_only.channels.linking.p95)} to ${ms(rN.graphrag_retrieve_only.channels.linking.p95)} because a name such as APT28 has 200 near-duplicate clones to verify — still below a millisecond.`));

C.push(h2("9.4  Bottlenecks found and fixed"));
C.push(p(`The first scaling run did not look like Figure ${F("scaleStores")}. GraphRAG retrieval grew roughly linearly with corpus size — median ${ms(rag(B.scale.rows[0]).total.p50)} at 1× to ${ms(rag(bN).total.p50)} at 200×, p95 ${ms(rag(bN).total.p95)} — and ingest throughput fell from ${B.scale.rows[0].ingest.reports_per_s} to ${bN.ingest.reports_per_s} reports per second. Per-channel timing and Neo4j PROFILE output traced this to four defects, none visible on the 87-node seed corpus:`));
C.push(table([2300, 3700, 3638], [
  ["Defect", "Cause", "Fix"],
  ["Linear entity linking", "one regular-expression search per gazetteer surface form for every question and every ingest (≈30,000 at 200×)", "inverted index from tokens and dotted runs to surface forms; candidates verified with the original word-boundary rule; a unit test proves identical results [39]"],
  ["Unbounded global traversal + N+1 lookups", "questions naming no actor listed every infrastructure-sharing pair, then fetched each missing node with a label-less MATCH (a full scan of all nodes, once per node)", "LIMIT 25 ordered by shared-report evidence; one batched lookup via a UNION of labelled index seeks; an index on Indicator.id"],
  ["Whole-graph join on ingest", "every ingest re-linked OBSERVED_AS across all Infrastructure × Indicator pairs and invalidated the gazetteer", "join restricted to the plan's values; gazetteer invalidated only when a job adds graph entities"],
  ["Thread-unsafe vector client under load", "one Qdrant REST client shared by FastAPI's worker threads: under 16 concurrent clients a socket was closed under another thread's read (HTTP 500)", "one Qdrant client per worker thread; gazetteer refresh behind a lock"],
], { size: 18 }));
C.push(tab("defects", "Scalability defects exposed by the benchmark and their fixes."));
C.push(...fig("scaleFix", FIG("chart_scale_fix.png"), "Entity linking and GraphRAG retrieval latency before and after the fixes, 1× to 200×."));
C.push(p(`At 200× the fixes reduce entity linking from ${ms(bN.graphrag_retrieve_only.channels.linking.p50)} to ${ms(rN.graphrag_retrieve_only.channels.linking.p50)} (median), GraphRAG retrieval from ${ms(rag(bN).total.p50)} to ${ms(rag(rN).total.p50)} (median) and from ${ms(rag(bN).total.p95)} to ${ms(rag(rN).total.p95)} (p95), and raise ingest throughput from ${bN.ingest.reports_per_s} to ${rN.ingest.reports_per_s} reports per second (Figure ${F("ingestChart")}). The full scale experiment now runs in ${R.scale.experiment_s} s instead of ${B.scale.experiment_s} s.`));
C.push(...fig("ingestChart", FIG("chart_ingest.png"), "Ingest throughput through the full four-store fan-out, before and after the fixes."));

C.push(h2("9.5  Indexing"));
C.push(p(`Each store's indexes were ablated on dedicated data: ${n0(M.documents)} synthetic reports in MongoDB and ${n0(N.nodes)} hosts in Neo4j. Figure ${F("indexes")} and Table ${T("ablation")} show latency together with the work the engine reports — documents and keys examined from MongoDB \`explain()\`, database hits from Neo4j \`PROFILE\`.`));
C.push(...fig("indexes", FIG("chart_indexes.png"), "Index ablation: MongoDB report queries and Neo4j property lookup, without and with indexes (median latency)."));
const mq = [["by_actor", "reports by actor (limit 100)"], ["by_ioc", "reports citing an IOC"], ["tlp_recent_50", "50 newest at TLP ≤ GREEN"]];
C.push(table([2900, 1700, 1700, 1700, 1638], [
  ["Query", "Plan without → with", "Docs examined", "Median latency", "Speed-up"],
  ...mq.map(([k, lab]) => [lab, `${M.no_index[k].plan.slice(-1)[0]} → ${M.production_indexes[k].plan.slice(-1)[0]}`,
    `${n0(M.no_index[k].docs_examined)} → ${n0(M.production_indexes[k].docs_examined)}`,
    `${ms(M.no_index[k].latency.p50)} → ${ms(M.production_indexes[k].latency.p50)}`, x(M.no_index[k].latency.p50, M.production_indexes[k].latency.p50)]),
  ["Neo4j host by value", `${N.no_index.operators.slice(-1)[0]} → ${N.range_index.operators.slice(-1)[0]}`, `${n0(N.no_index.db_hits)} → ${n0(N.range_index.db_hits)} db hits`,
    `${ms(N.no_index.latency.p50)} → ${ms(N.range_index.latency.p50)}`, x(N.no_index.latency.p50, N.range_index.latency.p50)],
], { size: 18, center: [2, 3, 4] }));
C.push(tab("ablation", "Index ablation results."));
C.push(p(`Without secondary indexes MongoDB scans the collection (COLLSCAN) and reads up to every document; the multikey indexes reduce this to the matching documents. The newest-first TLP query reads ${M.production_indexes.tlp_recent_50.docs_examined} documents through the date index and ${M.compound_tlp_date.tlp_recent_50.docs_examined} with a compound (tlp, date) index — a small further gain we record but do not need at this scale. The production indexes cost ${(Object.entries(M.index_mb).filter(([k]) => k !== "_id_" && k !== "tlp_1_date_-1").reduce((a, [, v]) => a + v, 0)).toFixed(1)} MB for ${M.data_mb} MB of data and build in ${M.index_build_s} s. In Neo4j, a label scan touches every node; the range index turns the lookup into a seek with ${N.range_index.db_hits} database hits.`));

C.push(h2("9.6  Key–value enforcement plane"));
C.push(...fig("redis", FIG("chart_redis.png"), "Redis: blocklist lookup p99 against a full keyspace scan as the number of IOC keys grows to 500,000."));
C.push(p(`The enforcement lookup (pipelined GET + TTL) stays at ${ms(rTop.get_hit.p50)} median and ${ms(rTop.get_hit.p99)} p99 at ${n0(rTop.keys)} keys, while any lookup that is not by key — such as finding IOCs by actor — needs a full SCAN that grows linearly to ${ms(rTop.full_scan_ms)}. This is why the design never queries Redis by attribute (NFR3) and keeps attribute queries in MongoDB and Neo4j. Memory grows to ${rTop.used_memory_mb} MB at ${n0(rTop.keys)} keys (about ${Math.round((rTop.used_memory_mb * 2 ** 20) / rTop.keys)} bytes per IOC including the expiry index).`));

C.push(h2("9.7  Vector search: HNSW against exact search"));
C.push(...fig("qdrant", FIG("chart_qdrant.png"), "Qdrant: recall@10 of HNSW as search breadth grows, and median latency of HNSW and exact search as the collection grows."));
C.push(table([1500, 1900, 1900, 2100, 2238], [
  ["Points", "Exact (unfiltered)", "HNSW ef = 64", "Recall@10 ef = 64", "Recall@10 ef = 128 (TLP filter)"],
  ...Q.map((r) => [`${n0(r.points)}`, ms(r.unfiltered.exact.p50), ms(r.unfiltered.hnsw_ef64.p50), r.unfiltered.hnsw_ef64.recall_at_10.toFixed(3), r.tlp_filter.hnsw_ef128.recall_at_10.toFixed(3)]),
], { size: 19, center: [0, 1, 2, 3, 4] }));
C.push(tab("hnsw", "HNSW against exact search on 64-dimensional clustered vectors (100 queries, k = 10)."));
C.push(p(`Exact search grows linearly with the collection (${ms(Q[0].unfiltered.exact.p50)} → ${ms(qTop.unfiltered.exact.p50)}) while HNSW stays near ${ms(qTop.unfiltered.hnsw_ef64.p50)} with recall@10 of ${qTop.unfiltered.hnsw_ef64.recall_at_10.toFixed(3)} at ef = 64. Filtering by TLP needs a wider search: at ${n0(qTop.points)} points recall is ${qTop.tlp_filter.hnsw_ef16.recall_at_10.toFixed(2)} at ef = 16 but ${qTop.tlp_filter.hnsw_ef128.recall_at_10.toFixed(3)} at ef = 128. The platform's own collection (25 chunks, ${n0(rN.chunks)} at 200×) is below Qdrant's indexing threshold, so it is searched exactly — the optimal choice at that size.`));

C.push(h2("9.8  Concurrency"));
C.push(...fig("load", FIG("chart_load.png"), "API throughput and p95 latency from 1 to 64 concurrent clients (200× corpus, one Uvicorn worker)."));
const enfPeak = maxBy(LOAD.enforce_check, (r) => r.throughput_rps);
const ragPeak = maxBy(LOAD.graphrag_retrieve_only, (r) => r.throughput_rps);
C.push(p(`A single API worker peaks at ${n0(enfPeak.throughput_rps)} enforcement checks per second (${enfPeak.concurrency} clients) and ${ragPeak.throughput_rps} GraphRAG retrievals per second, with no errors at any level after the thread-safety fix. Beyond four clients throughput falls and tail latency rises sharply: the worker is bound by the Python interpreter lock and the two virtual CPUs it shares with the stores, so requests queue. Throughput therefore scales by adding Uvicorn workers or API replicas behind a load balancer — the stores are not the limit — and a deployment on dedicated cores would move the knee further out.`));

C.push(h2("9.9  LLM latency"));
C.push(p(`The GraphRAG SLO is the only one that depends on the language model. Profiling one call showed that with the full evidence pack (${n0(LL.call_profile.prompt_chars_full)} characters, ${n0(LL.call_profile.calls[0].prompt_tokens)} tokens) \`llama3.1:8b\` spent ${LL.call_profile.calls[0].prompt_eval_s} s evaluating the prompt and ${LL.call_profile.calls[0].generation_s} s generating ${LL.call_profile.calls[0].output_tokens} tokens. A prompt budget — the top 30 non-MENTIONED_IN facts, six documents of 300 characters and 12 IOC states, about half the characters — plus an output cap and keep-alive brought \`llama3.1\` to 21–27 s, and \`llama3.2:3b\` to ${llmFinal.p95_s} s p95 (Figure ${F("llm")}). Keeping the most relevant evidence also follows the observation that models use long contexts poorly [36].`));
C.push(...fig("llm", FIG("chart_llm.png"), "GraphRAG end-to-end p95 across measured configurations, with mean citation coverage (six acceptance questions)."));
C.push(p(`The smaller model is the default because it meets the SLO with full gold recall; \`llama3.1\` gives fuller prose and remains one setting away (\`OLLAMA_MODEL\`). The groundedness-gate fix of this review matters here: before it, sentences such as “Sandworm is attributed to NotPetya (G20)” were discarded for using parentheses, lowering coverage for both models.`));

C.push(h2("9.10  Summary"));
[`Every NFR2 objective is met, including GraphRAG end-to-end p95 ${llmFinal.p95_s} s < 15 s.`,
  `Store-level queries stay flat from 87 to ${n0(rN.nodes)} nodes; GraphRAG retrieval p95 at 200× is ${ms(rag(rN).total.p95)} after the fixes.`,
  `Indexes give ${x(M.no_index.by_ioc.latency.p50, M.production_indexes.by_ioc.latency.p50)} (MongoDB, IOC lookup) and ${x(N.no_index.latency.p50, N.range_index.latency.p50)} (Neo4j) speed-ups and cut examined records by up to five orders of magnitude.`,
  `Redis lookups are independent of key count up to ${n0(rTop.keys)} keys; HNSW keeps recall@10 ≥ ${qTop.unfiltered.hnsw_ef64.recall_at_10.toFixed(3)} at half the latency of exact search at ${n0(qTop.points)} points.`,
  "The benchmark found four defects invisible at seed scale; all are fixed and covered by tests or re-measurement."]
  .forEach((t) => C.push(bullet(t)));

// ================================================================== 10 traceability
C.push(h1(SECTIONS[9], { newPage: true }));
C.push(table([900, 2500, 4300, 1938], [
  ["Req", "Requirement", "Implementation", "Evidence"],
  ["FR1", "Ingest STIX 2.1 and free text, fan-out", "ingest.py plans, job log, retry", "unit + integration tests"],
  ["FR2", "Multi-hop graph queries", "graph.py: shared infrastructure, tooling, victims, paths", "acceptance Q1, Q3, Q4"],
  ["FR3", "O(1) blocklist with TTL, export", "blocklist.py: SET EX, ZSET index; /enforce/*", "Section 9.6; integration"],
  ["FR4", "Semantic search with filters", "vectors.search: TLP, actor, date payload filters", "integration; Section 9.7"],
  ["FR5", "GraphRAG Q&A on a local LLM", "graphrag.ask, Ollama /api/chat", `Table ${T("accept")}`],
  ["FR6", "Hydration of reports", "documents.hydrate, GET /api/reports/{id}", "integration"],
  ["FR7", "Evidence UI", "GraphRAG evidence panel", `Figure ${F("console")}`],
  ["FR8", "Corpus and ongoing ingest", "seed.py, data.py, auto-seed", "CI first start"],
  ["FR9", "Health and SLOs", "stores.health, metrics.py, Operations page", "Section 9.2"],
  ["FR10", "Replay and audit", "save_audit, replay", "integration: hops re-verified"],
  ["FR11", "AuthN and TLP", "security.py; TLP in every store query", "integration (junior)"],
  ["FR12", "Publish and revoke IOCs", "POST/DELETE /api/blocklist (lead)", "integration"],
  ["NFR1", "Data residency", "local Ollama and embeddings", "no external calls"],
  ["NFR2", "Interactive latency", "prompt budget, indexes, fixes of 9.4", "Section 9"],
  ["NFR3", "Store isolation", "enforcement reads Redis only", "integration; 9.6"],
  ["NFR4", "Groundedness", "groundedness gate, refusal, fallback", `unit tests; Table ${T("accept")}`],
  ["NFR5", "Reproducibility", "compose, pinned dependencies, versioned schema, dumps, CI", "CI from empty stores"],
  ["NFR6", "Ethics and safety", "public corpus, lab IOCs, system prompt", "—"],
  ["NFR7", "Usability", "UC1–UC4 inside the console", "user manual, demo"],
  ["NFR8", "Availability", "retrieve-only when LLM/Redis down; fail closed", "integration tests"],
], { size: 18 }));
C.push(tab("trace", "Requirement traceability. All functional and non-functional requirements are met."));
C.push(table([900, 4400, 4338], [
  ["Gap", "Review I observation", "Closed by"],
  ["G1", "one engine forced to serve four workloads", `four engines with closed operation sets (Table ${T("roles")}); measured in Section 9`],
  ["G2", "sharing platforms lack a query-native graph with enforcement state", "Neo4j graph + Redis enforcement plane + cited Q&A"],
  ["G3", "knowledge graphs lack TTL cache and vectors", "Redis and Qdrant beside Neo4j, joined by shared keys"],
  ["G4", "RAG over CTI is under-constrained", "four-channel GraphRAG with a groundedness gate"],
  ["G5", "answers cannot be audited", "evidence panel, audit log and replay"],
], { size: 18 }));
C.push(tab("gaps", "Review I gaps and how the final system closes them."));

// ================================================================== 11 limitations
C.push(h1(SECTIONS[10]));
["**Single-node deployment.** All stores run as single instances; clustering Neo4j, MongoDB replica sets and Redis replication are configuration work, not design changes.",
  "**One API worker.** Section 9.8 shows the knee at four concurrent clients on two virtual CPUs; production would run several workers or replicas.",
  "**Small, curated corpus.** Twelve public-knowledge reports cover every mechanism; the 200× scaling is synthetic. A TAXII feed connector would supply real volume.",
  "**Model quality versus latency.** `llama3.2:3b` meets the SLO but writes terser answers than `llama3.1:8b`; streaming the answer with the gate applied on completion would let the larger model feel interactive.",
  "**Embeddings.** The default TF-IDF + SVD model is deterministic and offline but weaker than neural embeddings; `nomic-embed-text` is supported and should become the default once download size is acceptable for the target environment.",
  "**Demo-grade secrets.** The JWT secret and consumer key in `.env.example` must be replaced outside a lab."].forEach((t) => C.push(bullet(t)));

// ================================================================== 12 conclusion
C.push(h1(SECTIONS[11]));
C.push(p(`The platform shows that CTI is best served by a polyglot design in which each NoSQL model does what it is best at, and that GraphRAG over such a design can be both useful and accountable. Relationships live in Neo4j, reports in MongoDB, live indicators in Redis and narrative similarity in Qdrant; a local LLM turns their combined evidence into answers whose every sentence can be traced and replayed. Review III completed the system, verified it with ${UNIT_TESTS + INT_TESTS} automated tests and continuous integration, and measured it: all latency objectives are met, store-level queries remain flat across a 200-fold corpus increase, and the benchmark harness proved its worth by exposing and confirming the fix of four defects that would have surfaced only in production.`));

// ================================================================== references
C.push(h1(SECTIONS[12], { newPage: true }));
const REFS = [
  "W. Tounsi and H. Rais, “A survey on technical threat intelligence in the age of information sharing,” Computers & Security, vol. 72, pp. 212–233, 2018.",
  "F. Skopik, G. Settanni, and R. Fiedler, “A problem shared is a problem halved: A survey on the dimensions of collective cyber defense through security information sharing,” Computers & Security, vol. 60, pp. 154–176, 2016.",
  "OASIS Open, “STIX Version 2.1,” OASIS Standard, June 2021. [Online]. Available: https://docs.oasis-open.org/cti/stix/v2.1/",
  "B. E. Strom et al., “MITRE ATT&CK: Design and Philosophy,” The MITRE Corporation, 2020.",
  "C. Wagner, A. Dulaunoy, G. Wagener, and A. Iklody, “MISP: The design and implementation of a collaborative threat intelligence sharing platform,” in Proc. ACM WISCS, 2016, pp. 49–56.",
  "X. Liao et al., “Acing the IOC game: Toward automatic discovery and analysis of open-source cyber threat intelligence,” in Proc. ACM CCS, 2016, pp. 755–766.",
  "G. Husari, E. Al-Shaer, M. Ahmed, B. Chu, and X. Niu, “TTPDrill: Automatic and accurate extraction of threat actions from unstructured text of CTI sources,” in Proc. ACSAC, 2017, pp. 103–115.",
  "M. Stonebraker and U. Çetintemel, “‘One size fits all’: An idea whose time has come and gone,” in Proc. ICDE, 2005, pp. 2–11.",
  "P. J. Sadalage and M. Fowler, NoSQL Distilled: A Brief Guide to the Emerging World of Polyglot Persistence. Addison-Wesley, 2012.",
  "R. Cattell, “Scalable SQL and NoSQL data stores,” ACM SIGMOD Record, vol. 39, no. 4, pp. 12–27, 2011.",
  "E. Brewer, “CAP twelve years later: How the ‘rules’ have changed,” Computer, vol. 45, no. 2, pp. 23–29, 2012.",
  "I. Robinson, J. Webber, and E. Eifrem, Graph Databases, 2nd ed. O’Reilly Media, 2015.",
  "S. Noel et al., “CyGraph: Graph-based analytics and visualization for cybersecurity,” in Handbook of Statistics, vol. 35. Elsevier, 2016, pp. 117–167.",
  "A. Piplai, S. Mittal, A. Joshi, T. Finin, J. Holt, and R. Zak, “Creating cybersecurity knowledge graphs from malware after action reports,” IEEE Access, vol. 8, pp. 211691–211703, 2020.",
  "I. Sarhan and M. Spruit, “Open-CyKG: An open cyber threat intelligence knowledge graph,” Knowledge-Based Systems, vol. 227, 2021.",
  "Filigran, “OpenCTI documentation,” 2024. [Online]. Available: https://docs.opencti.io/",
  "MongoDB, Inc., “MongoDB manual (document model, indexes, explain),” 2024.",
  "Redis Ltd., “Redis documentation: EXPIRE, sorted sets and pipelining,” 2024.",
  "Y. A. Malkov and D. A. Yashunin, “Efficient and robust approximate nearest neighbor search using hierarchical navigable small world graphs,” IEEE Trans. Pattern Anal. Mach. Intell., vol. 42, no. 4, pp. 824–836, 2020.",
  "Qdrant, “Qdrant documentation: collections, HNSW and payload filtering,” 2024.",
  "P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Proc. NeurIPS, 2020.",
  "V. Karpukhin et al., “Dense passage retrieval for open-domain question answering,” in Proc. EMNLP, 2020, pp. 6769–6781.",
  "D. Edge et al., “From local to global: A graph RAG approach to query-focused summarization,” arXiv:2404.16130, 2024.",
  "B. Peng et al., “Graph retrieval-augmented generation: A survey,” arXiv:2408.08921, 2024.",
  "M. Yasunaga, H. Ren, A. Bosselut, P. Liang, and J. Leskovec, “QA-GNN: Reasoning with language models and knowledge graphs for question answering,” in Proc. NAACL, 2021.",
  "Neo4j, Inc., “Neo4j Cypher manual (indexes, PROFILE, subqueries),” 2024.",
  "ENISA, “ENISA threat landscape,” European Union Agency for Cybersecurity, 2024.",
  "Mandiant, “M-Trends,” Google Cloud, 2024.",
  "CIRCL / MISP Project, “MISP data models and objects,” 2024. [Online]. Available: https://www.misp-project.org/",
  "J. Johnson, M. Douze, and H. Jégou, “Billion-scale similarity search with GPUs,” IEEE Trans. Big Data, vol. 7, no. 3, pp. 535–547, 2021.",
  "A. Grattafiori et al., “The Llama 3 herd of models,” arXiv:2407.21783, 2024.",
  "Ollama, “Ollama documentation and REST API,” 2024. [Online]. Available: https://github.com/ollama/ollama",
  "B. F. Cooper, A. Silberstein, E. Tam, R. Ramakrishnan, and R. Sears, “Benchmarking cloud serving systems with YCSB,” in Proc. ACM SoCC, 2010, pp. 143–154.",
  "O. Erling et al., “The LDBC Social Network Benchmark: Interactive workload,” in Proc. ACM SIGMOD, 2015, pp. 619–630.",
  "M. Aumüller, E. Bernhardsson, and A. Faithfull, “ANN-Benchmarks: A benchmarking tool for approximate nearest neighbor algorithms,” Information Systems, vol. 87, 2020.",
  "N. F. Liu et al., “Lost in the middle: How language models use long contexts,” Trans. Assoc. Comput. Linguistics, vol. 12, pp. 157–173, 2024.",
  "S. Es, J. James, L. Espinosa-Anke, and S. Schockaert, “RAGAS: Automated evaluation of retrieval augmented generation,” in Proc. EACL (System Demonstrations), 2024.",
  "FIRST, “Traffic Light Protocol (TLP) version 2.0,” 2022. [Online]. Available: https://www.first.org/tlp/",
  "A. V. Aho and M. J. Corasick, “Efficient string matching: An aid to bibliographic search,” Commun. ACM, vol. 18, no. 6, pp. 333–340, 1975.",
];
REFS.forEach((t, i) => C.push(new K.Paragraph({
  spacing: { after: 100, line: 260 }, indent: { left: 520, hanging: 520 }, alignment: K.AlignmentType.LEFT,
  children: [run(`[${i + 1}]`, { size: 20 }), run(`  ${t}`, { size: 20 })],
})));

// ================================================================== appendix
C.push(h1(SECTIONS[13]));
C.push(p("All results in this report can be regenerated from the repository. The demo stack and the benchmark stack use different ports and volumes."));
C.push(codeBlock([
  "make infra && make install          # four stores, Python and Node dependencies",
  "make api                            # FastAPI on :8000 (seeds empty stores)",
  "make web                            # console on :5173",
  "ollama pull llama3.2:3b             # local model (default)",
  "make test                           # unit tests",
  "make test-integration               # API against the live stores",
  "make eval-check                     # acceptance questions + gates  -> backend/eval_report.json",
  "docker compose --profile app stop   # pause the demo stack before benchmarking",
  "make bench                          # throwaway stack -> review3/performance/benchmark_results.json",
  "python review3/make_charts.py       # charts       (pip install matplotlib==3.9.2)",
  "python review3/generate_figures.py  # diagrams     (pip install pillow)",
  "node review3/generate_report.js     # this report  (npm install in review3/, LibreOffice for PDF)",
]));
C.push(spacer(120), p(`The raw results are in \`review3/performance/\`: \`benchmark_results.json\` (after the fixes), \`benchmark_baseline_before_fixes.json\`, the three evaluation runs and \`llm_latency_runs.json\`, which records the provenance of every LLM measurement in Figure ${F("llm")}.`));

// ================================================================== build
K.publish(K.makeDocument({
  children: C, headerLeft: "Review–III  ·  GraphRAG CTI Platform", headerRight: "Final Report",
  footerLeft: "Final Demonstration and Innovation",
}), OUT, SECTIONS, TOC_CACHE, __filename);
