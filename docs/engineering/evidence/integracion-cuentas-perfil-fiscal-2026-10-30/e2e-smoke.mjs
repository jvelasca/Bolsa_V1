/**
 * Smoke E2E de la integración Cuentas/Perfil inversor + fiscal (2026-10-30).
 *
 * Corre contra el stack AISLADO del worktree de integración:
 *   Vite  http://localhost:5318  →  API  http://127.0.0.1:8318  →  BD bolsa_v1_integracion
 *
 * Comprueba las tres cosas que la fusión tenía que dejar ciertas:
 *  1. la ficha muestra el perfil asignado en la cabecera y el botón con el copy del
 *     candidato («Editar comisiones y fiscal»);
 *  2. `?tab=config&focus=fiscal` abre el diálogo directamente en la pestaña Fiscal y
 *     el diálogo es el del candidato («Comisiones y fiscal de la cuenta»);
 *  3. dentro del panel ya NO hay ninguna superficie de asignación de perfil: la única
 *     asignación vive en la ficha.
 *
 * Uso (desde `apps/web`, para resolver `@playwright/test`):
 *   node <esta carpeta>/e2e-smoke.mjs
 *
 * Escribe `smoke-01-ficha.png`, `smoke-02-fiscal.png` y `smoke-console.txt` aquí.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = path.dirname(fileURLToPath(import.meta.url));
const requireFromWeb = createRequire(path.resolve("package.json"));
const { chromium } = requireFromWeb("@playwright/test");

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:5318";
const ACCOUNT = process.env.E2E_ACCOUNT_ID ?? "default-account-seed";
const PROFILE_NAME = process.env.E2E_PROFILE_NAME ?? "Perfil por defecto (moderado)";

const checks = [];
const consoleLines = [];
function check(name, ok, detail = "") {
  checks.push({ name, ok, detail });
  const mark = ok ? "OK  " : "FAIL";
  console.log(`${mark} ${name}${detail ? ` — ${detail}` : ""}`);
}
function note(kind, text) {
  consoleLines.push(`[${kind}] ${text}`);
  console.log(`[${kind}] ${text}`);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("console", (msg) => {
  if (msg.type() === "error" || msg.type() === "warning") {
    note(msg.type(), msg.text());
  }
});
page.on("pageerror", (err) => note("pageerror", err.message));

try {
  // ── 1. Ficha de la cuenta, pestaña Configuración ─────────────────────────────
  await page.goto(`${BASE}/accounts?selected=${ACCOUNT}&tab=config`, { waitUntil: "domcontentloaded" });
  const profileBlock = page.getByTestId("account-profile-block");
  await profileBlock.waitFor({ state: "visible", timeout: 20000 });
  const blockText = (await profileBlock.innerText()).replace(/\s+/g, " ");
  check("la ficha pinta el bloque de perfil", true);
  check(`el bloque de perfil nombra «${PROFILE_NAME}»`, blockText.includes(PROFILE_NAME), blockText.slice(0, 160));

  const fiscalSummary = page.getByTestId("account-fiscal-summary");
  const fiscalText = (await fiscalSummary.innerText()).replace(/\s+/g, " ");
  check("la ficha muestra el resumen fiscal fusionado", /Comisiones y fiscal/.test(fiscalText) && /Fiscal/.test(fiscalText), fiscalText.slice(0, 160));

  const editButton = page.getByRole("button", { name: /Editar comisiones y fiscal/ });
  check("el botón usa el copy del candidato", (await editButton.count()) === 1);

  await page.screenshot({ path: path.join(here, "smoke-01-ficha.png"), fullPage: false });

  // ── 2. Deep-link a Fiscal: el diálogo abre en la pestaña correcta ────────────
  await page.goto(
    `${BASE}/accounts?selected=${ACCOUNT}&tab=config&focus=fiscal`,
    { waitUntil: "domcontentloaded" },
  );
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ state: "visible", timeout: 20000 });
  const dialogText = (await dialog.innerText()).replace(/\s+/g, " ");
  check("el diálogo abre con focus=fiscal", true);
  check(
    "el diálogo es el del candidato",
    dialogText.includes("Comisiones y fiscal de la cuenta"),
    dialogText.slice(0, 120),
  );

  const taxTab = dialog.getByTestId("settings-tab-tax");
  const taxSelected = await taxTab.getAttribute("aria-selected");
  check("la pestaña Fiscal está activa", taxSelected === "true", `aria-selected=${taxSelected}`);
  check(
    "la pestaña Fiscal pinta sus campos",
    (await dialog.getByTestId("settings-tax-jurisdiction").count()) === 1,
  );

  // ── 3. El panel no duplica la asignación de perfil ───────────────────────────
  check(
    "el panel no contiene el selector de perfil",
    (await dialog.getByTestId("account-investor-profile-select").count()) === 0,
  );
  check(
    "el panel no tiene ningún desplegable de perfil",
    (await dialog.getByRole("combobox", { name: /perfil/i }).count()) === 0,
  );
  check(
    "el panel no repite la acción de asignar perfil",
    !dialogText.includes("Aplicar a esta cuenta"),
  );
  check("el panel conserva el botón de guardado fiscal", (await dialog.getByText("Guardar comisiones y fiscal").count()) >= 1);

  await page.screenshot({ path: path.join(here, "smoke-02-fiscal.png"), fullPage: false });
} finally {
  await browser.close();
}

const failed = checks.filter((c) => !c.ok);
fs.writeFileSync(
  path.join(here, "smoke-console.txt"),
  [...consoleLines, "", `checks: ${checks.length - failed.length}/${checks.length} OK`, ""].join("\n"),
  "utf8",
);
fs.writeFileSync(
  path.join(here, "smoke-result.json"),
  JSON.stringify({ base: BASE, account: ACCOUNT, checks, consoleLines }, null, 2),
  "utf8",
);
console.log(`\nchecks: ${checks.length - failed.length}/${checks.length} OK`);
if (failed.length > 0) process.exitCode = 1;
