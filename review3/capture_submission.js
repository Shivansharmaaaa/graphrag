// Screenshots for the Review III submission document: the analyst console, the API and the four
// databases in their own consoles, all on the live local stack with today's feeds loaded.
//   make infra && make dbui && make import-feeds
//   cd backend && TRUST_FORWARDED_FOR=true ../.venv/bin/uvicorn app.main:app --port 8000   # terminal 1
//   make web                                                                                # terminal 2
//   node review3/capture_submission.js review3/submission/screenshots
// ONLY=console,api,neo4j,mongo,redis,qdrant retakes a subset.
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const OUT = path.resolve(process.argv[2] || path.join(__dirname, "submission", "screenshots"));
const BASE = process.env.CTI_URL || "http://localhost:5173";
const API = process.env.CTI_API || "http://localhost:8000";
const STIX = path.join(__dirname, "..", "samples", "stix_apt28_bundle.json");
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD || "ctiplatform"; // lab default from docker-compose.yml
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : null;
const want = (k) => !ONLY || ONLY.includes(k);
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const shot = async (name, opts = {}) => {
    await page.waitForTimeout(opts.wait ?? 1500);
    await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: !!opts.full });
    console.log("shot", name);
  };
  const login = async (user, pw) => {
    await page.goto(`${BASE}/login`);
    const inputs = page.locator("form input");
    await inputs.nth(0).fill(user);
    await inputs.nth(1).fill(pw);
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(`${BASE}/`);
  };
  const logout = async () => {
    await page.getByRole("button", { name: /sign out/i }).click();
    await page.waitForURL(`${BASE}/login`);
  };
  const ask = async (question) => {
    await page.goto(`${BASE}/`);
    await page.locator("textarea").fill(question);
    await page.locator("textarea").press("Enter");
    await page.locator(".card.answer").waitFor({ timeout: 180000 });
  };

  if (want("console")) {
    await page.goto(`${BASE}/login`);
    await shot("c01_login");

    // ---------------------------------------------------------------- analyst (AMBER)
    await login("analyst", "analyst123");
    await ask("Which botnet command-and-control servers host QakBot, and are they still on the blocklist?");
    await shot("c02_graphrag_qakbot", { wait: 4000 });
    await page.locator(".card.evidence").scrollIntoViewIfNeeded();
    await shot("c03_graphrag_hops", { wait: 2500 });
    await page.locator(".card.evidence .tabs button", { hasText: /^IOC state/ }).click();
    await shot("c04_graphrag_iocs");
    await page.locator(".card.evidence .tabs button", { hasText: /^Chunks/ }).click();
    await shot("c05_graphrag_chunks");
    await page.locator(".card.evidence .tabs button", { hasText: /^Latency/ }).click();
    await shot("c06_graphrag_latency");

    await ask("Which groups are attributed to the SolarWinds Compromise campaign and what malware was used?");
    await shot("c07_graphrag_solarwinds", { wait: 4000 });

    await page.goto(`${BASE}/graph`);
    await page.waitForTimeout(3000);
    await page.locator('input[placeholder^="APT28"]').fill("Sandworm");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.locator("ul.list button.link").first().click();
    await shot("c08_graph_sandworm", { wait: 8000 });

    await page.goto(`${BASE}/reports`);
    await shot("c09_reports", { wait: 3000 });
    await page.goto(`${BASE}/reports/attack-G0034`);
    await shot("c10_report_sandworm", { wait: 3000 });

    await page.goto(`${BASE}/search`);
    await page.locator(".chip").first().waitFor();
    await page.getByRole("button", { name: "supply-chain compromise of signed software updates" }).click();
    await shot("c11_semantic_search", { wait: 3000 });

    await page.goto(`${BASE}/blocklist`);
    await shot("c12_blocklist", { wait: 5000 });
    const refused = page.locator(".card", { hasText: "Requests blocked by the API" });
    await refused.scrollIntoViewIfNeeded();
    await page.waitForTimeout(800);
    await refused.screenshot({ path: path.join(OUT, "c13_blocked_requests.png") });
    console.log("shot c13_blocked_requests");

    await page.goto(`${BASE}/audit`);
    await page.waitForTimeout(2000);
    await shot("c14_audit");
    await page.locator("table.tbl tbody tr a").first().click();
    await page.getByRole("button", { name: /Replay against the stores/ }).click();
    await shot("c15_audit_replay", { wait: 3000 });

    await logout();

    // ---------------------------------------------------------------- junior (GREEN): TLP
    await login("junior", "junior123");
    await page.goto(`${BASE}/reports`);
    await shot("c17_tlp_junior_reports", { wait: 3000 });
    await page.goto(`${BASE}/reports/rpt-001`);
    await shot("c18_tlp_junior_forbidden", { wait: 2000 });
    await logout();

    // ---------------------------------------------------------------- lead: STIX ingest
    await login("lead", "lead123");
    await page.goto(`${BASE}/ingest`);
    await page.getByRole("button", { name: /STIX 2.1 bundle/ }).click();
    await page.locator('input[type="file"]').setInputFiles(STIX);
    await page.locator("label", { hasText: /publish/i }).locator('input[type="checkbox"]').first().check();
    await page.locator("form button.primary").click();
    await page.locator("text=neo4j").first().waitFor({ timeout: 60000 });
    await shot("c19_ingest_stix", { wait: 3000, full: true });
    await logout();
  }

  // ---------------------------------------------------------------- operations page + integrity check
  if (want("console") || want("ops")) {
    await login("analyst", "analyst123");
    await page.goto(`${BASE}/ops`);
    await page.waitForTimeout(4000);
    await page.getByRole("button", { name: "Run check" }).click();
    await shot("c16_operations", { wait: 5000, full: true });
    await logout();
  }

  // ---------------------------------------------------------------- the API itself (Swagger UI)
  if (want("api")) {
    await page.goto(`${API}/docs`);
    await page.locator(".opblock").first().waitFor({ timeout: 30000 });
    await shot("a01_swagger", { wait: 2000 });
    const health = page.locator(".opblock", { has: page.locator('.opblock-summary-path[data-path="/api/health"]') });
    await health.locator(".opblock-summary").click();
    await health.getByRole("button", { name: "Try it out" }).click();
    await health.getByRole("button", { name: "Execute" }).click();
    await health.locator(".responses-wrapper .response-col_status").first().waitFor();
    await health.locator(".live-responses-table").scrollIntoViewIfNeeded();
    await shot("a02_swagger_health", { wait: 2000 });
  }

  // ---------------------------------------------------------------- Neo4j Browser (graph)
  if (want("neo4j")) {
    await page.goto("http://localhost:7474/browser/");
    await page.locator('input[type="password"]').waitFor({ timeout: 30000 });
    await page.locator('input[type="password"]').fill(NEO4J_PASSWORD);
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    await page.waitForTimeout(3000);
    const dismiss = page.getByRole("button", { name: "Dismiss" });
    if (await dismiss.count()) await dismiss.first().click();
    const runQuery = async (cypher, wait = 4000) => {
      await page.locator('.cm-content[aria-label="Cypher Editor"]').first().click();
      await page.keyboard.press("Meta+A");
      await page.keyboard.type(cypher);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Run" }).first().click();
      await page.waitForTimeout(wait);
    };
    await runQuery("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC");
    await shot("n01_neo4j_counts", { wait: 1500 });
    await runQuery("MATCH p=(a:ThreatActor {id:'sandworm'})-[:USES|ATTRIBUTED_TO_CAMPAIGN|USES_INFRA|MENTIONED_IN]->() RETURN p");
    await shot("n02_neo4j_sandworm", { wait: 4000 });
    await runQuery("MATCH p=(i:Infrastructure)-[:HOSTS]->(m:Malware {name:'QakBot'}) OPTIONAL MATCH q=(a:ThreatActor)-[:USES]->(m) RETURN p, q");
    await shot("n03_neo4j_qakbot_c2", { wait: 4000 });
    await runQuery("MATCH p=(a:ThreatActor {id:'apt28'})-[:USES_INFRA]->(i:Infrastructure)<-[:USES_INFRA]-(b:ThreatActor) OPTIONAL MATCH h=(i)-[:HOSTS]->(:Malware) RETURN p, h");
    await shot("n04_neo4j_shared_infra", { wait: 4000 });
  }

  // ---------------------------------------------------------------- MongoDB (mongo-express)
  if (want("mongo")) {
    await page.goto("http://localhost:8081/db/cti/");
    await shot("m01_mongo_collections");
    await page.goto("http://localhost:8081/db/cti/reports");
    await shot("m02_mongo_reports");
    await page.goto('http://localhost:8081/db/cti/reports/"feed-feodo"');
    await shot("m03_mongo_document");
    await page.goto("http://localhost:8081/db/cti/blocked_requests");
    await shot("m04_mongo_blocked_requests");
  }

  // ---------------------------------------------------------------- Redis (Redis Commander)
  if (want("redis")) {
    await page.goto("http://localhost:8082/");
    await page.waitForTimeout(2500);
    await page.evaluate(async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      for (let i = 0; i < 3; i++) {
        document.querySelectorAll("li.jstree-closed > .jstree-ocl").forEach((e) => e.click());
        await sleep(1500);
      }
      [...document.querySelectorAll(".jstree-anchor")].find((a) => a.textContent.trim().endsWith("50.16.16.211"))?.click();
    });
    await shot("r01_redis_key", { wait: 3000 });
  }

  // ---------------------------------------------------------------- Qdrant dashboard (vectors)
  if (want("qdrant")) {
    await page.goto("http://localhost:6333/dashboard#/collections");
    await shot("q01_qdrant_collections", { wait: 2500 });
    await page.goto("http://localhost:6333/dashboard#/collections/threat_chunks");
    await shot("q02_qdrant_points", { wait: 3000 });
    await page.goto("http://localhost:6333/dashboard#/collections/threat_chunks/visualize");
    await page.waitForTimeout(2500);
    await page.getByText("RUN", { exact: true }).first().click();
    await shot("q03_qdrant_visualize", { wait: 6000 });
  }

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
