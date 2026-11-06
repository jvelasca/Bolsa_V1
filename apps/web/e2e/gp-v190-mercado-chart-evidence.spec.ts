/**
 * GP-V190 — evidencia visual de la operativa gráfica de MERCADO.
 *
 * Recorre el checklist de la fase 8 sobre el stack local REAL (solo lectura:
 * aborta escrituras de workspace) en dos viewports y dos temas, y guarda
 * capturas + `browser-checklist.json` en `evidence_runs/mercado-chart-<fecha>/`.
 *
 * Requiere opt-in:
 *   $env:PLAYWRIGHT_BASE_URL="http://localhost:5173"
 *   $env:E2E_INTEGRATION="1"; $env:E2E_EVIDENCE="1"
 *   pnpm --filter @bolsa/web exec playwright test gp-v190-mercado-chart-evidence
 *
 * Default: skipped (CI no genera capturas).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
  type Route,
} from "@playwright/test";

import { E2E_ACCOUNT_ID } from "./helpers/ids";
import {
  mercadoWorkspaceDocument,
  seedMercadoBrowserState,
} from "./helpers/mercado";

const NOISE = [
  /ResizeObserver loop/i,
  /Failed to load resource/i,
  /favicon/i,
  /net::ERR_/i,
];

const evidenceRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../evidence_runs",
);
const today = new Date().toISOString().slice(0, 10);
const outDir = path.join(evidenceRoot, `mercado-chart-${today}`, "browser");

type Checklist = {
  theme: "dark" | "light";
  viewport: { width: number; height: number };
  loadMs: number;
  chartReadyMs: number;
  barsCount: number;
  timeframes: string[];
  seriesTypes: string[];
  zoom: { initial: string; zoomed: string; reset: string };
  inspectorOpen: boolean;
  screenshots: string[];
  consoleErrors: string[];
  checks: { id: string; ok: boolean; detail: string }[];
};

const combos: { theme: "dark" | "light"; width: number; height: number }[] = [
  { theme: "dark", width: 1920, height: 1080 },
  { theme: "light", width: 1920, height: 1080 },
  { theme: "dark", width: 1366, height: 768 },
  { theme: "light", width: 1366, height: 768 },
];

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) =>
    errors.push(`pageerror: ${error.stack ?? error.message}`),
  );
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (NOISE.some((pattern) => pattern.test(text))) return;
    errors.push(`console: ${text}`);
  });
  return errors;
}

async function guardWrites(page: Page) {
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
      await route.continue();
      return;
    }
    const pathname = new URL(request.url()).pathname;
    const isWrite =
      pathname.startsWith("/api/workspaces") ||
      pathname.startsWith("/api/accounts") ||
      (method === "POST" && /\/sync$/.test(pathname));
    if (isWrite) {
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
}

async function selectZone(page: Page, zone: RegExp, optionId: string) {
  await page.getByRole("button", { name: zone }).first().click();
  await page
    .getByTestId("chart-zone-menu")
    .locator(`[data-zone-option-id="${optionId}"]`)
    .click();
}

async function snapshot(
  page: Page,
  target: string,
  name: string,
  shots: string[],
) {
  const file = path.join(outDir, target, name);
  mkdirSync(path.dirname(file), { recursive: true });
  await page.screenshot({ path: file, fullPage: false });
  shots.push(path.relative(path.resolve(evidenceRoot, ".."), file));
}

async function runCombo(
  browser: Browser,
  combo: (typeof combos)[number],
  workspace: { id: string; document: unknown },
): Promise<Checklist> {
  const target = `${combo.theme}-${combo.width}`;
  mkdirSync(path.join(outDir, target), { recursive: true });
  const context: BrowserContext = await browser.newContext({
    viewport: { width: combo.width, height: combo.height },
    colorScheme: combo.theme,
  });
  await context.addInitScript((theme) => {
    localStorage.setItem(
      "bolsa-ui-prefs-v1",
      JSON.stringify({
        state: { uiTheme: theme, uiDensity: "comfortable" },
        version: 0,
      }),
    );
  }, combo.theme);

  const page = await context.newPage();
  const errors = collectErrors(page);
  await guardWrites(page);
  await seedMercadoBrowserState(page, {
    accountId: E2E_ACCOUNT_ID,
    workspaceId: workspace.id,
    workspaceDocument: workspace.document as ReturnType<
      typeof mercadoWorkspaceDocument
    >,
    operativaOpen: false,
  });

  const result: Checklist = {
    theme: combo.theme,
    viewport: { width: combo.width, height: combo.height },
    loadMs: 0,
    chartReadyMs: 0,
    barsCount: 0,
    timeframes: [],
    seriesTypes: [],
    zoom: { initial: "", zoomed: "", reset: "" },
    inspectorOpen: false,
    screenshots: [],
    consoleErrors: errors,
    checks: [],
  };
  const check = (id: string, ok: boolean, detail: string) =>
    result.checks.push({ id, ok, detail });

  try {
    const started = Date.now();
    await page.goto("/trading");
    const chart = page.getByTestId("ohlcv-chart");
    await expect(chart).toBeVisible({ timeout: 30_000 });
    result.loadMs = Date.now() - started;

    await expect(chart).toHaveAttribute("data-has-data", "true", {
      timeout: 25_000,
    });
    result.chartReadyMs = Date.now() - started;
    result.barsCount = Number(await chart.getAttribute("data-bars-count"));
    check("chart.bars", result.barsCount > 0, `barras=${result.barsCount}`);
    check(
      "chart.visible-range",
      Boolean(await chart.getAttribute("data-visible-range")),
      String(await chart.getAttribute("data-visible-range")),
    );
    result.timeframes.push(String(await chart.getAttribute("data-timeframe")));
    result.seriesTypes.push(
      String(await chart.getAttribute("data-series-type")),
    );
    await snapshot(page, target, "01-inicial.png", result.screenshots);

    await selectZone(page, /Escala/, "1wk");
    await expect(chart).toHaveAttribute("data-timeframe", "1wk", {
      timeout: 25_000,
    });
    result.timeframes.push("1wk");
    await page.waitForTimeout(400);
    await snapshot(page, target, "02-escala-1wk.png", result.screenshots);

    await selectZone(page, /Escala/, "1d");
    await expect(chart).toHaveAttribute("data-timeframe", "1d", {
      timeout: 25_000,
    });

    await selectZone(page, /Estilo/, "line");
    await expect(chart).toHaveAttribute("data-series-type", "line", {
      timeout: 10_000,
    });
    result.seriesTypes.push("line");
    await snapshot(page, target, "03-estilo-linea.png", result.screenshots);

    await selectZone(page, /Estilo/, "candles");
    await expect(chart).toHaveAttribute("data-series-type", "candles", {
      timeout: 10_000,
    });

    result.zoom.initial = String(
      await chart.getAttribute("data-visible-range"),
    );
    await page.getByTitle("Acercar", { exact: true }).click();
    await expect
      .poll(() => chart.getAttribute("data-visible-range"), { timeout: 5_000 })
      .not.toBe(result.zoom.initial);
    result.zoom.zoomed = String(await chart.getAttribute("data-visible-range"));
    await snapshot(page, target, "04-zoom-in.png", result.screenshots);

    await page.getByTitle("Ajustar a ventana", { exact: true }).click();
    await expect
      .poll(() => chart.getAttribute("data-visible-range"), { timeout: 5_000 })
      .toBe(result.zoom.initial);
    result.zoom.reset = String(await chart.getAttribute("data-visible-range"));
    check(
      "zoom.reset",
      result.zoom.reset === result.zoom.initial,
      `${result.zoom.initial} → ${result.zoom.zoomed} → ${result.zoom.reset}`,
    );

    await page
      .getByTitle("Mostrar inspector de gráficos", { exact: true })
      .click();
    const inspector = page.getByTestId("chart-inspector-panel");
    await expect(inspector).toHaveAttribute("data-open", "true");
    result.inspectorOpen = true;
    await snapshot(page, target, "05-inspector.png", result.screenshots);
    await inspector.getByTitle("Colapsar inspector", { exact: true }).click();
    await expect(inspector).toHaveAttribute("data-open", "false");
  } catch (error) {
    check("journey", false, (error as Error).message.slice(0, 500));
  }

  result.consoleErrors = errors;
  check("console.clean", errors.length === 0, `${errors.length} error(es)`);
  if (!result.screenshots.length) {
    await snapshot(page, target, "00-fallo.png", result.screenshots).catch(
      () => undefined,
    );
  }
  await context.close();
  return result;
}

test.describe("GP-V190 — evidencia visual (live read-only)", () => {
  let skip: string | null = null;
  let workspace: { id: string; document: unknown } | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    if (process.env.E2E_EVIDENCE !== "1") {
      skip = "Set E2E_EVIDENCE=1 to generate browser evidence.";
      return;
    }
    if (process.env.E2E_INTEGRATION !== "1") {
      skip = "Set E2E_INTEGRATION=1 with the local stack running.";
      return;
    }
    if (!baseURL) {
      skip = "PLAYWRIGHT_BASE_URL required.";
      return;
    }
    const response = await request.get("/api/workspaces/default");
    if (!response.ok()) {
      skip = `GET /api/workspaces/default → ${response.status()}`;
      return;
    }
    const body = (await response.json()) as {
      data?: { id?: string; document?: unknown };
    };
    if (!body.data?.id) {
      skip = "Default workspace sin id/document.";
      return;
    }
    workspace = {
      id: body.data.id,
      document: body.data.document ?? mercadoWorkspaceDocument(),
    };
  });

  test("GP-V190-E01: checklist visual 2 viewports × 2 temas", async ({
    browser,
  }) => {
    test.skip(skip !== null, skip ?? "");
    if (!workspace) throw new Error("workspace required");
    test.setTimeout(240_000);

    const results: Checklist[] = [];
    for (const combo of combos) {
      results.push(await runCombo(browser, combo, workspace));
    }

    mkdirSync(outDir, { recursive: true });
    const reportPath = path.join(
      evidenceRoot,
      `mercado-chart-${today}`,
      "browser-checklist.json",
    );
    writeFileSync(
      reportPath,
      `${JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2)}\n`,
      "utf8",
    );

    const failures = results.flatMap((entry) =>
      entry.checks
        .filter((check) => !check.ok)
        .map(
          (check) =>
            `${entry.theme}-${entry.viewport.width} ${check.id}: ${check.detail}`,
        ),
    );
    expect(failures, `Evidencia: ${reportPath}`).toEqual([]);
  });
});
