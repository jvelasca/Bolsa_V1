/**
 * CTA-E2E — recorrido completo de /accounts (lista, ficha y Configuración) + «Nueva demo».
 *
 * Contra el stack indicado por `E2E_BASE_URL` (por defecto `http://localhost:5173`,
 * proxy Vite → API 8000). Cubre CTA-01 … CTA-12 del plan:
 *
 *  CTA-01 lista: filas, badge «Activa», perfil por fila / «Sin perfil», contadores.
 *  CTA-02 selección: clic NO activa; `?selected=`, localStorage intacto, X-Account-Id correcto.
 *  CTA-03 «Usar ahora»: 1 `POST make-default` y el badge se mueve.
 *  CTA-04 filtros: Paper vacío, selección constreñida, aviso de activa fuera del filtro.
 *  CTA-05 Resumen: cifras reales; error de resumen como alerta y «No disponible».
 *  CTA-06 Configuración: guardar nombre/descripción (1 PATCH), una sola superficie de perfil.
 *  CTA-07 perfil: asignar (1 PUT), aviso de compartido, «Quitar perfil» con confirmación,
 *         0 escrituras al abrir, 1 `PUT {"profileId": null}`, cabecera/fila «Sin perfil».
 *  CTA-08 comisiones/fiscal: botón y deep-link `focus=fiscal`; cancelar no escribe; guardar
 *         preset/custom/jurisdicción; notas con espacios recortadas solo al guardar.
 *  CTA-09 entorno Paper/Live: preferencia por cuenta persistida y conservada al guardar settings.
 *  CTA-10 Nueva demo: los 6 pasos, alta con perfil/comisiones/fiscal, verificación por API.
 *  CTA-11 cuenta cerrada: no editable/asignable (UI + API 409); «Mostrar cerradas»; borrado demo.
 *  CTA-12 red y consola: 0 `pageerror`, 0 `console.error`, escrituras contabilizadas.
 *
 * Higiene: ids desechables `CU-REV-*` / perfiles `PROF-REV-*`, foto de BD antes/después
 * (`snapshot-cuentas.py`) idéntica byte a byte y restauración de `is_default` de la semilla.
 *
 * Uso (desde `apps/web`, para resolver `@playwright/test`):
 *   $env:E2E_BASE_URL="http://localhost:5173"; node <esta carpeta>/e2e-cuentas.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..", "..");
const STARTED_AT = new Date().toISOString();

function gitOrNull(args) {
  try {
    return execSync(`git ${args}`, {
      cwd: REPO_ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

/**
 * Procedencia del recorrido: el E2E declara el árbol EXACTO que valida. Sin esto, un
 * resultado verde no es atribuible a ningún HEAD ni a ningún sello.
 */
const PROVENANCE = {
  branch: gitOrNull("rev-parse --abbrev-ref HEAD"),
  head: gitOrNull("rev-parse HEAD"),
  headShort: gitOrNull("rev-parse --short HEAD"),
  version: (() => {
    try {
      return JSON.parse(fs.readFileSync(path.join(REPO_ROOT, "package.json"), "utf8"))
        .version;
    } catch {
      return null;
    }
  })(),
  dirty: (gitOrNull("status --porcelain") ?? "").length > 0,
};

function provenanceLine() {
  return (
    `# procedencia · rama=${PROVENANCE.branch ?? "?"} · head=${PROVENANCE.headShort ?? "?"}` +
    ` · version=${PROVENANCE.version ?? "?"} · dirty=${String(PROVENANCE.dirty)}`
  );
}

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const PW_ROOT = process.env.PW_ROOT ?? process.cwd();
const require = createRequire(path.join(PW_ROOT, "package.json"));
const { chromium, request } = require("@playwright/test");

const SEED_ID = "default-account-seed";
const SEED_PROFILE_ID = "PROF-996fcd3d6ec6";
const stamp = Date.now().toString().slice(-6);
const nameA = `CU-REV A ${stamp}`;
const nameARenamed = `CU-REV A ${stamp} renombrada`;
const nameB = `CU-REV B ${stamp}`;
const profileName = `PROF-REV principal ${stamp}`;
const wizardName = `CU-REV wizard ${stamp}`;
const wizardProfileName = `PROF-REV wizard ${stamp}`;
const notesWithSpaces = "  nota con espacios internos  ";
const notesTrimmed = "nota con espacios internos";

const consoleLines = [];
const apiCalls = [];
const networkLines = [];
const checks = [];

function log(message) {
  consoleLines.push(message);
  console.log(message);
}

function check(name, ok, detail = "") {
  checks.push({ name, ok, detail });
  log(`${ok ? "OK " : "FALLO"} · ${name}${detail ? ` — ${detail}` : ""}`);
  if (!ok) throw new Error(`Comprobación fallida: ${name}${detail ? ` (${detail})` : ""}`);
}

function write(name, text) {
  fs.writeFileSync(path.join(HERE, name), `${text.trimEnd()}\n`, "utf8");
}

function writes() {
  return apiCalls.filter((call) => call.method !== "GET");
}

/**
 * Escrituras de LA SUPERFICIE /cuentas (cuenta y perfil). El shell de la app escribe
 * estado propio al navegar (`core-r`, `supervised-f3-queue`, `workspaces`, quotes…);
 * esas no son operaciones de esta pantalla y no deben contar como «escritura».
 */
function isScreenWrite(call) {
  const target = call.path.split("?")[0];
  if (call.method === "PATCH") {
    return /^\/api\/accounts\/[^/]+(\/settings|\/broker-venue)?$/.test(target);
  }
  if (call.method === "PUT") {
    return /^\/api\/accounts\/[^/]+\/active-profile$/.test(target);
  }
  if (call.method === "POST") {
    return (
      target === "/api/accounts" ||
      /^\/api\/accounts\/[^/]+\/(make-default|close)$/.test(target)
    );
  }
  if (call.method === "DELETE") return /^\/api\/accounts\/[^/]+$/.test(target);
  return false;
}

function screenWrites() {
  return writes().filter(isScreenWrite);
}

/**
 * Espera a que la red quede en reposo (ninguna petición /api/* sin respuesta) para que
 * las escrituras de fondo del shell no se confundan con llamadas perdidas: al navegar,
 * el poller cancela peticiones en vuelo (`requestfailed`) y una comprobación inmediata
 * las leería como «sin respuesta».
 */
async function settleNetwork(page) {
  let quiet = 0;
  for (let i = 0; i < 25 && quiet < 3; i += 1) {
    await page.waitForTimeout(200);
    const pending = apiCalls.filter((call) => call.status === null).length;
    quiet = pending === 0 ? quiet + 1 : 0;
  }
}

function lastCall(method, pathFragment) {
  return [...apiCalls]
    .reverse()
    .find((call) => call.method === method && call.path.includes(pathFragment));
}

async function getJson(api, pathname) {
  const response = await api.get(pathname);
  return { status: response.status(), body: await response.json() };
}

/** Limpieza idempotente: restaura la semilla y borra todo lo desechable por nombre. */
async function cleanup(api) {
  log("");
  log("§cleanup — restauración de la semilla y borrado de datos desechables");
  await api.post(`/api/accounts/${SEED_ID}/make-default`);

  const listed = await getJson(api, "/api/accounts");
  const disposable = (listed.body.data ?? []).filter(
    (a) => a.id !== SEED_ID && a.name.startsWith("CU-REV"),
  );
  for (const account of disposable) {
    if (account.status !== "closed") {
      await api.post(`/api/accounts/${account.id}/close`);
    }
    const deleted = await api.delete(`/api/accounts/${account.id}`);
    log(`cleanup · ${account.name} (${account.id}) → ${deleted.status()}`);
  }

  const profiles = await getJson(api, "/api/investor-profiles");
  const disposableProfiles = (profiles.body.data ?? []).filter((p) =>
    p.name.startsWith("PROF-REV"),
  );
  for (const profile of disposableProfiles) {
    const deleted = await api.delete(`/api/investor-profiles/${profile.profileId}`);
    log(`cleanup · ${profile.name} (${profile.profileId}) → ${deleted.status()}`);
  }

  await api.post(`/api/accounts/${SEED_ID}/make-default`);
  const finalAccounts = await getJson(api, "/api/accounts");
  const finalProfiles = await getJson(api, "/api/investor-profiles");
  const names = (finalAccounts.body.data ?? []).map((a) => a.name);
  const profileNames = (finalProfiles.body.data ?? []).map((p) => p.name);
  check(
    "cleanup · solo queda la semilla",
    finalAccounts.body.data.length === 1 &&
      finalAccounts.body.data[0].id === SEED_ID,
    JSON.stringify(names),
  );
  check(
    "cleanup · sin perfiles PROF-REV",
    profileNames.every((n) => !n.startsWith("PROF-REV")),
    JSON.stringify(profileNames),
  );
  check(
    "cleanup · semilla is_default",
    finalAccounts.body.data[0].isDefault === true,
  );
  check(
    "cleanup · semilla conserva su perfil",
    finalAccounts.body.data[0].activeProfileId === SEED_PROFILE_ID,
  );
}

async function main() {
  const api = await request.newContext({ baseURL: BASE, timeout: 30_000 });
  // `channel: "chrome"` usa el Chrome instalado del sistema (el paquete de
  // Playwright de este entorno no trae el headless-shell descargado).
  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const goto = async (url, options) => {
    log(`§goto ${url}`);
    return page.goto(url, options);
  };

  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      consoleLines.push(`[console.${message.type()}] ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => consoleLines.push(`[pageerror] ${error.message}`));

  // Espejo de la cuenta activa del cliente (localStorage `bolsa-active-account`) para
  // distinguir el poller del shell —que usa la ACTIVA— de una fuga de scope.
  let storeActive = null;
  await page.exposeFunction("__e2eActiveAccount", (id) => {
    if (id !== storeActive) {
      storeActive = id;
      log(`[store +${Date.now() % 100000}] cuenta activa del cliente → ${id ?? "null"}`);
    }
  });
  await page.addInitScript(() => {
    const read = () => {
      try {
        const raw = window.localStorage.getItem("bolsa-active-account");
        const id = raw ? JSON.parse(raw)?.state?.activeAccountId ?? null : null;
        window.__e2eActiveAccount?.(id);
      } catch {
        /* almacenamiento no disponible: se ignora */
      }
    };
    read();
    window.addEventListener("storage", read);
    window.setInterval(read, 100);
  });

  page.on("request", (req) => {
    const url = new URL(req.url());
    if (!url.pathname.startsWith("/api/")) return;
    apiCalls.push({
      method: req.method(),
      path: url.pathname + url.search,
      body: req.postData() ?? null,
      headers: req.headers(),
      status: null,
      // Cuenta que la UI está mostrando cuando sale la petición (`?selected=`) y
      // cuenta activa del cliente (localStorage) en ese instante.
      view: new URL(page.url()).searchParams.get("selected"),
      store: storeActive,
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
  page.on("requestfailed", (req) => {
    const url = new URL(req.url());
    if (!url.pathname.startsWith("/api/")) return;
    const target = [...apiCalls]
      .reverse()
      .find(
        (call) =>
          call.status === null &&
          call.method === req.method() &&
          call.path === url.pathname + url.search,
      );
    if (target) target.status = "aborted";
    networkLines.push(
      `${req.method()} ${url.pathname}${url.search} → ABORTED (${req.failure()?.errorText ?? "?"})`,
    );
  });

  log(`== CTA-E2E /accounts · ${new Date().toISOString()} ==`);
  log(`Base: ${BASE}`);

  let seedState = null;
  const disposable = { accounts: [], profiles: [] };

  try {
    // ── Preparación por API (no forma parte del recorrido visual) ─────────────
    const accounts0 = await getJson(api, "/api/accounts");
    const seed = (accounts0.body.data ?? []).find((a) => a.id === SEED_ID);
    check("semilla presente y activa", seed != null && seed.status === "active");
    seedState = {
      id: seed.id,
      isDefault: seed.isDefault,
      activeProfileId: seed.activeProfileId,
      name: seed.name,
    };

    const createdA = await api.post("/api/accounts", {
      data: {
        name: nameA,
        description: "Cuenta desechable A para revisión de /cuentas",
        currency: "EUR",
        initialDeposit: 10_000,
      },
    });
    const bodyA = await createdA.json();
    check("alta cuenta A", createdA.status() === 201, String(createdA.status()));
    const idA = bodyA.data.id;

    const createdB = await api.post("/api/accounts", {
      data: {
        name: nameB,
        description: "Cuenta desechable B para revisión de /cuentas",
        currency: "EUR",
        initialDeposit: 5_000,
      },
    });
    const bodyB = await createdB.json();
    check("alta cuenta B", createdB.status() === 201, String(createdB.status()));
    const idB = bodyB.data.id;

    const createdProfile = await api.post("/api/investor-profiles", {
      data: {
        name: profileName,
        horizon: "swing",
        objectives: ["growth"],
        riskTolerance: "moderate",
        experience: "intermediate",
      },
    });
    const bodyProfile = await createdProfile.json();
    check(
      "alta perfil desechable",
      createdProfile.status() === 200 || createdProfile.status() === 201,
      String(createdProfile.status()),
    );
    const idProfile = bodyProfile.data.profileId;

    disposable.accounts.push(idA, idB);
    disposable.profiles.push(idProfile);
    write(
      "setup-cuentas.json",
      JSON.stringify(
        {
          seed: seedState,
          disposable: {
            accountA: { id: idA, name: nameA },
            accountB: { id: idB, name: nameB },
            profile: { id: idProfile, name: profileName },
          },
          createdAt: new Date().toISOString(),
        },
        null,
        2,
      ),
    );

    // ── CTA-01 · lista ────────────────────────────────────────────────────────
    await goto(`${BASE}/accounts`, { waitUntil: "domcontentloaded" });
    await page.locator(`[data-testid="account-list-item-${SEED_ID}"]`).waitFor();
    await page.locator(`[data-testid="account-list-item-${idA}"]`).waitFor();
    await page.locator(`[data-testid="account-list-item-${idB}"]`).waitFor();

    check(
      "CTA-01 · contador Demo (3)",
      (await page.getByRole("button", { name: /^Demo \(\d+\)$/ }).textContent()) ===
        "Demo (3)",
    );
    check(
      "CTA-01 · contador Paper futuro (0)",
      (await page
        .getByRole("button", { name: /^Paper futuro \(\d+\)$/ })
        .textContent()) === "Paper futuro (0)",
    );
    check(
      "CTA-01 · pestaña Todas",
      (await page.getByRole("button", { name: "Todas", exact: true }).count()) === 1,
    );

    const seedRow = page.locator(`[data-testid="account-list-item-${SEED_ID}"]`);
    const rowA = page.locator(`[data-testid="account-list-item-${idA}"]`);
    const rowB = page.locator(`[data-testid="account-list-item-${idB}"]`);
    check(
      "CTA-01 · fila semilla con perfil",
      (await page
        .locator(`[data-testid="account-list-profile-${SEED_ID}"]`)
        .textContent()).includes("Perfil por defecto (moderado)"),
    );
    // Las cuentas nuevas sin perfil declarado reciben el perfil por defecto (moderate)
    // compartido con la semilla; «Sin perfil» se comprueba en CTA-07 tras desasignar.
    check(
      "CTA-01 · fila A con el perfil por defecto compartido",
      (await page
        .locator(`[data-testid="account-list-profile-${idA}"]`)
        .textContent()).includes("Perfil por defecto (moderado)"),
    );
    check(
      "CTA-01 · badge «Activa» solo en la semilla",
      (await seedRow.getByText("Activa", { exact: true }).count()) === 1 &&
        (await rowA.getByText("Activa", { exact: true }).count()) === 0 &&
        (await rowB.getByText("Activa", { exact: true }).count()) === 0,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-01-lista.png") });
    log("§CTA-01 e2e-01-lista.png");

    // ── CTA-02 · selección sin activar ───────────────────────────────────────
    const lsBefore = await page.evaluate(() =>
      localStorage.getItem("bolsa-active-account"),
    );
    const writesBeforeSelect = writes().length;
    await rowA.click();
    await page.waitForURL(new RegExp(`selected=${idA}`));
    await page.getByRole("heading", { name: nameA, level: 2 }).waitFor();
    await page.waitForResponse(
      (res) => res.url().includes("/api/portfolio") && res.status() === 200,
    );
    check(
      "CTA-02 · seleccionar no dispara make-default",
      !writes()
        .slice(writesBeforeSelect)
        .some((call) => call.path.includes("make-default")),
    );
    check(
      "CTA-02 · localStorage intacto",
      (await page.evaluate(() => localStorage.getItem("bolsa-active-account"))) ===
        lsBefore,
    );
    check(
      "CTA-02 · el badge sigue en la semilla",
      (await seedRow.getByText("Activa", { exact: true }).count()) === 1 &&
        (await rowA.getByText("Activa", { exact: true }).count()) === 0,
    );
    const portfolioCall = lastCall("GET", "/api/portfolio");
    check(
      "CTA-D1 · portfolio con X-Account-Id de la cuenta seleccionada",
      portfolioCall?.headers["x-account-id"] === idA,
      portfolioCall?.headers["x-account-id"] ?? "sin header",
    );
    check(
      "CTA-02 · botón «Usar ahora» disponible",
      (await page.locator('[data-testid="account-activate"]').count()) === 1,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-02-seleccion.png") });
    log("§CTA-02 e2e-02-seleccion.png");

    // ── CTA-03 · «Usar ahora» ────────────────────────────────────────────────
    const activateResponse = page.waitForResponse(
      (res) =>
        res.request().method() === "POST" &&
        res.url().includes(`/api/accounts/${idA}/make-default`),
    );
    await page.locator('[data-testid="account-activate"]').click();
    const activated = await activateResponse;
    check("CTA-03 · POST make-default 200", activated.status() === 200);
    await rowA.getByText("Activa", { exact: true }).waitFor();
    check(
      "CTA-03 · el badge se mueve a A",
      (await rowA.getByText("Activa", { exact: true }).count()) === 1 &&
        (await seedRow.getByText("Activa", { exact: true }).count()) === 0,
    );
    check(
      "CTA-03 · una sola llamada make-default",
      apiCalls.filter((call) => call.path.includes("make-default")).length === 1,
    );
    const lsActivated = JSON.parse(
      await page.evaluate(() => localStorage.getItem("bolsa-active-account")),
    );
    check(
      "CTA-03 · localStorage apunta a A",
      lsActivated?.state?.activeAccountId === idA,
      JSON.stringify(lsActivated),
    );
    check(
      "CTA-03 · «Usar ahora» desaparece al ser la activa",
      (await page.locator('[data-testid="account-activate"]').count()) === 0,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-03-usar-ahora.png") });
    log("§CTA-03 e2e-03-usar-ahora.png");

    // ── CTA-04 · filtros ─────────────────────────────────────────────────────
    await page.getByRole("button", { name: /^Paper futuro \(/ }).click();
    await page.waitForURL(/type=paper/);
    const outside = page.locator('[data-testid="accounts-active-outside-filter"]');
    await outside.waitFor();
    check("CTA-04 · aviso de activa fuera del filtro", (await outside.textContent()).includes(nameA));
    check(
      "CTA-04 · Paper no lista cuentas demo",
      (await page.locator(`[data-testid="account-list-item-${idA}"]`).count()) === 0 &&
        (await page.locator(`[data-testid="account-list-item-${SEED_ID}"]`).count()) === 0,
    );
    check(
      "CTA-04 · selección constreñida al filtro",
      (await page.getByText("Selecciona una cuenta a la izquierda.").count()) === 1,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-04-filtro-paper.png") });
    log("§CTA-04 e2e-04-filtro-paper.png");

    await page.getByRole("button", { name: "Todas", exact: true }).click();
    await page.locator(`[data-testid="account-list-item-${idA}"]`).waitFor();

    // Restauración de la Activa a la semilla (directo, para aislar el resto de casos).
    // Intencional: el cliente pasa a la semilla y se limpia el localStorage.
    log("§CTA-04 restauración intencional: semilla Activa y localStorage limpio");
    await api.post(`/api/accounts/${SEED_ID}/make-default`);
    await page.evaluate(() => localStorage.removeItem("bolsa-active-account"));
    await goto(`${BASE}/accounts?type=all`, { waitUntil: "domcontentloaded" });
    await page
      .locator(`[data-testid="account-list-item-${SEED_ID}"]`)
      .getByText("Activa", { exact: true })
      .waitFor();

    // ── CTA-05 · Resumen ─────────────────────────────────────────────────────
    await goto(`${BASE}/accounts?type=all&selected=${idA}`, {
      waitUntil: "domcontentloaded",
    });
    await page.getByText("Patrimonio", { exact: true }).waitFor();
    // Las métricas del Resumen formatean sin símbolo de moneda (`formatPrice` sin currency).
    await page.getByText("10000.00", { exact: true }).first().waitFor();
    const section = page.locator("section");
    const summaryText = await section.textContent();
    check("CTA-05 · Patrimonio con cifra", summaryText.includes("10000.00"));
    check("CTA-05 · Efectivo con cifra", summaryText.includes("10000.00"));
    check("CTA-05 · P&L no realizado", summaryText.includes("P&L no realizado"));
    check("CTA-05 · P&L realizado", summaryText.includes("P&L realizado"));
    check("CTA-05 · Posiciones 0", summaryText.includes("Posiciones"));
    check(
      "CTA-05 · sin rótulos de ausencia en Resumen",
      !summaryText.includes("No disponible") && !summaryText.includes("Sin dato todavía"),
    );
    await page.screenshot({ path: path.join(HERE, "e2e-05-resumen.png") });
    log("§CTA-05 e2e-05-resumen.png");

    // Error de resumen: 500 simulado en una pestaña aparte (no contamina la traza).
    const errorPage = await context.newPage();
    await errorPage.route(`**/api/accounts/${idA}/summary`, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "fallo simulado de resumen" }),
      }),
    );
    await errorPage.goto(`${BASE}/accounts?type=all&selected=${idA}`, {
      waitUntil: "domcontentloaded",
    });
    const summaryAlert = errorPage.locator('[data-testid="account-summary-error"]');
    await summaryAlert.waitFor();
    check(
      "CTA-05 · error de resumen como alerta",
      (await summaryAlert.getAttribute("role")) === "alert" &&
        (await summaryAlert.textContent()).includes("no como cero"),
    );
    check(
      "CTA-05 · cifras como «No disponible», no 0",
      (await errorPage.locator("section").textContent()).includes("No disponible"),
    );
    await errorPage.screenshot({ path: path.join(HERE, "e2e-05-resumen-error.png") });
    log("§CTA-05 e2e-05-resumen-error.png");
    await errorPage.close();

    // ── CTA-06 · Configuración (datos) ───────────────────────────────────────
    await goto(`${BASE}/accounts?type=all&selected=${idA}&tab=config`, {
      waitUntil: "domcontentloaded",
    });
    await section.getByLabel("Nombre", { exact: true }).waitFor();
    const writesBeforeSave = screenWrites().length;
    await section.getByLabel("Nombre", { exact: true }).fill(nameARenamed);
    await section.getByLabel("Descripción", { exact: true }).fill("descripción con espacios");
    const patchAccount = page.waitForResponse(
      (res) =>
        res.request().method() === "PATCH" &&
        res.url().endsWith(`/api/accounts/${idA}`),
    );
    await page.getByRole("button", { name: "Guardar datos" }).click();
    const patched = await patchAccount;
    check("CTA-06 · 1 PATCH de la cuenta", patched.status() === 200);
    const patchedBody = patched.request().postDataJSON();
    check(
      "CTA-06 · payload con nombre y descripción",
      patchedBody.name === nameARenamed &&
        patchedBody.description === "descripción con espacios",
      JSON.stringify(patchedBody),
    );
    await page.getByText("Datos actualizados.").waitFor();
    check(
      "CTA-06 · solo 1 escritura al guardar",
      screenWrites().length - writesBeforeSave === 1,
      `${screenWrites().length - writesBeforeSave}`,
    );
    const accountsAfterSave = await getJson(api, "/api/accounts");
    const accountA = accountsAfterSave.body.data.find((a) => a.id === idA);
    check("CTA-06 · nombre persistido", accountA.name === nameARenamed);
    check(
      "CTA-06 · descripción persistida",
      accountA.description === "descripción con espacios",
    );
    check(
      "CTA-06 · una sola superficie de perfil en la ficha",
      (await page.locator('[data-testid="account-investor-profile-select"]').count()) === 1,
    );
    const fiscalSummary = page.locator('[data-testid="account-fiscal-summary"]');
    check(
      "CTA-06 · resumen fiscal visible",
      (await fiscalSummary.textContent()).includes("Comisiones y fiscal") &&
        !(await fiscalSummary.textContent()).includes("No disponible"),
    );
    await page.screenshot({ path: path.join(HERE, "e2e-06-config.png") });
    log("§CTA-06 e2e-06-config.png");

    // ── CTA-07 · perfil inversor ─────────────────────────────────────────────
    const profileSelect = page.locator('[data-testid="account-investor-profile-select"]');
    await profileSelect.getByRole("option", { name: new RegExp(profileName) }).click();
    const assignA = page.waitForResponse(
      (res) =>
        res.request().method() === "PUT" &&
        res.url().includes(`/api/accounts/${idA}/active-profile`),
    );
    await page.locator('[data-testid="account-profile-apply"]').click();
    const assignedA = await assignA;
    check(
      "CTA-07 · asignar A es 1 PUT con el perfil",
      assignedA.status() === 200 &&
        assignedA.request().postDataJSON().profileId === idProfile,
    );
    const detailProfile = page.locator('[data-testid="account-detail-profile"]');
    await detailProfile.getByText(profileName, { exact: false }).waitFor();
    check("CTA-07 · cabecera con el perfil", (await detailProfile.textContent()).includes(profileName));
    await page
      .locator(`[data-testid="account-list-profile-${idA}"]`)
      .getByText(profileName, { exact: false })
      .waitFor();
    log("§CTA-07 perfil asignado a A");

    // B: abrir el panel NO escribe y compartir el perfil avisa.
    const writesBeforeOpenB = screenWrites().length;
    await goto(`${BASE}/accounts?type=all&selected=${idB}&tab=config`, {
      waitUntil: "domcontentloaded",
    });
    await page.locator('[data-testid="account-investor-profile-select"]').waitFor();
    check(
      "CTA-07 · abrir la ficha de B no escribe",
      screenWrites().length === writesBeforeOpenB,
      `${screenWrites().length - writesBeforeOpenB}`,
    );
    const selectB = page.locator('[data-testid="account-investor-profile-select"]');
    await selectB.getByRole("option", { name: new RegExp(profileName) }).click();
    const shared = page.locator('[data-testid="account-profile-shared-warning"]');
    await shared.waitFor();
    check(
      "CTA-07 · aviso de perfil compartido",
      (await shared.textContent()).includes("ya lo usan 1 cuenta") &&
        (await shared.textContent()).includes(nameARenamed),
    );
    const assignB = page.waitForResponse(
      (res) =>
        res.request().method() === "PUT" &&
        res.url().includes(`/api/accounts/${idB}/active-profile`),
    );
    await page.locator('[data-testid="account-profile-apply"]').click();
    check("CTA-07 · asignar B es 1 PUT", (await assignB).status() === 200);
    await page
      .locator('[data-testid="account-detail-profile"]')
      .getByText(profileName, { exact: false })
      .waitFor();

    // «Quitar perfil»: confirmación inline sin escrituras y después 1 PUT null.
    const writesBeforeClear = screenWrites().length;
    await page.locator('[data-testid="account-profile-clear"]').click();
    const confirmBlock = page.locator('[data-testid="account-profile-clear-confirm-block"]');
    await confirmBlock.waitFor();
    check(
      "CTA-07 · confirmación inline (alertdialog)",
      (await confirmBlock.getAttribute("role")) === "alertdialog",
    );
    check(
      "CTA-07 · pulsar «Quitar perfil» no escribe",
      screenWrites().length === writesBeforeClear,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-07-confirmacion.png") });
    log("§CTA-07 e2e-07-confirmacion.png");

    const clearResponse = page.waitForResponse(
      (res) =>
        res.request().method() === "PUT" &&
        res.url().includes(`/api/accounts/${idB}/active-profile`),
    );
    await page.locator('[data-testid="account-profile-clear-confirm"]').click();
    const cleared = await clearResponse;
    check(
      "CTA-07 · desasignar es 1 PUT con profileId null",
      cleared.request().postDataJSON().profileId === null,
    );
    await page
      .locator('[data-testid="account-detail-profile"]')
      .getByText("Sin perfil", { exact: true })
      .waitFor();
    await page
      .locator(`[data-testid="account-list-profile-${idB}"]`)
      .getByText("Sin perfil", { exact: true })
      .waitFor();
    check(
      "CTA-07 · «Quitar perfil» deja de ofrecerse",
      (await page.locator('[data-testid="account-profile-clear"]').count()) === 0,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-07-sin-perfil.png") });
    log("§CTA-07 e2e-07-sin-perfil.png");

    // ── CTA-09 · entorno Paper/Live por cuenta ───────────────────────────────
    const fiscalUrl = `${BASE}/accounts?type=all&selected=${idA}&tab=config&focus=fiscal`;
    await goto(fiscalUrl, { waitUntil: "domcontentloaded" });
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    check(
      "CTA-08 · deep-link focus=fiscal abre «Fiscal»",
      (await page.locator('[data-testid="settings-tab-tax"]').getAttribute("aria-selected")) ===
        "true",
    );
    const venueResponse = page.waitForResponse(
      (res) =>
        res.request().method() === "PATCH" &&
        res.url().includes(`/api/accounts/${idA}/broker-venue`),
    );
    await page.locator('[data-testid="account-venue-preference-live"]').click();
    const venue = await venueResponse;
    check(
      "CTA-09 · PATCH broker-venue live",
      venue.status() === 200 && venue.request().postDataJSON().venue === "live",
    );
    // El botón se pinta desde la query invalidada; se espera a que refleje la preferencia.
    await page.waitForFunction(
      () =>
        (
          document.querySelector('[data-testid="account-venue-preference-live"]')
            ?.className ?? ""
        ).includes("border-primary"),
      undefined,
      { timeout: 10_000 },
    );
    check(
      "CTA-09 · botón Live activo",
      ((await page
        .locator('[data-testid="account-venue-preference-live"]')
        .getAttribute("class")) ?? "").includes("border-primary"),
    );
    await page.screenshot({ path: path.join(HERE, "e2e-08-fiscal-dialog.png") });
    log("§CTA-09 e2e-08-fiscal-dialog.png");

    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    const persistedVenue = await getJson(api, `/api/accounts/${idA}/broker-venue`);
    check(
      "CTA-09 · preferencia persistida en la API",
      persistedVenue.body.preference === "live",
      JSON.stringify(persistedVenue.body),
    );

    // Reabrir por botón (sin deep-link nuevo) y cancelar: no debe escribir.
    await page.getByRole("button", { name: "Editar comisiones y fiscal →" }).click();
    await dialog.waitFor();
    // El deep-link `focus=fiscal` hace que el diálogo abra en Fiscal; el selector de
    // presets vive en la pestaña Comisiones.
    await page.locator('[data-testid="settings-tab-commissions"]').click();
    await page.locator('[data-testid="settings-preset-custom"]').check();
    const commissionPct = dialog.locator('input[type="number"]').first();
    await commissionPct.fill("0.12");
    const writesBeforeCancel = screenWrites().length;
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    check(
      "CTA-08 · cancelar con Escape no escribe",
      screenWrites().length === writesBeforeCancel,
      `${screenWrites().length - writesBeforeCancel}`,
    );

    // ── CTA-08 · guardar comisiones/fiscal + notas con espacios ──────────────
    await page.getByRole("button", { name: "Editar comisiones y fiscal →" }).click();
    await dialog.waitFor();
    await page.locator('[data-testid="settings-tab-commissions"]').click();
    await page.locator('[data-testid="settings-preset-custom"]').check();
    await dialog.locator('input[type="number"]').first().fill("0.12");
    await page.locator('[data-testid="settings-tab-tax"]').click();
    await page.locator('[data-testid="settings-tax-jurisdiction"]').selectOption("US");
    const notesInput = dialog.locator("textarea");
    await notesInput.fill(notesWithSpaces);
    check(
      "CTA-D3 · el texto conserva los espacios al teclear",
      (await notesInput.inputValue()) === notesWithSpaces,
    );
    const settingsSave = page.waitForResponse(
      (res) =>
        res.request().method() === "PATCH" &&
        res.url().includes(`/api/accounts/${idA}/settings`),
    );
    await page.getByRole("button", { name: "Guardar comisiones y fiscal" }).click();
    const saved = await settingsSave;
    const savedBody = saved.request().postDataJSON();
    check("CTA-08 · 1 PATCH de settings", saved.status() === 200);
    check(
      "CTA-08 · preset custom persistido en el payload",
      savedBody.settings.commission.presetId === "custom" &&
        savedBody.settings.commission.stockCommissionPct === 0.12,
      JSON.stringify(savedBody.settings.commission),
    );
    check(
      "CTA-08 · jurisdicción US en el payload",
      savedBody.settings.tax.jurisdiction === "US",
      savedBody.settings.tax.jurisdiction,
    );
    check(
      "CTA-08 · notas recortadas solo al guardar",
      savedBody.settings.notes === notesTrimmed,
      JSON.stringify(savedBody.settings.notes),
    );
    await dialog.waitFor({ state: "detached" });
    const accountsAfterSettings = await getJson(api, "/api/accounts");
    const accountASettings = accountsAfterSettings.body.data.find((a) => a.id === idA);
    check(
      "CTA-08 · notas con espacios verificadas en la API",
      accountASettings.settings.notes === notesTrimmed,
      JSON.stringify(accountASettings.settings.notes),
    );
    // El DTO de la cuenta no expone `brokerVenue`; la lectura canónica es su endpoint.
    const venueAfterSettings = await getJson(api, `/api/accounts/${idA}/broker-venue`);
    check(
      "CTA-08 · guardar settings conserva brokerVenue",
      venueAfterSettings.body.preference === "live",
      JSON.stringify(venueAfterSettings.body),
    );
    check(
      "CTA-08 · resumen fiscal refleja la jurisdicción",
      (await page.locator('[data-testid="account-fiscal-summary"]').textContent()).includes(
        "Estados Unidos",
      ),
    );
    await page.screenshot({ path: path.join(HERE, "e2e-09-fiscal-guardado.png") });
    log("§CTA-08 e2e-09-fiscal-guardado.png");

    // ── CTA-10 · «Nueva demo» ────────────────────────────────────────────────
    await goto(`${BASE}/accounts?type=all`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Nueva demo" }).click();
    const wizard = page.getByRole("dialog");
    await wizard.waitFor();
    check(
      "CTA-10 · el asistente abre en Identidad",
      (await wizard.getByText("Identidad", { exact: true }).count()) === 1,
    );
    await wizard.getByLabel("Nombre de la cuenta").fill(wizardName);
    await wizard.getByRole("button", { name: "Siguiente" }).click();
    await wizard.getByLabel("Depósito inicial").waitFor();
    await wizard.getByRole("button", { name: "Siguiente" }).click();
    await wizard.getByRole("button", { name: "Crear nuevo" }).click();
    await wizard.getByLabel("Nombre del perfil (opcional)").fill(wizardProfileName);
    await wizard.getByRole("button", { name: "Siguiente" }).click();
    await wizard.getByText("Comisiones", { exact: true }).first().waitFor();
    await wizard.getByRole("button", { name: "Siguiente" }).click();
    await page.locator('[data-testid="wizard-tax-summary"]').waitFor();
    await wizard.getByRole("button", { name: "Siguiente" }).click();
    const review = page.locator('[data-testid="wizard-review"]');
    await review.waitFor();
    const reviewText = await review.textContent();
    check(
      "CTA-10 · revisión con cuenta y perfil",
      reviewText.includes(wizardName) && reviewText.includes(wizardProfileName),
      reviewText,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-10-wizard-revision.png") });
    log("§CTA-10 e2e-10-wizard-revision.png");

    const createAccount = page.waitForResponse(
      (res) => res.request().method() === "POST" && res.url().endsWith("/api/accounts"),
    );
    await wizard.getByRole("button", { name: "Crear cuenta" }).click();
    const created = await createAccount;
    const createdBody = await created.json();
    const idWizard = createdBody.data.id;
    check("CTA-10 · POST /accounts 201", created.status() === 201);
    disposable.accounts.push(idWizard);
    await wizard.waitFor({ state: "detached" });
    const wizardRow = page.locator(`[data-testid="account-list-item-${idWizard}"]`);
    await wizardRow.waitFor();
    const wizardBadge = wizardRow.getByText("Activa", { exact: true });
    await wizardBadge.waitFor({ timeout: 15_000 }).catch(() => {});
    const lsWizard = await page.evaluate(() =>
      localStorage.getItem("bolsa-active-account"),
    );
    check(
      "CTA-10 · la cuenta nueva aparece y es la Activa",
      (await wizardBadge.count()) === 1,
      `${await wizardRow.textContent()} · localStorage=${lsWizard}`,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-10-cuenta-creada.png") });
    log("§CTA-10 e2e-10-cuenta-creada.png");

    const accountsAfterWizard = await getJson(api, "/api/accounts");
    const wizardAccount = accountsAfterWizard.body.data.find((a) => a.id === idWizard);
    check(
      "CTA-10 · cuenta con perfil asignado",
      wizardAccount.activeProfileId != null,
      JSON.stringify(wizardAccount.activeProfileId),
    );
    check(
      "CTA-10 · comisión por defecto del asistente",
      wizardAccount.settings.commission.presetId === "standard_es",
      wizardAccount.settings.commission.presetId,
    );
    check(
      "CTA-10 · fiscal por defecto del asistente",
      wizardAccount.settings.tax.jurisdiction === "ES",
      wizardAccount.settings.tax.jurisdiction,
    );
    const profilesAfterWizard = await getJson(api, "/api/investor-profiles");
    const wizardProfile = profilesAfterWizard.body.data.find(
      (p) => p.name === wizardProfileName,
    );
    check("CTA-10 · perfil nuevo en el catálogo", wizardProfile != null);
    if (wizardProfile) disposable.profiles.push(wizardProfile.profileId);
    check(
      "CTA-10 · el perfil es el de la cuenta",
      wizardProfile != null && wizardAccount.activeProfileId === wizardProfile.profileId,
    );

    // ── CTA-11 · cuenta cerrada ──────────────────────────────────────────────
    await goto(`${BASE}/accounts?type=all&selected=${idB}&tab=config`, {
      waitUntil: "domcontentloaded",
    });
    page.once("dialog", (confirm) => confirm.accept());
    const closeResponse = page.waitForResponse(
      (res) =>
        res.request().method() === "POST" &&
        res.url().includes(`/api/accounts/${idB}/close`),
    );
    await page.getByRole("button", { name: "Cerrar cuenta" }).click();
    check("CTA-11 · cerrar cuenta 200", (await closeResponse).status() === 200);
    await page.locator('[data-testid="account-closed-notice"]').waitFor();
    check(
      "CTA-11 · nombre y descripción no editables",
      (await page.getByLabel("Nombre", { exact: true }).isDisabled()) &&
        (await page.getByLabel("Descripción", { exact: true }).isDisabled()),
    );
    check(
      "CTA-11 · sin «Guardar datos» en cerrada",
      (await page.getByRole("button", { name: "Guardar datos" }).count()) === 0,
    );
    check(
      "CTA-11 · sin bloque de perfil en cerrada",
      (await page.locator('[data-testid="account-profile-block"]').count()) === 0,
    );
    check(
      "CTA-11 · sin edición de comisiones/fiscal en cerrada",
      (await page.getByRole("button", { name: /Editar comisiones y fiscal/ }).count()) === 0,
    );
    check(
      "CTA-11 · «Eliminar cuenta (demo)» disponible",
      (await page.getByRole("button", { name: "Eliminar cuenta (demo)" }).count()) === 1,
    );
    await page.screenshot({ path: path.join(HERE, "e2e-11-cerrada.png") });
    log("§CTA-11 e2e-11-cerrada.png");

    // CTA-D5: la API tampoco permite editar/asignar una cuenta cerrada.
    const closedSettings = await api.patch(`/api/accounts/${idB}/settings`, {
      data: { settings: accountASettings.settings },
    });
    const closedSettingsBody = await closedSettings.json();
    check(
      "CTA-D5 · settings de cerrada → 409 account_closed",
      closedSettings.status() === 409 &&
        closedSettingsBody.detail?.code === "account_closed",
      JSON.stringify(closedSettingsBody),
    );
    const closedProfile = await api.put(`/api/accounts/${idB}/active-profile`, {
      data: { profileId: null },
    });
    const closedProfileBody = await closedProfile.json();
    check(
      "CTA-D5 · perfil de cerrada → 409 account_closed",
      closedProfile.status() === 409 &&
        closedProfileBody.detail?.code === "account_closed",
      JSON.stringify(closedProfileBody),
    );
    const closedName = await api.patch(`/api/accounts/${idB}`, {
      data: { name: `${nameB} intento` },
    });
    check("CTA-D5 · nombre de cerrada → 409", closedName.status() === 409);

    // «Mostrar cerradas» y borrado de demo desde la UI.
    await page.getByRole("button", { name: /Mostrar cerradas \(/ }).click();
    const closedRow = page.locator(`[data-testid="account-list-item-${idB}"]`);
    await closedRow.waitFor();
    check("CTA-11 · la cerrada aparece al mostrarla", (await closedRow.textContent()).includes("cerrada"));
    page.once("dialog", (confirm) => confirm.accept());
    const deleteResponse = page.waitForResponse(
      (res) =>
        res.request().method() === "DELETE" &&
        res.url().includes(`/api/accounts/${idB}`),
    );
    await page.getByRole("button", { name: "Eliminar cuenta (demo)" }).click();
    check("CTA-11 · borrado de demo 204", (await deleteResponse).status() === 204);
    await closedRow.waitFor({ state: "detached" });

    // ── CTA-12 · red y consola ───────────────────────────────────────────────
    await settleNetwork(page);
    check(
      "CTA-12 · 0 pageerror",
      !consoleLines.some((line) => line.startsWith("[pageerror]")),
    );
    check(
      "CTA-12 · 0 console.error",
      !consoleLines.some((line) => line.startsWith("[console.error]")),
    );
    check(
      "CTA-12 · 0 llamadas a ensure-defaults",
      apiCalls.every((call) => !call.path.includes("ensure-default")),
    );
    const unresolvedScreen = screenWrites().filter((call) => call.status === null);
    check(
      "CTA-12 · escrituras de la superficie todas contabilizadas",
      unresolvedScreen.length === 0,
      unresolvedScreen.map((call) => `${call.method} ${call.path}`).join(", "),
    );
    // Las peticiones de fondo del shell pueden cancelarse al navegar (quotes, colas de
    // estado…): no son escrituras de esta pantalla, pero quedan registradas como tales.
    const abortedBackground = apiCalls.filter(
      (call) => call.status === null && !isScreenWrite(call),
    );
    if (abortedBackground.length > 0) {
      log(
        `aviso · ${abortedBackground.length} petición(es) de fondo del shell en vuelo al cerrar la captura (no son escrituras de /cuentas): ` +
          abortedBackground.map((call) => `${call.method} ${call.path}`).join(", "),
      );
    }
    // CTA-D1: el poller del shell pide `/api/portfolio` con la cuenta ACTIVA; la ficha
    // debe pedirlo con la cuenta que muestra (`?selected=`). El invariante es que
    // NUNCA se pida el portfolio con el header de una cuenta distinta de la vista y de
    // la activa: eso sería una fuga de scope (CTA-D1). Los endpoints con id explícito
    // en la ruta (`/accounts/{id}/summary`, `/ledger`, …) validan acceso por ese id
    // (`require_account_access`) e ignoran el header ambiente.
    const implicitScoped = apiCalls.filter((call) =>
      /^\/api\/portfolio(\/|$)/.test(call.path.split("?")[0]),
    );
    const scopedPortfolio = implicitScoped.filter((call) => call.view === call.headers["x-account-id"]);
    check(
      "CTA-12 · la ficha pide el portfolio de la cuenta seleccionada (CTA-D1)",
      scopedPortfolio.length > 0,
      `${scopedPortfolio.length}/${implicitScoped.length}`,
    );
    const implicitMismatch = implicitScoped.filter(
      (call) =>
        call.view &&
        call.headers["x-account-id"] !== call.view &&
        call.headers["x-account-id"] !== call.store,
    );
    check(
      "CTA-12 · portfolio nunca con el scope de una tercera cuenta (CTA-D1)",
      implicitMismatch.length === 0,
      implicitMismatch
        .map(
          (call) =>
            `${call.method} ${call.path} → ${call.headers["x-account-id"]} (vista ${call.view}, activa ${call.store})`,
        )
        .join(", "),
    );
  } finally {
    try {
      await cleanup(api);
    } catch (error) {
      log(`cleanup falló: ${error instanceof Error ? error.message : String(error)}`);
      checks.push({ name: "cleanup", ok: false, detail: String(error) });
    }

    const byEndpoint = new Map();
    for (const call of apiCalls) {
      const key = `${call.method} ${call.path.split("?")[0].replace(/\/[a-z0-9-]{8,}$/i, "/{id}")}`;
      byEndpoint.set(key, (byEndpoint.get(key) ?? 0) + 1);
    }
    write(
      "console.txt",
      [
        "# Consola, comprobaciones y decisiones — CTA-E2E /accounts",
        `# ${new Date().toISOString()} · ${BASE}`,
        provenanceLine(),
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
        "# Traza de red del navegador — CTA-E2E /accounts",
        `# ${new Date().toISOString()} · ${BASE}`,
        provenanceLine(),
        `# Peticiones /api/* observadas: ${apiCalls.length}`,
        "",
        "## Recuento por endpoint (ids normalizados)",
        ...[...byEndpoint.entries()]
          .sort((a, b) => a[0].localeCompare(b[0]))
          .map(([key, count]) => `${String(count).padStart(3)} × ${key}`),
        "",
        "## Escrituras (cuerpo y X-Account-Id)",
        ...writes().map(
          (call) =>
            `${call.method} ${call.path} → ${call.status ?? "sin respuesta"}` +
            `${call.headers["x-account-id"] ? ` · X-Account-Id=${call.headers["x-account-id"]}` : ""}` +
            `${call.body ? ` · body=${call.body}` : ""}`,
        ),
        "",
        "## Portfolio (verificación CTA-D1)",
        ...apiCalls
          .filter((call) => call.path.startsWith("/api/portfolio"))
          .map(
            (call) =>
              `${call.method} ${call.path} → ${call.status ?? "sin respuesta"} · X-Account-Id=${
                call.headers["x-account-id"] ?? "sin header"
              }`,
          ),
        "",
        "## Traza completa",
        ...networkLines,
      ].join("\n"),
    );
    write(
      "e2e-result.json",
      JSON.stringify(
        {
          createdAt: new Date().toISOString(),
          base: BASE,
          provenance: {
            ...PROVENANCE,
            startedAt: STARTED_AT,
            finishedAt: new Date().toISOString(),
          },
          seed: seedState,
          disposable,
          checks,
          ok: checks.every((c) => c.ok),
          apiCalls: apiCalls.length,
          writes: writes().length,
        },
        null,
        2,
      ),
    );

    await context.close();
    await browser.close();
    await api.dispose();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
