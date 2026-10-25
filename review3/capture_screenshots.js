// Console screenshots for the report, user manual and slides.
//   npm i playwright-core   (uses the installed Google Chrome; no browser download)
//   node review3/capture_screenshots.js review3/screenshots
// Needs the demo stack on http://localhost:5173 with a fresh seed (make seed) and Ollama running.
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const OUT = path.resolve(process.argv[2] || path.join(__dirname, "screenshots"));
const BASE = process.env.CTI_URL || "http://localhost:5173";
const STIX = path.join(__dirname, "..", "samples", "stix_apt28_bundle.json");
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const shot = async (name, opts = {}) => {
    await page.waitForTimeout(opts.wait ?? 1200);
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

  await page.goto(`${BASE}/login`);
  await shot("login");

  // ---------------------------------------------------------------- analyst (AMBER)
  await login("analyst", "analyst123");
  await page.getByRole("button", { name: /What destructive campaigns is Sandworm/ }).click();
  await page.locator(".card.answer").waitFor({ timeout: 120000 });
  await shot("graphrag_answer", { wait: 4000 });
  await page.locator(".card.evidence").scrollIntoViewIfNeeded();
  await shot("graphrag_evidence", { wait: 2500 });
  await page.getByRole("button", { name: /^Chunks/ }).click();
  await shot("graphrag_chunks");
  await page.getByRole("button", { name: /^IOC state/ }).click();
  await shot("graphrag_iocs");
  await page.getByRole("button", { name: /^Latency/ }).click();
  await shot("graphrag_latency");

  await page.goto(`${BASE}/`);
  await page.getByRole("button", { name: /Why is Mimikatz a weak attribution signal/ }).click();
  await page.locator(".card.answer").waitFor({ timeout: 120000 });
  await shot("graphrag_mimikatz", { wait: 3000 });

  await page.goto(`${BASE}/graph`);
  await shot("graph_explorer", { wait: 5000 });

  await page.goto(`${BASE}/reports`);
  await shot("reports");
  await page.goto(`${BASE}/reports/rpt-002`);
  await shot("report_detail");

  await page.goto(`${BASE}/blocklist`);
  await shot("blocklist", { wait: 2000 });

  await page.goto(`${BASE}/search`);
  await page.getByRole("button", { name: "supply-chain compromise of signed software updates" }).click();
  await shot("semantic_search", { wait: 2000 });

  await page.goto(`${BASE}/audit`);
  await page.locator("table.tbl tbody tr a").first().click();
  await page.getByRole("button", { name: /Replay against the stores/ }).click();
  await shot("audit_replay", { wait: 2500 });

  await page.goto(`${BASE}/ops`);
  await shot("operations", { wait: 2500, full: true });
  await logout();

  // ---------------------------------------------------------------- junior (GREEN): TLP
  await login("junior", "junior123");
  await page.goto(`${BASE}/reports`);
  await shot("tlp_junior_reports");
  await page.goto(`${BASE}/reports/rpt-001`);
  await shot("tlp_junior_forbidden");
  await logout();

  // ---------------------------------------------------------------- lead: STIX ingest
  await login("lead", "lead123");
  await page.goto(`${BASE}/ingest`);
  await page.getByRole("button", { name: /STIX 2.1 bundle/ }).click();
  await page.locator('input[type="file"]').setInputFiles(STIX);
  await page.locator("label", { hasText: /publish/i }).locator('input[type="checkbox"]').first().check();
  await page.locator("form button.primary").click();
  await page.locator("text=neo4j").first().waitFor({ timeout: 60000 });
  await shot("ingest_stix", { wait: 2500, full: true });

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
