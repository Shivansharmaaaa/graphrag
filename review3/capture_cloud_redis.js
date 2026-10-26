// Redis Cloud in Redis Commander: a read-only container pointed at the hosted database
//   (REDIS_HOST/PORT/PASSWORD from .env.cloud, READ_ONLY=true, port 8092), then
//   node review3/capture_cloud_redis.js review3/screenshots/cloud_redis_key.png
const { chromium } = require("playwright-core");
(async () => {
  const b = await chromium.launch({ channel: "chrome", headless: true });
  const page = await (await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })).newPage();
  await page.goto("http://localhost:8092/");
  await page.waitForTimeout(5000);
  const cli = { click: () => page.mouse.click(300, 884) };
  for (const c of ["DBSIZE", "ZCOUNT ioc:index -inf +inf", "GET ioc:ip:50.16.16.211", "TTL ioc:ip:50.16.16.211", "GET ioc:ip:34.204.119.63", "TTL ioc:ip:34.204.119.63"]) {
    await cli.click();
    await page.keyboard.type(c);
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2500);
  }
  await page.screenshot({ path: process.argv[2] });
  await b.close();
})();
