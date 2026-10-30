// Review-III submission document (docx + pdf): the working system and its four databases, shown
// with screenshots and terminal output captured from the live local stack.
//   node review3/capture_submission.js review3/submission/screenshots   # screenshots
//   (terminal output in review3/submission/logs/ — see Appendix A for the commands)
//   node review3/generate_submission.js                                 # this document
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { ImageRun, TextRun, Table, TableRow, TableCell, WidthType, ShadingType } = require("docx");
const K = require("./doc_kit");

const { p, h1, h2, caption, bullet, table, callout, spacer, run, runB, CW, CW_PX } = K;
const ROOT = path.join(__dirname, "..");
const SUB = path.join(__dirname, "submission");
const SHOT = (f) => path.join(SUB, "screenshots", `${f}.png`);
const LOG = (f) => fs.readFileSync(path.join(SUB, "logs", f), "utf8").replace(/\s+$/, "").split("\n");
const EVAL = JSON.parse(fs.readFileSync(path.join(SUB, "logs", "eval_live.json"), "utf8"));
const OUT = path.join(__dirname, "Review3_Submission_GraphRAG_CTI_Platform");
const TOC_CACHE = path.join(__dirname, "build", "submission_toc.json");
const IMG_DIR = path.join(__dirname, "build", "submission_img");

const CAPTURED = "30 October 2026";
const ENDPOINTS = (fs.readFileSync(path.join(ROOT, "backend", "app", "main.py"), "utf8").match(/^@app\.(get|post|delete|put)\(/gm) || []).length;
const N_SHOTS = fs.readdirSync(path.join(SUB, "screenshots")).filter((f) => f.endsWith(".png")).length;

// ------------------------------------------------------------------ screenshots -> framed JPEGs
// Scaled to 1800 px wide and given a 2 px grey frame so white consoles stand off the page.
// The pixels inside the frame are the screenshot as captured.
fs.mkdirSync(IMG_DIR, { recursive: true });
const PREP = `
import sys, json, glob, os
from PIL import Image, ImageOps
src, dst = sys.argv[1], sys.argv[2]
sizes = {}
for f in sorted(glob.glob(os.path.join(src, "*.png"))):
    name = os.path.splitext(os.path.basename(f))[0]
    im = Image.open(f).convert("RGB")
    if im.width > 1800:
        im = im.resize((1800, round(im.height * 1800 / im.width)), Image.LANCZOS)
    im = ImageOps.expand(im, border=2, fill="#9AA3AD")
    out = os.path.join(dst, name + ".jpg")
    im.save(out, "JPEG", quality=86, optimize=True)
    sizes[name] = [im.width, im.height]
print(json.dumps(sizes))
`;
const SIZES = JSON.parse(execFileSync("python3", ["-c", PREP, path.join(SUB, "screenshots"), IMG_DIR], { encoding: "utf8" }));

// ------------------------------------------------------------------ contents (two-pass page numbers)
const SECTIONS = [
  "1.  Project Summary", "2.  System Under Demonstration", "3.  Working System: Analyst Console",
  "4.  Working System: REST and Enforcement API", "5.  Live Databases",
  "6.  One Indicator Across the Four Databases", "7.  Tests and Evaluation on the Live System",
  "8.  Submission Contents", "Appendix A.  Reproducing This Document",
];
const tocPages = K.tocFrom(TOC_CACHE);

// figure / table numbers resolve from these orders, so references in the text cannot drift
const FIG_ORDER = ["arch",
  "login", "qakbot", "hops", "iocs", "chunks", "latency", "solarwinds", "graph", "reports", "report",
  "search", "blocklist", "blocked", "ingest", "tlpReports", "tlpForbidden", "audit", "replay", "ops",
  "swagger", "swaggerHealth",
  "neoCounts", "neoSandworm", "neoQakbot", "neoShared",
  "mongoDb", "mongoReports", "mongoDoc", "mongoBlocked",
  "redisKey",
  "qdrantCollections", "qdrantPoints", "qdrantMap"];
const TAB_ORDER = ["stores", "env", "trace", "tests", "slo", "accept", "contents"];
const F = (k) => { const i = FIG_ORDER.indexOf(k); if (i < 0) throw new Error(`figure ${k}`); return i + 1; };
const T = (k) => { const i = TAB_ORDER.indexOf(k); if (i < 0) throw new Error(`table ${k}`); return i + 1; };
let figN = 0;
let tabN = 0;

function image(file, name, widthPx) {
  const [w, h] = SIZES[name] || (() => { throw new Error(`no image ${name}`); })();
  return new K.Paragraph({
    alignment: K.AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 40 },
    children: [new ImageRun({
      type: "jpg", data: fs.readFileSync(file), transformation: { width: widthPx, height: Math.round((widthPx * h) / w) },
      altText: { title: name, description: name, name },
    })],
  });
}
// a captured screenshot, framed, with its caption
function shot(key, name, cap, widthPx = CW_PX) {
  if (FIG_ORDER[figN++] !== key) throw new Error(`figure ${key} out of order`);
  return [image(path.join(IMG_DIR, `${name}.jpg`), name, widthPx), caption(`Figure ${F(key)}.  ${cap}`)];
}
function diagram(key, file, cap, widthPx = CW_PX) {
  if (FIG_ORDER[figN++] !== key) throw new Error(`figure ${key} out of order`);
  return [K.figure(file, widthPx, cap), caption(`Figure ${F(key)}.  ${cap}`)];
}
function tab(key, cap) {
  if (TAB_ORDER[tabN++] !== key) throw new Error(`table ${key} out of order`);
  return caption(`Table ${T(key)}.  ${cap}`);
}

// terminal output, verbatim; lines longer than the block are wrapped with a 4-space indent
const WRAP = 90;
function wrap(line) {
  const out = [];
  let rest = line;
  let first = true;
  while (rest.length > (first ? WRAP : WRAP - 4)) {
    const max = first ? WRAP : WRAP - 4;
    let cut = Math.max(rest.lastIndexOf(" ", max), ...[",", "?", "&"].map((c) => rest.lastIndexOf(c, max - 1) + 1));
    if (cut < max * 0.5) cut = max;
    out.push((first ? "" : "    ") + rest.slice(0, cut).trimEnd());
    rest = rest.slice(cut).trimStart();
    first = false;
  }
  out.push((first ? "" : "    ") + rest);
  return out;
}
function terminal(lines, title) {
  const b = { style: K.BorderStyle.SINGLE, size: 4, color: "C8CDD3" };
  const rows = lines.flatMap(wrap);
  const para = (t, o = {}) => new K.Paragraph({ spacing: { after: 0, line: 228 }, children: [new TextRun({ text: t || " ", font: "Courier New", size: 16, ...o })] });
  return new Table({
    width: { size: CW, type: WidthType.DXA }, columnWidths: [CW],
    rows: [new TableRow({ cantSplit: rows.length < 60, children: [new TableCell({
      borders: { top: b, bottom: b, left: b, right: b }, shading: { fill: "F4F5F7", type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: CW, type: WidthType.DXA },
      children: [
        ...(title ? [para(title, { bold: true, color: K.MUTED, font: "Times New Roman", size: 18 })] : []),
        ...rows.map((t) => para(t, t.startsWith("$ ") ? { bold: true, color: "1B4F72" } : {})),
      ],
    })] })],
  });
}
const pct = (v) => `${Math.round(v * 100)}%`;
const sec = (ms) => `${(ms / 1000).toFixed(1)} s`;

const C = []; // document children

// ================================================================== cover
C.push(
  new K.Paragraph({ spacing: { after: 120 }, border: { bottom: { style: K.BorderStyle.SINGLE, size: 18, color: K.NAVY, space: 8 } }, children: [] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { before: 80, after: 80 },
    children: [run("REVIEW – III  ·  SUBMISSION", { bold: true, size: 28, color: K.NAVY, characterSpacing: 60 })] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { after: 200 },
    children: [run("The Working System and its Live Databases", { italics: true, size: 24, color: K.MUTED })] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { before: 300, after: 80 },
    children: [run("GraphRAG-Powered Cyber Threat Intelligence Platform:", { bold: true, size: 36, color: K.NAVY })] }),
  new K.Paragraph({ alignment: K.AlignmentType.CENTER, spacing: { after: 320 },
    children: [run("A Multi-Model NoSQL Approach", { bold: true, size: 36, color: K.NAVY })] }),
  table([3000, 6638], [
    ["Deliverable", "Review – III  (10 marks): final demonstration and innovation"],
    ["Team", K.cell(["Shivansh Sharma (23BCE0254)", "Himali Sharma (23BCE0317)", "Aayush Sinha (23BCE0558)"], 6638, { size: 22 })],
    ["Institution", "VIT Vellore"],
    ["Guide", "Dr. Lydia Jane G"],
    ["Repository", "github.com/Shivansharmaaaa/graphrag"],
    ["Evidence captured", `${CAPTURED}, 20:57–21:15 IST, on the running system`],
  ], { size: 22 }),
  spacer(320),
  callout([
    "**About this document**",
    `Every screenshot here was taken on ${CAPTURED} from the running platform and its four NoSQL databases (Neo4j, MongoDB, Redis and Qdrant). The threat intelligence in them was downloaded the same day from MITRE ATT&CK, abuse.ch Feodo Tracker and Emerging Threats. Screenshots are unedited: they are only scaled and framed. Terminal output is copied verbatim. All ${N_SHOTS} original screenshots and every log are in \`review3/submission/\`.`,
    "The design, the full performance evaluation and the operating guide are in the Final Report, the User Manual and the slides submitted alongside this document (Section 8).",
  ]),
);

// ================================================================== contents
C.push(h1("Contents", { newPage: true }));
C.push(table([7600, 2038], [["Section", "Page"], ...SECTIONS.map((s) => [s, String(tocPages[s] || "")])], { size: 22, center: [1] }));
C.push(spacer(200), p(`Figures are screenshots of the live system unless a caption says otherwise (Figure ${F("arch")} is a diagram). Tables are numbered in order of appearance.`));

// ================================================================== 1 summary
C.push(h1(SECTIONS[0], { newPage: true }));
C.push(p("Cyber threat intelligence (CTI) is polyglot data. Relationships between threat actors, campaigns, malware and infrastructure form a graph. Analyst reports are documents whose fields vary from report to report. Blocked indicators of compromise (IOCs) need millisecond lookups and must expire on time. Analysts ask questions in natural language, which needs semantic search. One database serves all of these poorly."));
C.push(p("The platform gives each workload the NoSQL engine built for it, and adds a GraphRAG layer on top. A question is answered by retrieving evidence from all four stores: similar report passages from Qdrant, multi-hop paths from Neo4j, the full reports from MongoDB and the live blocklist state from Redis. A locally hosted LLM (llama3.2:3b through Ollama) then writes the answer. A groundedness gate removes every sentence that does not cite a graph edge, a passage, a report or an IOC state. Traffic Light Protocol (TLP) clearance is enforced on every read path. Firewalls and EDR tools query a fail-closed enforcement API, and API requests that arrive from a blocklisted address are refused."));
C.push(table([1500, 2300, 3438, 2400], [
  ["Store", "Engine (version)", "What it holds", `Contents on ${CAPTURED}`],
  ["Graph", "Neo4j 5.26.31 Community", "Threat knowledge graph: actors, campaigns, malware, techniques, infrastructure, indicators, reports", "2,223 nodes, 18,491 relationships"],
  ["Document", "MongoDB 7.0.43", "Reports, STIX bundles, users, audit log, ingest log, blocked-request log", "250 reports in 7 collections"],
  ["Key–value", "Redis 7.4.11", "IOC blocklist `ioc:{type}:{value}`, one TTL per key", "565 live IOC keys"],
  ["Vector", "Qdrant 1.13.4", "Report-chunk embeddings (64-dim, cosine) with payload indexes", "796 chunks"],
  ["LLM", "Ollama 0.5.4, llama3.2:3b", "Writes the answer from retrieved evidence; runs locally", "—"],
], { size: 19 }));
C.push(tab("stores", `The four databases and the model, with the data they held when the screenshots were taken. Counts are from the databases' own command-line tools (Section 5).`));
C.push(...diagram("arch", path.join(__dirname, "figures", "r3_architecture.png"), "Implemented architecture (diagram): analyst console and enforcement clients, the FastAPI service, the four NoSQL stores and the local LLM."));
C.push(p(`**Data.** The graph holds 178 threat actors, 843 malware and tools, 227 techniques and 63 campaigns, mostly from MITRE ATT&CK Enterprise v20.0. The blocklist holds the 21 botnet command-and-control (C2) servers on abuse.ch Feodo Tracker (QakBot 16, Emotet 5) and 536 compromised hosts listed by Emerging Threats. All three feeds were downloaded on ${CAPTURED}. Alongside them sit the project's 12 seed analyst reports and one STIX 2.1 bundle that was ingested during the demonstration (Figure ${F("ingest")}).`));

// ================================================================== 2 system
C.push(h1(SECTIONS[1], { newPage: true }));
C.push(h2("2.1  Environment"));
C.push(table([2600, 7038], [
  ["Component", "Version used for this document"],
  ["Host", "macOS (Darwin 25.3), Docker 29.5.2; the four databases run as containers"],
  ["API service", "Python 3.11.7, FastAPI 0.116.1, Uvicorn 0.35.0 on port 8000"],
  ["Database drivers", "neo4j 5.28.1, pymongo 4.13.2, redis-py 6.2.0, qdrant-client 1.14.3"],
  ["Analyst console", "React 18.3.1 and Vite 5.4.11 on port 5173"],
  ["Language model", "Ollama 0.5.4 serving llama3.2:3b on the same machine (no cloud API)"],
  ["Database consoles", "Neo4j Browser (7474), mongo-express (8081), Redis Commander (8082, read-only), Qdrant dashboard (6333)"],
  ["Screenshots", "Google Chrome, headless, 1440 × 900 viewport at 2× scale, driven by `review3/capture_submission.js`"],
], { size: 20 }));
C.push(tab("env", "Software and versions on the demonstration machine."));
C.push(h2("2.2  Starting the system"));
C.push(p("The system was started with the project's own make targets. The API was started with `TRUST_FORWARDED_FOR=true` so that the IP gate can be demonstrated from one machine by sending an `X-Forwarded-For` header (Section 4)."));
C.push(terminal([
  "make infra              # Neo4j, MongoDB, Redis and Qdrant containers",
  "make dbui               # mongo-express and Redis Commander",
  "make import-feeds       # today's MITRE ATT&CK, Feodo Tracker and Emerging Threats data",
  "cd backend && TRUST_FORWARDED_FOR=true ../.venv/bin/uvicorn app.main:app --port 8000",
  "make web                # analyst console on http://localhost:5173",
]));
C.push(h2("2.3  Running containers"));
C.push(terminal(LOG("docker_ps.txt")));
C.push(h2("2.4  Loading today's threat intelligence"));
C.push(p("The importer downloads the three public feeds and writes them into all four stores in one run. ATT&CK groups, software, techniques and campaigns go into Neo4j as nodes and relationships. MongoDB gets one report per group, campaign and feed. Every report is re-chunked and re-embedded into Qdrant. The feed IP addresses go into Redis, each with a TTL that depends on its severity."));
C.push(terminal(LOG("import_feeds.txt").filter((l) => !l.startsWith("[exited"))));
C.push(h2("2.5  Health of the running system"));
C.push(terminal(LOG("api_checks.txt").slice(2, 8)));
C.push(p("This check ran at 20:58, before the STIX ingest of Section 3.7 added 7 nodes, 1 report, 2 chunks and 2 IOCs. `/api/health` reaches every store and the model on each call. The same check drives the green status dots at the bottom left of every console page and the Operations page (Figure " + F("ops") + ")."));

// ================================================================== 3 console
C.push(h1(SECTIONS[2], { newPage: true }));
C.push(p("The analyst console is a React single-page application that talks only to the API. Each user signs in with a role and a TLP clearance, and the API applies that clearance to every request. The screenshots below follow one analyst session (user `analyst`, clearance TLP:AMBER), then a junior analyst (TLP:GREEN) and a CTI lead (TLP:RED)."));
C.push(h2("3.1  Sign-in"));
C.push(...shot("login", "c01_login", "Sign-in page. Four demonstration accounts cover the roles: analyst (AMBER), junior (GREEN), lead (RED, can ingest and publish IOCs) and admin (operator)."));
C.push(h2("3.2  GraphRAG question answering"));
C.push(p(`The question in Figure ${F("qakbot")} is about today's data: which botnet C2 servers host QakBot, and are they still blocked. Entity linking maps "QakBot" to the ATT&CK software node S0650. The graph expansion finds the Feodo Tracker servers that host it, and the IOC check reads each address's live state from Redis. Every sentence in the answer carries citation chips: **G** for a graph edge, **C** for a passage, **D** for a report, **I** for an IOC state. Three uncited sentences were removed by the groundedness gate. This is shown under the answer and can be expanded.`));
C.push(...shot("qakbot", "c02_graphrag_qakbot", "GraphRAG answer about QakBot C2 servers on today's data: llama3.2:3b, citation coverage 86%, 19.7 s end to end, with audit id. Each address is cited to its HOSTS edge (G) and its live blocklist entry (I)."));
C.push(...shot("hops", "c03_graphrag_hops", "Evidence panel, Graph hops tab: the 60 retrieved edges drawn as a graph and listed. Cited hops are bold, for example [G7] 50.16.16.211 –[HOSTS]→ QakBot."));
C.push(...shot("iocs", "c04_graphrag_iocs", "IOC state tab: each indicator in the evidence with its Redis state, remaining TTL and severity. 50.16.16.211 (I4) is live for another 6 d 23 h at critical severity; addresses that are not on the blocklist are marked as such."));
C.push(...shot("chunks", "c05_graphrag_chunks", "Chunks tab: the passages Qdrant returned for the question, with similarity scores and TLP. C1 and C4 come from today's Feodo Tracker report, C2 and C3 from the Emerging Threats report."));
C.push(...shot("latency", "c06_graphrag_latency", "Latency tab: time spent in each step. Retrieval from the four stores takes about half a second in total (Neo4j 342 ms, entity linking 149 ms, Qdrant 25 ms, Redis and MongoDB about 2 ms each). The local model takes 19.1 s."));
C.push(p(`Figure ${F("solarwinds")} asks about an ATT&CK campaign. The answer attributes the SolarWinds Compromise to APT29 and names the malware from USES_MALWARE edges. Three yellow cautions appear because Mimikatz, Cobalt Strike and AdFind are each used by many actors (51, 32 and 12): such tools are weak evidence for attribution. These cautions come from node degree in the graph, not from the model.`));
C.push(...shot("solarwinds", "c07_graphrag_solarwinds", "GraphRAG answer for the SolarWinds Compromise (ATT&CK C0024): APT29 with GoldFinder, Raindrop, TEARDROP and TrailBlazer; hub cautions for commodity tools; 71% coverage, 7.4 s."));
C.push(h2("3.3  Graph explorer"));
C.push(...shot("graph", "c08_graph_sandworm", "Graph explorer: the 1-hop neighbourhood of Sandworm (105 nodes, 104 edges) loaded from Neo4j, with the node's ATT&CK properties and the path-query panel."));
C.push(h2("3.4  Report browser"));
C.push(p("Reports live in MongoDB. Their core fields are shared, but nested fields differ by source: feed metadata, ATT&CK identifiers, or STIX objects. The list shows today's two feed reports first."));
C.push(...shot("reports", "c09_reports", "Report browser: newest first, today's Feodo Tracker and Emerging Threats snapshots followed by ATT&CK campaign and group profiles, each with its TLP and nested-field type."));
C.push(...shot("report", "c10_report_sandworm", "A report opened: the MITRE ATT&CK profile of Sandworm Team (G0034), TLP:CLEAR, read from MongoDB."));
C.push(h2("3.5  Semantic search"));
C.push(...shot("search", "c11_semantic_search", "Semantic search for \"supply-chain compromise of signed software updates\": Qdrant k-NN hits led by the 3CX Supply Chain Attack (C0057), with TLP filters and a 2-D map of the neighbourhood."));
C.push(h2("3.6  IOC blocklist and the IP gate"));
C.push(p(`The blocklist page reads the Redis hot set and refreshes every 5 seconds. Each key's TTL counts down live, and a key that reaches zero leaves the set by itself. The page lists up to 500 live keys; Redis held 565. The API also refuses any request whose client address is live on the blocklist. Figure ${F("blocked")} shows the two requests refused in Section 4, which MongoDB logged with an automatic expiry.`));
C.push(...shot("blocklist", "c12_blocklist", "IOC blocklist: live keys from Redis with type, value, severity, source and remaining TTL, plus the O(1) lookup form."));
C.push(...shot("blocked", "c13_blocked_requests", "Requests blocked by the API: GET /api/reports from QakBot C2 50.16.16.211 (critical) and POST /api/auth/login from 34.204.119.63 (high), both refused with HTTP 403. Times are UTC; each log entry expires on 6 November 2026."));
C.push(h2("3.7  Ingest"));
C.push(p("Signed in as the CTI lead, the sample STIX 2.1 bundle was uploaded. One job writes to the four stores in a fixed order and records each step, so a failed job is retried from the first incomplete step."));
C.push(...shot("ingest", "c19_ingest_stix", "STIX 2.1 ingest by the CTI lead (TLP:RED): job 9d691a270082 succeeded in Neo4j (827 ms), MongoDB (3.3 ms), Qdrant (51.8 ms) and Redis (2.5 ms), creating report rpt-4da6727af1 with its actors, malware and IOCs."));
C.push(h2("3.8  TLP access control"));
C.push(p("A junior analyst has TLP:GREEN clearance. The API filters the report list to what that clearance allows. A direct request for a report above it returns the document's existence but withholds the body."));
C.push(...shot("tlpReports", "c17_tlp_junior_reports", "Report browser as the junior analyst (TLP:GREEN): only reports at or below GREEN are listed."));
C.push(...shot("tlpForbidden", "c18_tlp_junior_forbidden", "The junior analyst opens rpt-001 (TLP:AMBER) by its address: \"TLP:AMBER exceeds your clearance TLP:GREEN\" and the body is withheld."));
C.push(h2("3.9  Audit and replay"));
C.push(...shot("audit", "c14_audit", "Audit log: every GraphRAG answer with its user, mode, citation coverage and latency, stored in MongoDB. Today's two questions are at the top."));
C.push(...shot("replay", "c15_audit_replay", "Replay of the SolarWinds answer against the live stores: all 60 hops, 6 chunks and 3 documents still exist and no IOC state has changed, so the answer can be reproduced."));
C.push(h2("3.10  Operations"));
C.push(p(`The Operations page shows store liveness, latency against the service-level objectives (SLOs), the graph inventory and the cross-store integrity check. Its latency table covers only requests that this API process has served since it started: 2 GraphRAG answers and 30 Redis lookups. With so few samples, the first answer (19.7 s) and the first Redis calls set the high percentiles, and two cells are red. The controlled evaluation in Section 7 sends more requests and meets both SLOs: Redis p99 ${EVAL.latency.redis_get_p99_ms} ms against 5 ms, and GraphRAG p95 ${sec(EVAL.graphrag.p95_ms)} against 15 s.`));
C.push(...shot("ops", "c16_operations", "Operations: all four stores and the model UP; read and enforcement paths healthy; per-channel latency since process start; graph inventory; and all five cross-model integrity rules passing."));

// ================================================================== 4 API
C.push(h1(SECTIONS[3], { newPage: true }));
C.push(p(`The console is one client of the API. The service exposes ${ENDPOINTS} endpoints and documents them with OpenAPI. Analysts authenticate with a JWT. Firewall, EDR and SIEM consumers use an API key, and their path reads only Redis.`));
C.push(...shot("swagger", "a01_swagger", `Interactive API documentation served by the running service (FastAPI, OpenAPI 3.1): ${ENDPOINTS} endpoints for auth, graph, reports, blocklist, enforcement, search, GraphRAG, audit, ingest and admin.`));
C.push(...shot("swaggerHealth", "a02_swagger_health", "GET /api/health executed from the documentation page: HTTP 200 with each store's status, contents and ping time."));
C.push(h2("4.1  Enforcement lookups and the IP gate"));
C.push(p("These commands were run against the live API. Check 1 is the lookup a firewall makes before it lets traffic through to an address. Checks 3 and 4 are the IP gate: the same request is refused when it comes from a C2 server on the blocklist and passes on to authentication when it comes from an ordinary address. If Redis is unreachable, the enforcement endpoint fails closed and answers blocked with HTTP 503."));
C.push(terminal(LOG("api_checks.txt").slice(9)));

// ================================================================== 5 databases
C.push(h1(SECTIONS[4], { newPage: true }));
C.push(p("This section shows the data inside each database, using that database's own console and command-line tool rather than the platform. Every count matches the corresponding view in the console (Section 3)."));
C.push(h2("5.1  Neo4j: the threat knowledge graph"));
C.push(...shot("neoCounts", "n01_neo4j_counts", "Neo4j Browser connected to the local instance: node count per label (Malware 843, Indicator 618, Report 250, Technique 227, ThreatActor 178, Campaign 63, Infrastructure 35, Victim 9)."));
C.push(...shot("neoSandworm", "n02_neo4j_sandworm", "Cypher: Sandworm's malware, campaigns, infrastructure and reports (40 nodes, 39 relationships)."));
C.push(...shot("neoQakbot", "n03_neo4j_qakbot_c2", "Cypher: the 16 Feodo Tracker C2 servers that HOST QakBot and the three threat actors that USE it (20 nodes, 19 relationships)."));
C.push(...shot("neoShared", "n04_neo4j_shared_infra", "Cypher: infrastructure that APT28 shares with other actors, and the malware it hosts. This is the multi-hop query behind the shared-infrastructure question."));
C.push(terminal(LOG("neo4j_cli.txt"), "cypher-shell inside the Neo4j container"));
C.push(h2("5.2  MongoDB: reports and logs"));
C.push(...shot("mongoDb", "m01_mongo_collections", "mongo-express: database cti and its seven collections, with data size."));
C.push(...shot("mongoReports", "m02_mongo_reports", "Collection reports. The documents share a core (title, source, date, TLP, actors, IOCs) but carry different nested fields."));
C.push(...shot("mongoDoc", "m03_mongo_document", "Document feed-feodo: today's abuse.ch Feodo Tracker snapshot, with its 21 C2 addresses in iocs[], the ATT&CK ids of QakBot and Emotet, and the feed URL."));
C.push(...shot("mongoBlocked", "m04_mongo_blocked_requests", "Collection blocked_requests: the two requests refused by the IP gate in Section 4. A TTL index on expires_at deletes each entry after seven days."));
C.push(terminal(LOG("mongo_cli.txt"), "mongosh inside the MongoDB container"));
C.push(h2("5.3  Redis: the IOC blocklist"));
C.push(...shot("redisKey", "r01_redis_key", "Redis Commander (read-only): key ioc:ip:50.16.16.211 with TTL 604,318 s (about 7 days) and its JSON value: critical, QakBot, published by import-feeds from abuse.ch Feodo Tracker."));
C.push(p("The keyspace holds one key per IOC plus the sorted set `ioc:index`, which orders keys by expiry time so the hot set can be listed without scanning. `DBSIZE` is therefore one more than the number of live IOCs."));
C.push(terminal(LOG("redis_cli.txt"), "redis-cli inside the Redis container"));
C.push(h2("5.4  Qdrant: report embeddings"));
C.push(...shot("qdrantCollections", "q01_qdrant_collections", "Qdrant dashboard: collection threat_chunks, status green, 796 points, 64-dimensional vectors with cosine distance."));
C.push(...shot("qdrantPoints", "q02_qdrant_points", "A point and its payload: report_id, title, source, date, chunk index and the chunk text. Search filters on these payload fields."));
C.push(...shot("qdrantMap", "q03_qdrant_visualize", "Qdrant's own 2-D projection of 500 stored vectors. Chunks from similar reports form clusters."));
C.push(terminal(LOG("qdrant_cli.txt"), "Qdrant REST API"));

// ================================================================== 6 trace
C.push(h1(SECTIONS[5], { newPage: true }));
C.push(p("To show that the four databases hold one consistent picture, Table " + T("trace") + " follows a single real indicator through the system. 50.16.16.211 is a QakBot C2 server listed by abuse.ch Feodo Tracker in today's snapshot."));
C.push(table([1700, 5338, 2600], [
  ["Where", "What it holds for 50.16.16.211", "Evidence"],
  ["Redis", "Key `ioc:ip:50.16.16.211`: severity critical, QakBot, source abuse.ch Feodo Tracker, TTL 604,800 s (7 days)", `Figure ${F("redisKey")}, Section 5.3`],
  ["Neo4j", "Infrastructure node 50.16.16.211 –[HOSTS]→ QakBot (S0650), which three threat actors USE", `Figure ${F("neoQakbot")}`],
  ["MongoDB", "In iocs[] and the body of report feed-feodo; two refused requests in blocked_requests, expiring 6 Nov 2026", `Figures ${F("mongoDoc")}, ${F("mongoBlocked")}`],
  ["Qdrant", "Chunks of feed-feodo (7 points with source abuse.ch Feodo Tracker), returned as passages C1 and C4", `Figure ${F("chunks")}, Section 5.4`],
  ["Enforcement API", "`/api/enforce/check` answers blocked, critical; requests from the address get HTTP 403", "Section 4.1"],
  ["GraphRAG", "The answer cites G7 (HOSTS edge) and I4 (live, critical, 6 d 23 h left)", `Figures ${F("qakbot")}–${F("iocs")}`],
  ["Integrity check", "Every report in MongoDB has a Report node and Qdrant chunks; every Redis IOC traces to the graph or a report", `Figure ${F("ops")}, Section 7`],
], { size: 19 }));
C.push(tab("trace", "One indicator traced through the four databases, the API and GraphRAG."));

// ================================================================== 7 tests
C.push(h1(SECTIONS[6], { newPage: true }));
C.push(p(`All test tiers were run on ${CAPTURED} against the same running stack used for the screenshots. The integration tests call the real API, which uses the live stores, and they delete everything they write.`));
const g = EVAL.graphrag;
C.push(table([3600, 3200, 2838], [
  ["Tier", "Command", "Result"],
  ["Unit tests (no database)", "`make test`", "18 passed in 1.46 s"],
  ["Integration tests (live API and stores)", "`make test-integration`", "16 passed in 2.66 s"],
  ["Acceptance evaluation", "`make eval`", `6 questions; gold edges ${pct(g.gold_edge_recall)}, gold reports ${pct(g.gold_report_recall)}`],
  ["Cross-model integrity", "part of `make eval`", `${EVAL.integrity.rules.filter((r) => r.ok).length} / ${EVAL.integrity.rules.length} rules pass`],
], { size: 20 }));
C.push(tab("tests", "Test tiers run on the live system."));
C.push(terminal([...LOG("unit_tests.txt"), "", ...LOG("integration_tests.txt")]));
C.push(h2("7.1  Service-level objectives"));
const L = EVAL.latency;
const ok = (b) => (b ? "met" : "**not met**");
C.push(table([3800, 2600, 1900, 1338], [
  ["Objective", "Measured", "Target", "Status"],
  ["Redis blocklist GET, p99", `${L.redis_get_p99_ms} ms`, "< 5 ms", ok(L.redis_slo_p99_lt_5ms)],
  ["Neo4j traversal, p95 (1 / 2 / 3 hops)", `${L.graph_1hop_p95_ms} / ${L.graph_2hop_p95_ms} / ${L.graph_3hop_p95_ms} ms`, "< 500 ms", ok(L.graph_slo_p95_lt_500ms)],
  ["GraphRAG end to end with the LLM, p95", sec(g.p95_ms), "< 15 s", ok(g.slo_p95_lt_15s)],
  ["Blocklist freshness", "live before expiry, gone after", "TTL honoured", ok(EVAL.blocklist_freshness.ok)],
  ["Cross-model integrity", `${EVAL.integrity.counts.mongodb_reports} reports = ${EVAL.integrity.counts.report_nodes} Report nodes = ${EVAL.integrity.counts.qdrant_reports} reports in Qdrant`, "no violations", ok(EVAL.integrity.ok)],
], { size: 19, center: [3] }));
C.push(tab("slo", "Service-level objectives measured by the evaluation on the live system."));
C.push(p("These checks cover the system at its current size. The Final Report (Section 9) measures the same objectives as the corpus grows from 1× to 200× and under concurrent load."));
C.push(h2("7.2  Acceptance questions"));
C.push(p("Each acceptance question has gold evidence: the graph edges and reports a correct answer must use. The evaluation asks each question through the full GraphRAG pipeline with the local model, and checks that the gold evidence was retrieved and that the answer is grounded."));
C.push(table([4638, 1100, 1100, 1300, 1500], [
  ["Question", "Gold edges", "Gold reports", "Citation coverage", "Latency"],
  ...g.questions.map((q) => [q.question, q.gold_edges_recalled, q.gold_reports_recalled, pct(q.citation_coverage), sec(q.latency_ms)]),
], { size: 18, center: [1, 2, 3, 4] }));
C.push(tab("accept", `Acceptance questions on ${CAPTURED} (llama3.2:3b). Gold edge recall ${g.gold_edge_recall.toFixed(2)}, gold report recall ${g.gold_report_recall.toFixed(2)}, mean citation coverage ${pct(g.mean_citation_coverage)}. The spearphishing question is a similarity question with no gold edges.`));

// ================================================================== 8 contents
C.push(h1(SECTIONS[7], { newPage: true }));
C.push(table([2700, 4338, 2600], [
  ["Item", "File", "Contents"],
  ["This document", "`review3/Review3_Submission_GraphRAG_CTI_Platform.pdf` (and .docx)", "Working system and live databases"],
  ["Final report", "`review3/Final_Report_GraphRAG_CTI_Platform.pdf`", "Design, implementation, testing, performance evaluation"],
  ["User manual", "`review3/User_Manual_GraphRAG_CTI_Platform.pdf`", "Installation, every console page, troubleshooting"],
  ["Presentation", "`review3/Presentation_GraphRAG_CTI_Platform.pptx` (and .pdf)", "Slides with speaker notes"],
  ["Demo runbook", "`review3/DEMO_RUNBOOK.md`", "Live demo script and viva preparation"],
  ["Source code", "`backend/`, `frontend/`, github.com/Shivansharmaaaa/graphrag", "API, GraphRAG, ingest, console, tests"],
  ["Evidence for this document", "`review3/submission/screenshots/`, `review3/submission/logs/`", `${N_SHOTS} original screenshots and the terminal output`],
], { size: 19 }));
C.push(tab("contents", "Review III submission."));
C.push(p("The same platform also runs on the database vendors' hosted services: Neo4j AuraDB, MongoDB Atlas, Redis Cloud and Qdrant Cloud. That deployment and its verification on 27 October 2026 are documented in the Final Report (Sections 6.8 and 8.2). This document uses the local deployment."));
C.push(h2("Conclusion"));
C.push(p(`On ${CAPTURED} the platform ran end to end on four NoSQL databases loaded with that day's public threat intelligence. Its answers cited real graph edges, passages and blocklist states. It refused API requests from a live botnet C2 address and logged them with an automatic expiry. It enforced TLP clearance and recorded each answer so it could be replayed against the stores. Every test tier passed, and every service-level objective was met.`));

// ================================================================== appendix
C.push(h1(SECTIONS[8]));
C.push(p("The screenshots, the logs and this document can be regenerated on any machine with the project installed (`make install`, Google Chrome, LibreOffice and Pillow)."));
C.push(terminal([
  "make infra && make dbui && make import-feeds",
  "# terminal 1: the API, with the IP gate demonstrable from this machine",
  "cd backend && TRUST_FORWARDED_FOR=true ../.venv/bin/uvicorn app.main:app --port 8000",
  "# terminal 2: the analyst console",
  "make web",
  "# all screenshots",
  "node review3/capture_submission.js review3/submission/screenshots",
  "# tests and evaluation; their output goes in review3/submission/logs/",
  "make test; make test-integration; make eval",
  "# this document",
  "node review3/generate_submission.js",
]));

// ================================================================== build
K.publish(K.makeDocument({
  children: C, headerLeft: "Review–III  ·  GraphRAG CTI Platform", headerRight: "Submission: Working System and Live Databases",
  footerLeft: `Captured on the running system, ${CAPTURED}`,
}), OUT, SECTIONS, TOC_CACHE, __filename);
