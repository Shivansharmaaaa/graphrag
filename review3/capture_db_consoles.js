// Screenshots of the four NoSQL databases in their own consoles (not the CTI app).
//   make dbui                                   # MongoDB and Redis consoles (Neo4j, Qdrant have their own)
//   node review3/capture_db_consoles.js review3/screenshots
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const OUT = path.resolve(process.argv[2] || path.join(__dirname, "screenshots"));
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD || "ctiplatform"; // lab default from docker-compose.yml
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const shot = async (name, wait = 1500) => {
    await page.waitForTimeout(wait);
    await page.screenshot({ path: path.join(OUT, `${name}.png`) });
    console.log("shot", name);
  };

  // ---------------------------------------------------------------- Neo4j Browser (graph)
  await page.goto("http://localhost:7474/browser/");
  await page.locator('input[type="password"]').waitFor({ timeout: 30000 });
  await page.locator('input[type="password"]').fill(NEO4J_PASSWORD);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.waitForTimeout(3000);
  const dismiss = page.getByRole("button", { name: "Dismiss" });
  if (await dismiss.count()) await dismiss.first().click();
  const runQuery = async (cypher) => {
    await page.locator('.cm-content[aria-label="Cypher Editor"]').first().click();
    await page.keyboard.press("Meta+A");
    await page.keyboard.type(cypher);
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Run" }).first().click();
    await page.waitForTimeout(4000);
  };
  await runQuery("MATCH (n)-[r]->(m) WHERE NOT n:Report AND NOT m:Report RETURN n, r, m LIMIT 160");
  await shot("db_neo4j_graph", 4000);
  await runQuery("MATCH p=(a:ThreatActor {id:'apt28'})-[:USES_INFRA]->(i:Infrastructure)<-[:USES_INFRA]-(b:ThreatActor) OPTIONAL MATCH h=(i)-[:HOSTS]->(:Malware) RETURN p, h");
  await shot("db_neo4j_shared_infra", 4000);

  // ---------------------------------------------------------------- MongoDB (mongo-express)
  await page.goto("http://localhost:8081/db/cti/");
  await shot("db_mongo_collections");
  await page.goto("http://localhost:8081/db/cti/reports");
  await shot("db_mongo_reports");
  await page.goto('http://localhost:8081/db/cti/reports/"rpt-002"');
  await shot("db_mongo_document");

  // ---------------------------------------------------------------- Redis (Redis Commander)
  await page.goto("http://localhost:8082/");
  await page.waitForTimeout(2500);
  await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    for (let i = 0; i < 3; i++) {
      document.querySelectorAll("li.jstree-closed > .jstree-ocl").forEach((e) => e.click());
      await sleep(1200);
    }
    [...document.querySelectorAll(".jstree-anchor")].find((a) => a.textContent.includes("185.86.77.12"))?.click();
  });
  await shot("db_redis_key", 2500);

  // ---------------------------------------------------------------- Qdrant dashboard (vectors)
  await page.goto("http://localhost:6333/dashboard#/collections");
  await shot("db_qdrant_collections", 2500);
  await page.goto("http://localhost:6333/dashboard#/collections/threat_chunks");
  await shot("db_qdrant_points", 2500);
  await page.goto("http://localhost:6333/dashboard#/collections/threat_chunks/visualize");
  await page.waitForTimeout(2500);
  await page.getByText("RUN", { exact: true }).first().click();
  await shot("db_qdrant_visualize", 5000);

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
