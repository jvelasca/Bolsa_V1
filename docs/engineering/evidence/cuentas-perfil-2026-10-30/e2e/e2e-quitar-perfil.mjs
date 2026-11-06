/**
 * CUE-E2E — «Quitar perfil desde la UI» (AUD-01) con navegador real.
 *
 * Contra el stack AISLADO del worktree (Vite 5317 → API 8317, `XTB_BRIDGE_AUTOSTART=0`),
 * nunca contra 5173/8000. Recorre el camino completo de la desasignación explícita:
 *
 *  1. alta desechable de cuenta y perfil por API (preparación, no es el caso);
 *  2. asignación por UI (selector + «Aplicar a esta cuenta») → 1 `PUT {"profileId":"…"}`;
 *  3. «Quitar perfil» → aparece la confirmación inline y NO se escribe nada todavía;
 *     captura `e2e-09-confirmacion.png`;
 *  4. «Sí, quitar perfil» → exactamente 1 `PUT {"profileId":null}`, 0 `ensure-defaults`;
 *     la cabecera y la fila pasan a «Sin perfil»; captura `e2e-10-sin-perfil.png`.
 *
 * Escribe `console.txt`, `network.txt` y `setup-quitar-perfil.json` en esta carpeta.
 * El borrado de los datos desechables lo hace el orquestador DESPUÉS de leer la BD
 * (`db-active-profile-null.json`): así la prueba no puede pasar «por casualidad» con
 * la cuenta ya eliminada.
 *
 * Uso (desde `apps/web`, para resolver `@playwright/test`):
 *   node <esta carpeta>/e2e-quitar-perfil.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:5317";
const PW_ROOT = process.env.PW_ROOT ?? process.cwd();
const require = createRequire(path.join(PW_ROOT, "package.json"));
const { chromium, request } = require("@playwright/test");

const stamp = Date.now().toString().slice(-6);
const accountName = `CU-AUD01 quitar perfil ${stamp}`;
const profileName = `CU-AUD01 perfil ${stamp}`;

const consoleLines = [];
const networkLines = [];
const apiCalls = [];
const checks = [];

function log(message) {
  consoleLines.push(message);
  console.log(message);
}

function check(name, ok, detail = "") {
  checks.push({ name, ok, detail });
  log(`${ok ? "OK " : "FALLO"} · ${name}${detail ? ` — ${detail}` : ""}`);
  if (!ok) {
    throw new Error(`Comprobación fallida: ${name}${detail ? ` (${detail})` : ""}`);
  }
}

function write(name, text) {
  fs.writeFileSync(path.join(HERE, name), `${text.trimEnd()}\n`, "utf8");
}

async function main() {
  const api = await request.newContext({ baseURL: BASE, timeout: 30_000 });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      consoleLines.push(`[console.${message.type()}] ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => consoleLines.push(`[pageerror] ${error.message}`));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (!url.pathname.startsWith("/api/")) return;
    apiCalls.push({
      method: req.method(),
      path: url.pathname + url.search,
      body: req.postData() ?? null,
      status: null,
    });
  });
  page.on("response", (res) => {
    const url = new URL(res.url());
    if (!url.pathname.startsWith("/api/")) return;
    const target = [...apiCalls]
      .reverse()
      .find(
        (call) =>
          call.status === null &&
          call.method === res.request().method() &&
          call.path === url.pathname + url.search,
      );
    if (target) target.status = res.status();
    networkLines.push(
      `${res.request().method()} ${url.pathname}${url.search} → ${res.status()}`,
    );
  });

  log(`== CUE-E2E «Quitar perfil» · ${new Date().toISOString()} ==`);
  log(`Base: ${BASE}`);

  // 1. Datos desechables (preparación, no forman parte del recorrido visual).
  const createdAccount = await api.post("/api/accounts", {
    data: { name: accountName, currency: "EUR", initialDeposit: 10_000 },
  });
  const accountBody = await createdAccount.json();
  check(
    "alta de cuenta desechable",
    createdAccount.status() === 200 || createdAccount.status() === 201,
    String(createdAccount.status()),
  );
  const accountId = accountBody.data.id;

  const createdProfile = await api.post("/api/investor-profiles", {
    data: {
      name: profileName,
      horizon: "swing",
      objectives: ["growth"],
      riskTolerance: "moderate",
      experience: "intermediate",
    },
  });
  const profileBody = await createdProfile.json();
  check(
    "alta de perfil desechable",
    createdProfile.status() === 200 || createdProfile.status() === 201,
    String(createdProfile.status()),
  );
  const profileId = profileBody.data.profileId;

  write(
    "setup-quitar-perfil.json",
    JSON.stringify(
      {
        account: { id: accountId, name: accountName },
        profile: { id: profileId, name: profileName },
        createdAt: new Date().toISOString(),
      },
      null,
      2,
    ),
  );

  // 2. Asignación por UI (operación DISTINTA de «Quitar perfil»).
  await page.goto(`${BASE}/accounts?type=all&selected=${accountId}&focus=perfil`, {
    waitUntil: "domcontentloaded",
  });
  await page.locator('[data-testid="account-investor-profile-select"]').waitFor();
  log("§2 selector de perfil visible en Configuración");

  const select = page.locator('[data-testid="account-investor-profile-select"]');
  await select.getByRole("option", { name: profileName }).click();
  const assignResponse = page.waitForResponse(
    (res) =>
      res.request().method() === "PUT" &&
      res.url().includes(`/api/accounts/${accountId}/active-profile`),
  );
  await page.locator('[data-testid="account-profile-apply"]').click();
  const assigned = await assignResponse;
  check("«Aplicar» asigna el perfil", assigned.status() === 200, String(assigned.status()));
  await page
    .locator('[data-testid="account-detail-profile"]')
    .getByText(profileName, { exact: false })
    .first()
    .waitFor();
  log("§2 cabecera con el perfil recién asignado");

  // 3. «Quitar perfil» → confirmación inline, sin escribir.
  const writesBefore = apiCalls.filter((call) => call.method !== "GET").length;
  await page.locator('[data-testid="account-profile-clear"]').click();
  const dialog = page.locator('[data-testid="account-profile-clear-confirm-block"]');
  await dialog.waitFor();
  check(
    "confirmación inline visible (role=alertdialog)",
    (await dialog.getAttribute("role")) === "alertdialog",
  );
  check(
    "pulsar «Quitar perfil» no escribe nada",
    apiCalls.filter((call) => call.method !== "GET").length === writesBefore,
    `${apiCalls.filter((call) => call.method !== "GET").length} escrituras`,
  );
  await page.screenshot({ path: path.join(HERE, "e2e-09-confirmacion.png") });
  log("§3 e2e-09-confirmacion.png");

  // 4. Confirmar → un único PUT con profileId null y estado «Sin perfil».
  const clearResponse = page.waitForResponse(
    (res) =>
      res.request().method() === "PUT" &&
      res.url().includes(`/api/accounts/${accountId}/active-profile`),
  );
  await page.locator('[data-testid="account-profile-clear-confirm"]').click();
  const cleared = await clearResponse;
  const clearPayload = cleared.request().postDataJSON();
  check(
    "un único PUT con profileId null",
    clearPayload.profileId === null,
    JSON.stringify(clearPayload),
  );

  const header = page.locator('[data-testid="account-detail-profile"]');
  await header.getByText("Sin perfil", { exact: true }).waitFor();
  check("cabecera «Sin perfil»", (await header.textContent()).includes("Sin perfil"));

  const row = page.locator(`[data-testid="account-list-profile-${accountId}"]`);
  await row.getByText("Sin perfil", { exact: true }).waitFor();
  check("fila «Sin perfil»", (await row.textContent()).trim() === "Sin perfil");
  check(
    "el botón deja de ofrecerse sin perfil",
    (await page.locator('[data-testid="account-profile-clear"]').count()) === 0,
  );

  await page.screenshot({ path: path.join(HERE, "e2e-10-sin-perfil.png") });
  log("§4 e2e-10-sin-perfil.png");

  // Trazabilidad: cero bootstrap de perfiles y un solo PUT null.
  const ensureDefaults = apiCalls.filter((call) => call.path.includes("ensure-default"));
  const nullPuts = apiCalls.filter(
    (call) => call.method === "PUT" && call.body && JSON.parse(call.body).profileId === null,
  );
  check("0 llamadas a ensure-defaults", ensureDefaults.length === 0, String(ensureDefaults.length));
  check("1 PUT con profileId null", nullPuts.length === 1, String(nullPuts.length));
  check(
    "0 errores de consola",
    consoleLines.every(
      (line) => !line.startsWith("[console.error]") && !line.startsWith("[pageerror]"),
    ),
  );

  log("");
  log(`Cuenta desechable: ${accountId}`);
  log(`Perfil desechable: ${profileId}`);

  const relevant = apiCalls.filter(
    (call) => call.path.includes("/accounts") || call.path.includes("/investor-profiles"),
  );
  const byEndpoint = new Map();
  for (const call of apiCalls) {
    const key = `${call.method} ${call.path.split("?")[0]}`;
    byEndpoint.set(key, (byEndpoint.get(key) ?? 0) + 1);
  }
  write(
    "console.txt",
    [
      "# Instrumentación de consola y comprobaciones — CUE-E2E «Quitar perfil» (AUD-01)",
      `# ${new Date().toISOString()} · ${BASE}`,
      "",
      ...consoleLines,
      "",
      "## Comprobaciones",
      ...checks.map(
        (c) => `- ${c.ok ? "OK" : "FALLO"} · ${c.name}${c.detail ? ` (${c.detail})` : ""}`,
      ),
    ].join("\n"),
  );
  write(
    "network.txt",
    [
      "# Traza de red del navegador — CUE-E2E «Quitar perfil» (AUD-01)",
      `# ${new Date().toISOString()} · ${BASE}`,
      `# Peticiones /api/* observadas: ${apiCalls.length}`,
      "",
      "## Recuento por endpoint",
      ...[...byEndpoint.entries()]
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([key, count]) => `${String(count).padStart(3)} × ${key}`),
      "",
      "## Peticiones de cuentas y perfiles (con cuerpo cuando lo hay)",
      ...relevant.map(
        (call) =>
          `${call.method} ${call.path} → ${call.status ?? "sin respuesta"}` +
          `${call.body ? ` · body=${call.body}` : ""}`,
      ),
      "",
      "## Traza completa",
      ...networkLines,
    ].join("\n"),
  );

  await context.close();
  await browser.close();
  await api.dispose();
}

main().catch((error) => {
  write(
    "console.txt",
    [
      "# Instrumentación de consola — CUE-E2E «Quitar perfil» (AUD-01)",
      "",
      ...consoleLines,
      "",
      `FALLO: ${error.stack ?? error.message}`,
    ].join("\n"),
  );
  console.error(error);
  process.exit(1);
});
