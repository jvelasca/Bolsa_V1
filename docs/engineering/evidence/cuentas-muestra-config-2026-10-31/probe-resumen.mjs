import path from "node:path";
import { createRequire } from "node:module";
const require = createRequire(path.join(process.cwd(), "package.json"));
const { chromium, request } = require("@playwright/test");

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const api = await request.newContext({ baseURL: BASE });
const created = await api.post("/api/accounts", {
  data: { name: "CU-REV probe ui", currency: "EUR", initialDeposit: 10000 },
});
const { data } = await created.json();
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();
page.on("console", (m) => console.log("console", m.type(), m.text()));
page.on("pageerror", (e) => console.log("pageerror", e.message));
page.on("request", (r) => {
  if (r.url().includes("/api/accounts")) console.log("REQ", r.method(), r.url());
});
page.on("response", (r) => {
  if (r.url().includes("/api/accounts")) console.log("RES", r.status(), r.url());
});
page.on("requestfailed", (r) => console.log("FAILED", r.url(), r.failure()?.errorText));
await page.goto(`${BASE}/accounts?type=all&selected=${data.id}`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(10000);
console.log("--- SECTION ---");
console.log(await page.locator("section").innerText());
console.log("--- direct fetch ---");
console.log(
  JSON.stringify(
    await page.evaluate(
      async (id) => (await fetch(`/api/accounts/${id}/summary`)).json(),
      data.id,
    ),
  ).slice(0, 400),
);
await page.screenshot({ path: "probe-resumen.png", fullPage: true });
await browser.close();
await api.post(`/api/accounts/${data.id}/close`);
await api.delete(`/api/accounts/${data.id}`);
await api.dispose();
