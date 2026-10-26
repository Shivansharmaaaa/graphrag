// Console screenshots with the API running on the hosted databases and the real feeds loaded.
//   make cloud-import-feeds && TRUST_FORWARDED_FOR=true make cloud-api   # terminal 1
//   make web                                                             # terminal 2
//   node review3/capture_cloud.js review3/screenshots
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const OUT = path.resolve(process.argv[2] || path.join(__dirname, "screenshots"));
const BASE = process.env.CTI_URL || "http://localhost:5173";
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : null; // e.g. ONLY=blocklist to retake one group
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
  const ask = async (question, name) => {
    await page.goto(`${BASE}/`);
    await page.locator("textarea").fill(question);
    await page.locator("textarea").press("Enter");
    await page.locator(".card.answer").waitFor({ timeout: 180000 });
    await shot(name, { wait: 4000 });
  };

  await page.goto(`${BASE}/login`);
  const inputs = page.locator("form input");
  await inputs.nth(0).fill("analyst");
  await inputs.nth(1).fill("analyst123");
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(`${BASE}/`);

  if (want("ops")) {
    await page.goto(`${BASE}/ops`);
    await shot("cloud_operations", { wait: 6000, full: true });
  }

  if (want("graphrag")) {
    await ask("Which groups are attributed to the SolarWinds Compromise campaign and what malware was used?", "cloud_graphrag_solarwinds");
    await ask("Which botnet command-and-control servers host QakBot, and are they still on the blocklist?", "cloud_graphrag_qakbot");
  }

  if (want("graph")) {
    await page.goto(`${BASE}/graph`);
    await page.waitForTimeout(3000);
    await page.locator('input[placeholder^="APT28"]').fill("Sandworm");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.locator("ul.list button.link").first().click();
    await shot("cloud_graph_sandworm", { wait: 8000 });
  }

  if (want("reports")) {
    await page.goto(`${BASE}/reports`);
    await shot("cloud_reports", { wait: 4000 });
    await page.goto(`${BASE}/reports/attack-G0034`);
    await shot("cloud_report_attack", { wait: 3000 });
  }

  if (want("blocklist")) {
    await page.goto(`${BASE}/blocklist`);
    await shot("cloud_blocklist", { wait: 5000 });
    // the refusal log sits below 500+ live entries: capture that card on its own
    const card = page.locator(".card", { hasText: "Requests blocked by the API" });
    await card.scrollIntoViewIfNeeded();
    await page.waitForTimeout(800);
    await card.screenshot({ path: path.join(OUT, "cloud_blocked_requests.png") });
    console.log("shot cloud_blocked_requests");
  }

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
