// Review-III slide deck (pptx + pdf), with speaker notes.   node review3/generate_slides.js
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const PptxGenJS = require("pptxgenjs");

const FIG = (f) => path.join(__dirname, "figures", f);
const SHOT = (f) => path.join(__dirname, "screenshots", f);
const PERF = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "performance", f), "utf8"));
const OUT = path.join(__dirname, "Presentation_GraphRAG_CTI_Platform");

const R = PERF("benchmark_results.json");
const B = PERF("benchmark_baseline_before_fixes.json");
const E = PERF("eval_llama3.2-3b_default.json");
const LL = PERF("llm_latency_runs.json");
const CV = PERF("cloud_verification.json");
const EC = PERF("eval_real_data_cloud.json");
const rows = R.scale.rows;
const r1 = rows[0];
const rN = rows[rows.length - 1];
const bN = B.scale.rows[B.scale.rows.length - 1];
const rag = (r) => r.graphrag_retrieve_only;
const rTop = R.redis.rows[R.redis.rows.length - 1];
const M = R.mongo;
const N = R.neo4j;
const qTop = R.qdrant.rows[R.qdrant.rows.length - 1];
const llmFinal = LL.runs[LL.runs.length - 1];
const llmSept = LL.runs[0];
const ms = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)} s` : v >= 100 ? `${v.toFixed(0)} ms` : v >= 10 ? `${v.toFixed(1)} ms` : `${v.toFixed(2)} ms`);
const n0 = (v) => Math.round(v).toLocaleString("en-US");
const count = (file, re) => (fs.readFileSync(path.join(__dirname, "..", file), "utf8").match(re) || []).length;
const UNIT = count("backend/tests/test_units.py", /^def test_/gm);
const INTEG = count("backend/tests/test_api.py", /^def test_/gm);
const ENDPOINTS = count("backend/app/main.py", /^@app\.(get|post|delete|put)\(/gm);

// ------------------------------------------------------------------ design tokens
const NAVY = "0F2A47";
const INK = "1A1F26";
const MUTED = "5A6470";
const BG = "F7F6F2";
const CARD = "FFFFFF";
const AMBER = "C98500"; // fills only
const AMBER_TEXT = "9A6700"; // 4.9:1 on the light background
const STORE = { neo4j: "1F4E79", mongo: "0E5A66", redis: "7A2A2A", qdrant: "48306B", llm: "1B5E40" };
const HEAD = "Georgia";
const BODY = "Calibri";
const W = 10;
const H = 5.625;

const pres = new PptxGenJS();
pres.layout = "LAYOUT_16x9";
pres.author = "Shivansh Sharma, Himali Sharma, Aayush Sinha";
pres.title = "GraphRAG-Powered CTI Platform — Review III";
let n = 0;

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
// place an image inside a box, preserving aspect ratio, centred
function image(slide, file, x, y, w, h) {
  const s = pngSize(file);
  const r = Math.min(w / s.w, h / s.h);
  const iw = s.w * r;
  const ih = s.h * r;
  slide.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih });
}

function content(kicker, title, notes) {
  const s = pres.addSlide();
  n += 1;
  s.background = { color: BG };
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 0.36, w: 0.12, h: 0.12, fill: { color: AMBER }, line: { color: AMBER } });
  s.addText(kicker.toUpperCase(), { x: 0.7, y: 0.27, w: 8, h: 0.3, margin: 0, fontFace: BODY, fontSize: 10, bold: true, color: AMBER_TEXT, charSpacing: 2 });
  s.addText(title, { x: 0.5, y: 0.55, w: 9, h: 0.6, margin: 0, fontFace: HEAD, fontSize: 24, bold: true, color: NAVY });
  s.addText("GraphRAG CTI Platform  ·  Review III", { x: 0.5, y: 5.28, w: 5, h: 0.22, margin: 0, fontFace: BODY, fontSize: 8, color: MUTED });
  s.addText(String(n), { x: 8.9, y: 5.28, w: 0.6, h: 0.22, margin: 0, fontFace: BODY, fontSize: 8, color: MUTED, align: "right" });
  if (notes) s.addNotes(notes);
  return s;
}

// card with a coloured left bar (the deck's motif)
function card(s, x, y, w, h, color, title, lines, { size = 11, titleSize = 13 } = {}) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: CARD }, line: { color: "DCDCD6", width: 0.75 } });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h, fill: { color }, line: { color } });
  s.addText(title, { x: x + 0.2, y: y + 0.1, w: w - 0.3, h: 0.32, margin: 0, fontFace: BODY, fontSize: titleSize, bold: true, color });
  if (lines && lines.length) {
    s.addText(lines.map((t, i) => ({ text: t, options: { breakLine: i < lines.length - 1 } })),
      { x: x + 0.2, y: y + 0.44, w: w - 0.3, h: h - 0.52, margin: 0, fontFace: BODY, fontSize: size, color: INK, valign: "top", paraSpaceAfter: 3 });
  }
}

function stat(s, x, y, w, big, label, color = NAVY, sub = "") {
  s.addText(big, { x, y, w, h: 0.62, margin: 0, fontFace: HEAD, fontSize: 30, bold: true, color });
  s.addText(label, { x, y: y + 0.62, w, h: 0.3, margin: 0, fontFace: BODY, fontSize: 11, bold: true, color: INK });
  if (sub) s.addText(sub, { x, y: y + 0.9, w, h: 0.42, margin: 0, fontFace: BODY, fontSize: 9.5, color: MUTED, valign: "top" });
}

function bullets(s, items, x, y, w, h, size = 13) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
    { x, y, w, h, margin: 0, fontFace: BODY, fontSize: size, color: INK, valign: "top", paraSpaceAfter: 6 });
}

// ================================================================== 1 title
{
  const s = pres.addSlide();
  n += 1;
  s.background = { color: NAVY };
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.05, w: 0.12, h: 0.12, fill: { color: AMBER }, line: { color: AMBER } });
  s.addText("REVIEW III  ·  FINAL DEMONSTRATION AND INNOVATION", { x: 0.82, y: 0.96, w: 8, h: 0.3, margin: 0, fontFace: BODY, fontSize: 11, bold: true, color: "E3B341", charSpacing: 2 });
  s.addText("GraphRAG-Powered Cyber Threat Intelligence Platform", { x: 0.6, y: 1.4, w: 8.8, h: 1.2, margin: 0, fontFace: HEAD, fontSize: 34, bold: true, color: "FFFFFF", valign: "top" });
  s.addText("A multi-model NoSQL approach: Neo4j · MongoDB · Redis · Qdrant · local LLM", { x: 0.6, y: 2.65, w: 8.8, h: 0.4, margin: 0, fontFace: BODY, fontSize: 15, color: "CADCFC" });
  const team = [["Shivansh Sharma", "23BCE0254"], ["Himali Sharma", "23BCE0317"], ["Aayush Sinha", "23BCE0558"]];
  team.forEach(([nm, id], i) => {
    s.addText([{ text: nm, options: { bold: true, breakLine: true } }, { text: id, options: { color: "9FB3C8" } }],
      { x: 0.6 + i * 2.3, y: 3.6, w: 2.2, h: 0.6, margin: 0, fontFace: BODY, fontSize: 13, color: "FFFFFF" });
  });
  s.addText("Guide: Dr. Lydia Jane G  ·  VIT Vellore  ·  October 2026", { x: 0.6, y: 4.55, w: 8.8, h: 0.3, margin: 0, fontFace: BODY, fontSize: 12, color: "9FB3C8" });
  s.addNotes("Introduce the team and the project in one sentence: a CTI workstation where each kind of threat data lives in the NoSQL engine built for it, and a GraphRAG layer that answers analyst questions with every sentence cited. Today: the complete system, a live demo, and the performance evaluation, including four scalability defects our benchmark found and we fixed.");
}

// ================================================================== 2 problem
{
  const s = content("The problem", "Threat intelligence is four different shapes of data",
    "An analyst's questions touch four data shapes at once. Who shares C2 with APT28 is a graph question; a STIX report is a document with fields that differ per report; a blocklist entry must expire on time and be checked in microseconds; and 'what looks like this lure' is a similarity question. One database is optimal for at most one of these, which is the literature's 'one size does not fit all' argument. And plain RAG over CTI can produce confident attributions that no stored evidence supports.");
  const items = [
    [STORE.neo4j, "Relationships", "Which actors share C2 infrastructure with APT28?", "graph"],
    [STORE.mongo, "Reports", "STIX bundles and analyst reports, each with different nested fields", "document"],
    [STORE.redis, "Live indicators", "Is 185.86.77.12 still on the blocklist? It must expire on time.", "key–value + TTL"],
    [STORE.qdrant, "Narrative", "What else looks like this spearphishing lure?", "vector similarity"],
  ];
  items.forEach(([c, t, q, m], i) => card(s, 0.5 + i * 2.27, 1.45, 2.1, 2.35, c, t, [q, "", `→ ${m}`], { size: 11.5 }));
  s.addText([
    { text: "One engine fits at most one of these. ", options: { bold: true, color: NAVY } },
    { text: "And an LLM answering CTI questions must not invent attributions: every claim has to be traceable to stored evidence.", options: { color: INK } },
  ], { x: 0.5, y: 4.1, w: 9, h: 0.8, margin: 0, fontFace: BODY, fontSize: 14, valign: "top" });
}

// ================================================================== 3 what we built
{
  const s = content("Review III", "A complete, measured system",
    `What exists now: four stores each used for one job; ${ENDPOINTS} API endpoints behind JWT auth and TLP policy; an eight-page analyst console; ${UNIT} unit and ${INTEG} integration tests in CI; and a benchmark harness. The headline numbers: all gold evidence recalled on the six acceptance questions, GraphRAG p95 ${llmFinal.p95_s} seconds with the local model, and retrieval p95 of ${ms(rag(rN).total.p95)} even at 200 times the corpus.`);
  stat(s, 0.5, 1.5, 2.1, "4", "NoSQL engines", NAVY, "graph, document, key–value, vector — one job each");
  stat(s, 2.75, 1.5, 2.1, String(ENDPOINTS), "API endpoints", NAVY, "JWT roles, TLP on every read, fail-closed enforcement");
  stat(s, 5.0, 1.5, 2.1, String(UNIT + INTEG), "automated tests", NAVY, `${UNIT} unit + ${INTEG} integration, run in CI on every push`);
  stat(s, 7.25, 1.5, 2.25, `${(E.graphrag.gold_edge_recall * 100).toFixed(0)}%`, "gold evidence recalled", STORE.llm, "six acceptance questions, edges and reports");
  stat(s, 0.5, 3.3, 2.1, `${llmFinal.p95_s} s`, "GraphRAG p95", STORE.llm, `target < 15 s (was ${llmSept.p95_s} s)`);
  stat(s, 2.75, 3.3, 2.1, "200×", "corpus scaling tested", NAVY, `${n0(rN.nodes)} nodes, ${n0(rN.reports)} reports`);
  stat(s, 5.0, 3.3, 2.1, ms(rag(rN).total.p95), "retrieval p95 at 200×", STORE.llm, `was ${ms(rag(bN).total.p95)} before the fixes`);
  stat(s, 7.25, 3.3, 2.25, "4", "scalability defects fixed", AMBER_TEXT, "found by our own benchmark harness");
}

// ================================================================== 4 architecture
{
  const s = content("Architecture", "Each store does one job; the API owns policy",
    "Walk top to bottom. Clients: the React console and enforcement consumers, which only ever reach the enforcement API. The FastAPI layer owns authentication, TLP policy, ingest, GraphRAG orchestration, audit and operations. The four stores each expose a closed set of operations. The enforcement API reads Redis only and fails closed. The local model is called only by the orchestrator and never writes to a store.");
  image(s, FIG("r3_architecture.png"), 0.5, 1.3, 9, 3.9);
}

// ================================================================== 4b the databases themselves
{
  const s = content("The databases", "Four real database servers, each in its own console",
    "Before the application, show the databases themselves. Top left, Neo4j Browser running Cypher on the live graph: APT28 and Sandworm share a server. Top right, mongo-express showing report rpt-002 with its own nested build_pipeline field. Bottom left, Redis Commander: an IOC key with its value and a TTL counting down. Bottom right, the Qdrant dashboard: a vector point with its payload. All four run as Docker containers from the official images; make dbui opens the two consoles that are not built in, and review3/DATABASE_TOUR.md has the queries.");
  image(s, FIG("r3_db_consoles.png"), 0.5, 1.25, 6.3, 3.95);
  card(s, 7.0, 1.35, 2.5, 3.75, NAVY, "Open them live", [
    "Neo4j  :7474",
    "MongoDB  :8081",
    "Redis  :8082",
    "Qdrant  :6333/dashboard",
    "",
    "make dbui starts the MongoDB and Redis consoles (read-only)",
  ], { size: 11.5 });
}


// ================================================================== hosted databases + real data
{
  const s = content("Hosted · real data", "The same platform on four cloud databases",
    `The databases now run on their vendors' own cloud services: Neo4j AuraDB, MongoDB Atlas, Redis Cloud and Qdrant Cloud, all free tiers. Only the databases are hosted; the API, console and LLM stay on the laptop. Operations shows each store's cloud hostname and contents. They hold real public threat intelligence: MITRE ATT&CK version ${CV.import.attack_version} — 178 groups, 842 malware families and tools, 227 techniques, 57 campaigns — plus botnet C2 servers from abuse.ch Feodo Tracker and compromised hosts from Emerging Threats. ATT&CK's APT28, Sandworm and the other corpus actors merged onto the existing nodes.`);
  image(s, SHOT("cloud_operations.png"), 0.5, 1.28, 5.9, 3.9);
  card(s, 6.6, 1.3, 2.9, 1.9, NAVY, "Hosted on", [
    `AuraDB · Neo4j ${CV.services.neo4j.version.split(" ")[0]}`,
    `Atlas · MongoDB ${CV.services.mongodb.version}`,
    `Redis Cloud · Redis ${CV.services.redis.version}`,
    `Qdrant Cloud · Qdrant ${CV.services.qdrant.version}`,
  ], { size: 11 });
  card(s, 6.6, 3.35, 2.9, 1.85, STORE.llm, "Real feeds loaded", [
    `MITRE ATT&CK v${CV.import.attack_version}`,
    "abuse.ch Feodo Tracker · Emerging Threats",
    `${n0(CV.import.nodes)} nodes · ${n0(CV.import.relationships)} edges`,
    `${CV.import.reports} reports · ${CV.import.chunks} chunks · ${CV.health.redis.detail.split(" ")[0]} live IOCs`,
  ], { size: 11 });
}

{
  const s = content("Hosted · real data", "GraphRAG answers from ATT&CK in the cloud",
    `Asked against the hosted databases: which groups are behind ATT&CK's SolarWinds Compromise campaign, and what malware was used. The campaign C0024 merged onto our own SolarWinds node, so the answer cites APT29 and the ATT&CK software list — SUNBURST, GoldMax, SUNSPOT and others — with every sentence cited. Cobalt Strike and Mimikatz get the commodity-tool caution: ATT&CK records 32 and 51 groups using them. Across the six acceptance questions on the hosted stores, gold evidence recall is still 100 percent.`);
  image(s, SHOT("cloud_graphrag_solarwinds.png"), 0.5, 1.28, 6.4, 3.95);
  card(s, 7.1, 1.35, 2.4, 3.8, STORE.neo4j, "On the hosted stores", [
    `gold edges ${EC.graphrag.gold_edge_recall * 100}% · gold reports ${EC.graphrag.gold_report_recall * 100}%`,
    `citation coverage ${EC.graphrag.mean_citation_coverage.toFixed(2)}`,
    `integrity: ${EC.integrity.counts.mongodb_reports} reports in all stores`,
    `${CV.integration_tests_on_cloud.passed}/${CV.integration_tests_on_cloud.passed} integration tests pass`,
    `latency includes the internet: GraphRAG p95 ${(EC.graphrag.p95_ms / 1000).toFixed(1)} s`,
  ], { size: 11 });
}

{
  const s = content("Security · IP gate", "A blocklisted IP cannot use the platform",
    `Every API request is checked against the Redis blocklist. Here the client is ${CV.ip_gate.client}, a QakBot command-and-control server from abuse.ch: every route answers 403, only the health check stays open. Each refusal is logged in MongoDB Atlas with an expires_at time, and a TTL index deletes it after 7 days. We proved both expiries on the cloud: an IP published with a ${CV.ttl_proof.blocklist_ttl_s}-second TTL was admitted again after ${CV.ttl_proof.unblocked_after_s} seconds, and an expired log entry was removed by Atlas after ${CV.ttl_proof.expired_log_deleted_after_s} seconds. Below, the same key read directly from Redis Cloud with its TTL.`);
  image(s, SHOT("cloud_blocked_requests.png"), 0.5, 1.3, 6.2, 1.55);
  s.addText("The same key read straight from Redis Cloud (Redis Commander, read-only): value and TTL in seconds",
    { x: 0.5, y: 3.05, w: 6.2, h: 0.28, margin: 0, fontFace: BODY, fontSize: 10.5, bold: true, color: STORE.redis });
  image(s, SHOT("cloud_redis_cli.png"), 0.5, 3.35, 6.2, 1.8);
  card(s, 6.9, 1.3, 2.6, 3.85, STORE.redis, "Verified on the cloud", [
    `${CV.ip_gate.client} → HTTP ${CV.ip_gate.blocked_status}`,
    `health check → ${CV.ip_gate.health_status}`,
    "refusal log: TTL index expires_at_1 in Atlas",
    `expired log entry deleted in ${CV.ttl_proof.expired_log_deleted_after_s} s`,
    `${CV.ttl_proof.blocklist_ttl_s} s block → admitted after ${CV.ttl_proof.unblocked_after_s} s`,
    "Redis down → gate fails open; /enforce fails closed",
  ], { size: 11 });
}

// ================================================================== 5 data model
{
  const s = content("Data model", "One graph, three join keys",
    "The graph holds eight labels and twelve relationship types. Commodity tools such as Mimikatz are single shared nodes, which is what makes them hubs. Three keys join the stores: the report id is the Mongo _id, the Report node id and the Qdrant payload report_id; and an indicator's type and value is both the Indicator node key and the Redis key. Indicator nodes outlive their Redis key, so history and enforcement can legitimately disagree — that is use case UC4.");
  image(s, FIG("r3_graph_schema.png"), 0.4, 1.25, 5.9, 3.95);
  card(s, 6.5, 1.35, 3.0, 3.75, NAVY, "Join keys", [
    "Report.id = MongoDB _id = Qdrant report_id",
    "",
    "Indicator (type, value) = Redis key ioc:{type}:{value}",
    "",
    "Indicators stay in the graph after their TTL: enforcement and history can disagree (UC4).",
    "",
    "Integrity check: 3 hard + 2 informational cross-store rules.",
  ], { size: 11 });
}

// ================================================================== 6 GraphRAG
{
  const s = content("GraphRAG", "Four-channel retrieval, a local LLM, and a gate",
    "Entity linking maps names and IOCs in the question to graph ids. Four channels retrieve in parallel, each filtered by the analyst's TLP clearance at the source. Every item gets a citation id: G for a graph edge, C for a passage, R for a report, I for an IOC state. The full pack goes to the evidence panel and the audit log; the LLM sees a ranked, trimmed pack. The gate keeps only sentences with a valid tag and refuses below 50 percent; a refused answer is replaced by deterministic evidence sentences, never by an unsupported one.");
  image(s, FIG("r3_answer_path.png"), 0.5, 1.28, 9, 3.95);
}

// ================================================================== 7 console
{
  const s = content("Live system", "Every sentence is cited and every hop is visible",
    "This is acceptance question 4 answered live by llama3.2:3b. The chips under each sentence link to the evidence; G16 and G17 are the ATTRIBUTED_TO_CAMPAIGN edges for NotPetya and Industroyer. The amber box is the commodity-hub caution. On the right, the evidence panel animates the cited hops. Coverage is 100 percent; the answer took about 11 seconds.");
  image(s, SHOT("graphrag_answer.png"), 0.5, 1.28, 6.4, 3.95);
  card(s, 7.1, 1.35, 2.4, 3.8, STORE.llm, "Reading an answer", [
    "llm / retrieve-only mode",
    "TLP label of the cited reports",
    "citation coverage",
    "G · C · R · I citation chips",
    "⚠ commodity-tool caution",
    "evidence: hops, chunks, documents, IOC state, latency",
    "audit link → replay",
  ], { size: 10.5 });
}

// ================================================================== 8 innovation
{
  const s = content("Innovation", "What is new in this design",
    "Eight things set this apart from MISP, OpenCTI or a plain RAG chatbot. Emphasise the gate with its deterministic fallback, TLP enforced inside each store query rather than after generation, the separation of the fail-closed enforcement plane from the analyst read path, replayable answers, and a fully local model that meets the latency target because of the prompt budget.");
  const items = [
    [STORE.neo4j, "Four-store GraphRAG", "typed citations across graph, documents, vectors and cache"],
    [STORE.redis, "Groundedness gate", "uncited sentences removed; refusal + evidence-only fallback"],
    [STORE.mongo, "Hub-aware traversal", "stops at commodity tools; weak-attribution caution"],
    [STORE.qdrant, "TLP inside retrieval", "payload filter, $in filter, graph filter; answers labelled"],
    [STORE.redis, "Fail-closed enforcement", "Redis-only API; 503 blocked:true when Redis is down"],
    [STORE.mongo, "Replayable answers", "re-verify every hop, chunk and IOC weeks later"],
    [STORE.llm, "Local AI, prompt budget", "3B model meets the 15 s SLO with no cloud API"],
    [AMBER_TEXT, "Self-measuring", "evaluation gate + benchmark harness in the code base"],
  ];
  items.forEach(([c, t, d], i) => card(s, 0.5 + (i % 4) * 2.27, 1.4 + Math.floor(i / 4) * 1.9, 2.1, 1.7, c, t, [d], { size: 11, titleSize: 12.5 }));
}

// ================================================================== 9 NoSQL capabilities
{
  const s = content("Advanced NoSQL", "Using each engine beyond CRUD",
    "One slide per store would be too much; these are the capabilities you can ask us about. Neo4j: variable-length paths with COUNT subquery predicates and weighted ranking, composite uniqueness, PROFILE-driven tuning. MongoDB: schema-on-read with multikey indexes verified by explain. Redis: TTL plus a sorted-set expiry index and pipelining. Qdrant: HNSW with tunable ef and payload-indexed filters, with exact search as ground truth.");
  const cols = [
    [STORE.neo4j, "Neo4j", ["variable-length paths with COUNT {} predicates (hub budget)", "weighted path ranking with reduce()", "composite (type, value) uniqueness", "UNION-of-labels index seeks", "CALL … IN TRANSACTIONS bulk writes"]],
    [STORE.mongo, "MongoDB", ["schema-on-read report fields", "multikey indexes on actors and IOCs", "explain() to verify IXSCAN", "idempotent replace_one upserts", "collStats for index sizing"]],
    [STORE.redis, "Redis", ["per-key TTL (SET EX)", "sorted-set expiry index", "pipelined GET + TTL", "hot set via ZRANGEBYSCORE", "AOF persistence"]],
    [STORE.qdrant, "Qdrant", ["HNSW, cosine, m = 16", "keyword + integer payload indexes", "filtered k-NN", "tunable ef (recall vs speed)", "exact search as ground truth"]],
  ];
  cols.forEach(([c, t, l], i) => card(s, 0.5 + i * 2.27, 1.4, 2.1, 2.95, c, t, l, { size: 11 }));
  s.addText([{ text: "Each claim is measured, not assumed: ", options: { bold: true, color: NAVY } },
    { text: "Neo4j PROFILE, MongoDB explain() and exact k-NN as ground truth back every index and traversal choice (Section 9).", options: { color: INK } }],
  { x: 0.5, y: 4.55, w: 9, h: 0.55, margin: 0, fontFace: BODY, fontSize: 12, valign: "top" });
}

// ================================================================== 10 testing
{
  const s = content("Validation", "Tested at three levels, on every push",
    `Unit tests cover policy and parsing; ${INTEG} integration tests drive the real API against live stores and clean up after themselves; the evaluation gate runs the six acceptance questions and fails the build if any gold edge or report is missed. All of it runs in GitHub Actions on fresh containers. In the final run every question recalled its gold evidence; question 2's draft was caught by the gate and replaced by the evidence answer — that is the safety net working.`);
  card(s, 0.5, 1.4, 3.2, 3.7, NAVY, "Test tiers", [
    `${UNIT} unit tests — TLP, parsing, linker equivalence, gate`,
    `${INTEG} integration tests — real API, live stores`,
    "Evaluation gate — 6 questions, exits non-zero on a miss",
    "Benchmarks — 6 experiments",
    "CI — all of the above, fresh containers, every push",
  ], { size: 11 });
  const tableRows = [[
    { text: "Acceptance question", options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } },
    { text: "Edges", options: { bold: true, color: "FFFFFF", fill: { color: NAVY }, align: "center" } },
    { text: "Reports", options: { bold: true, color: "FFFFFF", fill: { color: NAVY }, align: "center" } },
    { text: "Coverage", options: { bold: true, color: "FFFFFF", fill: { color: NAVY }, align: "center" } },
  ]];
  const short = ["Shared C2 + hosted malware", "APT29 ↔ SUNBURST supply chain", "Cobalt Strike users besides FIN7",
    "Sandworm campaigns + APT28 infra", "Spearphishing analogue search", "Why Mimikatz is weak attribution"];
  E.graphrag.questions.forEach((q, i) => tableRows.push([short[i] + (q.mode.startsWith("retrieve") ? " (gate fallback)" : ""),
    { text: q.gold_edges_recalled, options: { align: "center" } }, { text: q.gold_reports_recalled, options: { align: "center" } },
    { text: q.citation_coverage.toFixed(2), options: { align: "center" } }]));
  s.addTable(tableRows, { x: 3.9, y: 1.4, w: 5.6, colW: [3.2, 0.75, 0.8, 0.85], fontFace: BODY, fontSize: 10.5, color: INK,
    border: { type: "solid", pt: 0.5, color: "DCDCD6" }, fill: { color: CARD }, rowH: 0.36 });
  s.addText(`All gold evidence recalled · no refusals · mean coverage ${E.graphrag.mean_citation_coverage.toFixed(2)}`,
    { x: 3.9, y: 4.05, w: 5.6, h: 0.3, margin: 0, fontFace: BODY, fontSize: 11, bold: true, color: STORE.llm });
}

// ================================================================== 11 SLOs
{
  const s = content("Performance · service levels", "Every latency objective is met",
    `The three NFR2 targets. Redis p99 ${E.latency.redis_get_p99_ms} milliseconds against 5, and ${rTop.get_hit.p99} at half a million keys. Neo4j three-hop p95 ${E.latency.graph_3hop_p95_ms} milliseconds against 500. GraphRAG end to end, with the LLM, ${llmFinal.p95_s} seconds against 15. Benchmarks ran on a 2-vCPU, 4 GB Docker VM, so these are conservative.`);
  const slo = [
    [STORE.redis, "Redis blocklist GET", `${E.latency.redis_get_p99_ms} ms`, "p99 · target < 5 ms", `${rTop.get_hit.p99} ms at ${n0(rTop.keys)} keys`],
    [STORE.neo4j, "Neo4j 1–3 hop", `${E.latency.graph_3hop_p95_ms} ms`, "3-hop p95 · target < 500 ms", `1-hop ${E.latency.graph_1hop_p95_ms} ms · 2-hop ${E.latency.graph_2hop_p95_ms} ms`],
    [STORE.llm, "GraphRAG with LLM", `${llmFinal.p95_s} s`, "p95 · target < 15 s", `llama3.2:3b · was ${llmSept.p95_s} s`],
  ];
  slo.forEach(([c, t, big, lab, sub], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.45, 2.85, 2.6, c, t, []);
    stat(s, x + 0.2, 1.95, 2.5, big, lab, c, sub);
  });
  s.addText("Measured with make eval and make bench · Apple M3 Pro host, Docker VM with 2 vCPU / 4 GB shared by all engines",
    { x: 0.5, y: 4.35, w: 9, h: 0.3, margin: 0, fontFace: BODY, fontSize: 10.5, italic: true, color: MUTED });
}

// ================================================================== 12 scalability
{
  const s = content("Performance · scalability", `1× → 200×: store queries stay flat`,
    `We cloned the corpus up to 200 times through the production loader: ${n0(rN.nodes)} nodes and ${n0(rN.reports)} reports. Every store query stays within a few milliseconds. Neo4j traversal cost depends on the neighbourhood, not graph size, and the hub budget caps the evidence at ${rag(rN).max_evidence_edges} edges at every scale.`);
  image(s, FIG("chart_scale_stores.png"), 0.4, 1.25, 6.2, 3.95);
  card(s, 6.8, 1.35, 2.7, 3.75, NAVY, `At 200× (${n0(rN.nodes)} nodes)`, [
    `Neo4j 2-hop p95  ${ms(rN.neo4j.neighbourhood_2hop.p95)}`,
    `MongoDB by actor  ${ms(rN.mongodb.list_by_actor.p95)}`,
    `Qdrant k-NN  ${ms(rN.qdrant.knn_k6_tlp_filter.p95)}`,
    `Redis GET  ${ms(rN.redis.blocklist_get.p95)}`,
    `Entity linking  ${ms(rN.graphrag_retrieve_only.channels.linking.p95)}`,
    "",
    `Evidence capped at ${rag(rN).max_evidence_edges} edges by the hub budget`,
  ], { size: 11.5 });
}

// ================================================================== 13 bottlenecks
{
  const s = content("Performance · what the benchmark found", "Four defects, invisible at seed scale",
    `The first scaling run looked very different: retrieval grew linearly, to ${ms(rag(bN).total.p95)} p95 at 200 times. Profiling found four causes. Entity linking ran one regex per gazetteer entry; we replaced it with an inverted index, proven identical by a test. A global query was unbounded and fetched nodes one at a time with a label-less match — a full scan each; we bounded it and batched the lookups through index seeks. Ingest re-joined the whole graph. And under concurrency a shared Qdrant client caused HTTP 500s; now each worker thread has its own client.`);
  image(s, FIG("chart_scale_fix.png"), 0.4, 1.25, 5.6, 2.3);
  const defects = [
    ["Linear entity linking", "→ inverted index", `${ms(bN.graphrag_retrieve_only.channels.linking.p50)} → ${ms(rN.graphrag_retrieve_only.channels.linking.p50)}`],
    ["Unbounded query + N+1 full scans", "→ LIMIT + batched index seeks", `p95 ${ms(rag(bN).total.p95)} → ${ms(rag(rN).total.p95)}`],
    ["Whole-graph join on ingest", "→ plan-scoped join", `${bN.ingest.reports_per_s} → ${rN.ingest.reports_per_s} reports/s`],
    ["Shared vector client under load", "→ one client per thread", "HTTP 500 → 0 errors"],
  ];
  defects.forEach(([a, b, c], i) => {
    const y = 3.7 + i * 0.37;
    s.addText([{ text: `${a} `, options: { bold: true, color: NAVY } }, { text: b, options: { color: INK } }],
      { x: 0.5, y, w: 4.6, h: 0.32, margin: 0, fontFace: BODY, fontSize: 11 });
    s.addText(c, { x: 5.1, y, w: 1.9, h: 0.32, margin: 0, fontFace: BODY, fontSize: 11, bold: true, color: STORE.llm });
  });
  card(s, 7.2, 1.35, 2.3, 3.75, AMBER_TEXT, "At 200×", [
    "retrieval median", `${ms(rag(bN).total.p50)} → ${ms(rag(rN).total.p50)}`, "",
    "retrieval p95", `${ms(rag(bN).total.p95)} → ${ms(rag(rN).total.p95)}`, "",
    "ingest", `${bN.ingest.reports_per_s} → ${rN.ingest.reports_per_s} reports/s`,
  ], { size: 12 });
}

// ================================================================== 14 indexing
{
  const s = content("Performance · indexing", "Indexes turn scans into seeks",
    `On ${n0(M.documents)} synthetic reports MongoDB without secondary indexes scans the collection: looking up the reports that cite an IOC reads all ${n0(M.no_index.by_ioc.docs_examined)} documents in ${ms(M.no_index.by_ioc.latency.p50)}; with the multikey index it reads ${M.production_indexes.by_ioc.docs_examined} in ${ms(M.production_indexes.by_ioc.latency.p50)}. In Neo4j a label scan over ${n0(N.nodes)} nodes costs ${n0(N.no_index.db_hits)} database hits; the range index makes it ${N.range_index.db_hits}. The production indexes cost about ${(Object.entries(M.index_mb).filter(([k]) => k !== "_id_" && k !== "tlp_1_date_-1").reduce((a, [, v]) => a + v, 0)).toFixed(0)} MB on ${M.data_mb} MB of data.`);
  image(s, FIG("chart_indexes.png"), 0.4, 1.25, 6.4, 3.0);
  stat(s, 7.0, 1.4, 2.5, `${Math.round(M.no_index.by_ioc.latency.p50 / M.production_indexes.by_ioc.latency.p50)}×`, "MongoDB IOC lookup", STORE.mongo, `${n0(M.no_index.by_ioc.docs_examined)} → ${M.production_indexes.by_ioc.docs_examined} documents read`);
  stat(s, 7.0, 2.85, 2.5, `${Math.round(N.no_index.latency.p50 / N.range_index.latency.p50)}×`, "Neo4j lookup by value", STORE.neo4j, `${n0(N.no_index.db_hits)} → ${N.range_index.db_hits} db hits`);
  s.addText("Plans verified with MongoDB explain() (COLLSCAN → IXSCAN) and Neo4j PROFILE (NodeByLabelScan → NodeIndexSeek).",
    { x: 0.5, y: 4.45, w: 9, h: 0.5, margin: 0, fontFace: BODY, fontSize: 11, italic: true, color: MUTED });
}

// ================================================================== 15 redis + qdrant
{
  const s = content("Performance · key–value and vector", "O(1) enforcement, accurate vector search",
    `Redis: the enforcement lookup is independent of key count — ${ms(rTop.get_hit.p50)} median at half a million keys — while any lookup not by key is a full scan, a second at that size. That is why we never query Redis by attribute. Qdrant: exact search grows linearly; HNSW stays near ${ms(qTop.unfiltered.hnsw_ef64.p50)} with recall ${qTop.unfiltered.hnsw_ef64.recall_at_10.toFixed(3)}. Filtering by TLP needs a wider search breadth, ef 128, to keep recall at ${qTop.tlp_filter.hnsw_ef128.recall_at_10.toFixed(3)}.`);
  card(s, 0.5, 1.4, 3.0, 3.7, STORE.redis, "Redis at 500,000 keys", []);
  stat(s, 0.7, 1.9, 2.7, ms(rTop.get_hit.p50), "GET + TTL median", STORE.redis, `p99 ${ms(rTop.get_hit.p99)} · flat from 1k keys`);
  stat(s, 0.7, 3.35, 2.7, ms(rTop.full_scan_ms), "full SCAN (non-key lookup)", AMBER_TEXT, `grows linearly · ${rTop.used_memory_mb} MB memory`);
  image(s, FIG("chart_qdrant.png"), 3.7, 1.4, 5.8, 3.0);
  s.addText(`Qdrant, ${n0(qTop.points)} points: HNSW ${ms(qTop.unfiltered.hnsw_ef64.p50)} vs exact ${ms(qTop.unfiltered.exact.p50)} · recall@10 ${qTop.unfiltered.hnsw_ef64.recall_at_10.toFixed(3)} (ef 64)`,
    { x: 3.7, y: 4.5, w: 5.8, h: 0.5, margin: 0, fontFace: BODY, fontSize: 11, bold: true, color: STORE.qdrant });
}

// ================================================================== 16 load
{
  const enfPeak = R.load.enforce_check.reduce((a, b) => (b.throughput_rps > a.throughput_rps ? b : a));
  const s = content("Performance · concurrency", "One worker: ~1,500 checks/s, then queueing",
    `With one Uvicorn worker the enforcement check peaks at about ${n0(enfPeak.throughput_rps)} requests per second with four clients, with zero errors at any level after the thread-safety fix. Beyond that the Python worker, sharing two vCPUs with the databases, is the bottleneck, so latency rises from queueing. The stores are not the limit; scaling out means more workers or replicas.`);
  image(s, FIG("chart_load.png"), 0.4, 1.25, 6.4, 3.9);
  card(s, 7.0, 1.35, 2.5, 3.75, NAVY, "Takeaways", [
    `peak ${n0(enfPeak.throughput_rps)} enforcement checks/s`,
    "0 errors at 64 clients",
    "knee at 4 clients: one Python worker on 2 vCPUs",
    "scale out with workers or replicas — the stores are not the limit",
  ], { size: 11.5 });
}

// ================================================================== 17 LLM
{
  const prof = LL.call_profile.calls[0];
  const s = content("Performance · LLM latency", `From ${llmSept.p95_s} s to ${llmFinal.p95_s} s without a GPU server`,
    `Profiling showed the time went to reading the prompt: with the full evidence pack, llama3.1 spent ${prof.prompt_eval_s} of ${prof.wall_s} seconds evaluating ${n0(prof.prompt_tokens)} prompt tokens. The prompt budget — the top 30 facts, six short documents, twelve IOC states — halves the prompt; with the output cap and keep-alive llama3.1 reaches 21 to 27 seconds and llama3.2:3b ${llmFinal.p95_s} seconds. The gate fix stopped valid citations written as (G20) or G1-G4 from being thrown away.`);
  image(s, FIG("chart_llm.png"), 0.4, 1.25, 6.3, 3.95);
  card(s, 6.9, 1.35, 2.6, 3.75, STORE.llm, "Why it got faster", [
    `prompt evaluation was ${prof.prompt_eval_s} s of a ${prof.wall_s} s call`,
    "prompt budget: ~½ the characters",
    "output cap 320 tokens, model kept loaded",
    "default llama3.2:3b; llama3.1 is one setting away",
  ], { size: 11.5 });
}

// ================================================================== 18 traceability
{
  const s = content("Requirements", "All 20 requirements met, all 5 gaps closed",
    "Every functional requirement maps to code and to a test or measurement; the full table is in Section 10 of the report. The five gaps from Review I are closed: four engines with closed operation sets, a graph with an enforcement plane, Redis and Qdrant beside the graph, a constrained four-channel GraphRAG, and replayable evidence.");
  const fr = ["FR1 ingest", "FR2 multi-hop", "FR3 blocklist", "FR4 search", "FR5 GraphRAG", "FR6 hydration", "FR7 evidence UI", "FR8 corpus",
    "FR9 health/SLO", "FR10 replay", "FR11 TLP", "FR12 publish"];
  const nfr = ["NFR1 local only", "NFR2 latency", "NFR3 isolation", "NFR4 grounded", "NFR5 reproducible", "NFR6 ethics", "NFR7 usability", "NFR8 availability"];
  [...fr, ...nfr].forEach((t, i) => {
    const col = i % 5;
    const row = Math.floor(i / 5);
    const x = 0.5 + col * 1.82;
    const y = 1.4 + row * 0.52;
    const c = i < fr.length ? NAVY : STORE.llm;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 1.7, h: 0.42, fill: { color: CARD }, line: { color: "DCDCD6", width: 0.75 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.06, h: 0.42, fill: { color: c }, line: { color: c } });
    s.addText(`✓ ${t}`, { x: x + 0.12, y, w: 1.55, h: 0.42, margin: 0, fontFace: BODY, fontSize: 10.5, color: INK, valign: "middle" });
  });
  s.addText([{ text: "Review I gaps closed: ", options: { bold: true, color: NAVY } },
    { text: "G1 one engine for four workloads · G2 no graph + enforcement plane · G3 no TTL cache or vectors beside the graph · G4 under-constrained RAG · G5 un-auditable answers", options: { color: INK } }],
  { x: 0.5, y: 3.6, w: 9, h: 0.8, margin: 0, fontFace: BODY, fontSize: 12, valign: "top" });
}

// ================================================================== 19 demo plan
{
  const s = content("Live demo", "Six minutes, four use cases",
    "Run the demo from the runbook in review3/DEMO_RUNBOOK.md. Re-seed five minutes before so the short TTLs are fresh. If the LLM is slow or down, untick 'use local LLM' — retrieve-only answers are instant and still cited.");
  const stepsList = [
    ["UC1", "Shared C2 with APT28", "Sandworm via 185.86.77.12; cited rpt-001; IOC state"],
    ["UC2", "Similar spearphishing", "Qdrant passages → APT28 / APT29 → reports"],
    ["UC3", "Mimikatz attribution", "five users, commodity-hub caution"],
    ["UC4", "Indicator expiry", "TTL hits zero; graph still remembers"],
    ["TLP", "Sign in as junior", "AMBER reports vanish; 403 on rpt-001"],
    ["Ops", "Ingest, replay, health", "STIX fan-out; replay re-verifies; SLO view"],
  ];
  stepsList.forEach(([tag, t, d], i) => {
    const x = 0.5 + (i % 3) * 3.05;
    const y = 1.4 + Math.floor(i / 3) * 1.85;
    s.addShape(pres.shapes.OVAL, { x, y: y + 0.05, w: 0.62, h: 0.62, fill: { color: i < 4 ? NAVY : AMBER }, line: { color: i < 4 ? NAVY : AMBER } });
    s.addText(tag, { x, y: y + 0.05, w: 0.62, h: 0.62, margin: 0, fontFace: BODY, fontSize: 11, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    s.addText(t, { x: x + 0.75, y, w: 2.15, h: 0.4, margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: NAVY, valign: "middle" });
    s.addText(d, { x: x + 0.75, y: y + 0.4, w: 2.15, h: 0.9, margin: 0, fontFace: BODY, fontSize: 11, color: INK, valign: "top" });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.45, w: 9, h: 0.6, fill: { color: CARD }, line: { color: "DCDCD6", width: 0.75 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.45, w: 0.07, h: 0.6, fill: { color: AMBER }, line: { color: AMBER } });
  s.addText([{ text: "Before the demo: ", options: { bold: true, color: NAVY } },
    { text: "make seed 5 minutes ahead (fresh TTLs) · warm the model with one question · if the LLM stalls, untick “use local LLM” — answers stay cited", options: { color: INK } }],
  { x: 0.72, y: 4.45, w: 8.7, h: 0.6, margin: 0, fontFace: BODY, fontSize: 11.5, valign: "middle" });
}

// ================================================================== 20 limitations
{
  const s = content("Limitations and next steps", "What we would do next",
    "Be candid. Single-node stores and one API worker are deployment choices, not design limits. The real feeds are imported on demand rather than streamed, and the 200 times scaling is synthetic; a TAXII connector with scheduled refresh is next. On free cloud tiers in other regions, latency includes the internet. The 3B model meets the SLO but writes terser answers; streaming would let the 8B model feel interactive. Neural embeddings are supported but not the default.");
  card(s, 0.5, 1.4, 4.4, 3.1, MUTED, "Limitations", [
    "single-node stores; one API worker",
    "feeds are imported, not streamed; 200× scaling is synthetic",
    "free-tier cloud adds internet latency",
    "3B model is terser than 8B",
    "TF-IDF embeddings by default",
    "lab secrets in .env.example",
  ], { size: 14 });
  card(s, 5.1, 1.4, 4.4, 3.1, STORE.llm, "Next steps", [
    "Uvicorn workers / replicas; Neo4j and Mongo clustering",
    "TAXII connector with scheduled refresh",
    "stream answers, gate on completion → 8B feels interactive",
    "nomic-embed-text as default embedder",
    "secrets from a vault; SSO for analysts",
  ], { size: 14 });
  s.addText("None of these needs a design change: each is configuration, scale-out or a new connector.",
    { x: 0.5, y: 4.65, w: 9, h: 0.4, margin: 0, fontFace: BODY, fontSize: 12, italic: true, color: MUTED });
}

// ================================================================== 21 close
{
  const s = pres.addSlide();
  n += 1;
  s.background = { color: NAVY };
  s.addText("Each store does what it is best at — and every answer can be traced.", { x: 0.6, y: 1.2, w: 8.8, h: 1.3, margin: 0, fontFace: HEAD, fontSize: 28, bold: true, color: "FFFFFF", valign: "top" });
  const facts = [[`${llmFinal.p95_s} s`, "GraphRAG p95 (< 15 s)"], ["100%", "gold evidence recalled"], [ms(rag(rN).total.p95), "retrieval p95 at 200×"], [String(UNIT + INTEG), "automated tests in CI"]];
  facts.forEach(([b, l], i) => {
    s.addText(b, { x: 0.6 + i * 2.25, y: 2.85, w: 2.1, h: 0.6, margin: 0, fontFace: HEAD, fontSize: 26, bold: true, color: "E3B341" });
    s.addText(l, { x: 0.6 + i * 2.25, y: 3.45, w: 2.1, h: 0.4, margin: 0, fontFace: BODY, fontSize: 12, color: "CADCFC" });
  });
  s.addText("Thank you — questions?", { x: 0.6, y: 4.4, w: 8.8, h: 0.5, margin: 0, fontFace: BODY, fontSize: 18, bold: true, color: "FFFFFF" });
  s.addText("github.com/Shivansharmaaaa/graphrag", { x: 0.6, y: 4.9, w: 8.8, h: 0.3, margin: 0, fontFace: BODY, fontSize: 11, color: "9FB3C8" });
  s.addNotes("Close on the thesis: polyglot persistence plus constrained GraphRAG gives answers that are both useful and accountable, and the numbers back it. Then take questions — the likely ones and crisp answers are in review3/DEMO_RUNBOOK.md.");
}

pres.writeFile({ fileName: `${OUT}.pptx` }).then(() => {
  execFileSync("soffice", ["--headless", "--convert-to", "pdf", "--outdir", __dirname, `${OUT}.pptx`], { stdio: "ignore" });
  console.log(`wrote ${OUT}.pptx and .pdf — ${n} slides`);
});
