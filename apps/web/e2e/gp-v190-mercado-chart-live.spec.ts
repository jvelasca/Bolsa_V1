/**
 * GP-V190 — MERCADO gráficos · verificación integrada de solo lectura.
 *
 * Usa el stack local real (Vite en :5173 + FastAPI en :8000 + PostgreSQL) y el
 * workspace por defecto del usuario, SIN escribir nada:
 *   - bloquea `PUT /api/workspaces/**` y `POST /api/workspaces` (se abortan);
 *   - bloquea `POST /api/instruments/<id>/sync` para no sincronizar;
 *   - no crea cuentas, workspaces ni dibujos persistentes.
 *
 * Requiere opt-in explícito:
 *   $env:PLAYWRIGHT_BASE_URL="http://localhost:5173"; $env:E2E_INTEGRATION="1"
 *   pnpm --filter @bolsa/web exec playwright test gp-v190-mercado-chart-live
 *
 * Default: skipped.
 */
import { expect, test, type Page, type Route } from "@playwright/test";

import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
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

const READ_ONLY_BLOCKED: RegExp[] = [
  /\/api\/workspaces(?:\/|$)/,
  /\/api\/accounts(?:\/|$)/,
  /\/api\/instruments\/[^/]+\/sync(?:\?|$)/,
];

function integrationEnabled(): boolean {
  return process.env.E2E_INTEGRATION === "1";
}

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

/** Aborta escrituras y sincronizaciones: la corrida live es read-only. */
async function installReadOnlyGuards(page: Page, writes: string[]) {
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
      await route.continue();
      return;
    }
    const url = new URL(request.url());
    const path = url.pathname;
    const blocked = READ_ONLY_BLOCKED.some((pattern) => pattern.test(path));
    if (shouldBlockWrite(method, path, blocked)) {
      writes.push(`${method} ${path}`);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
}

function shouldBlockWrite(method: string, path: string, blocked: boolean) {
  if (!blocked) return false;
  if (path.startsWith("/api/workspaces")) return true;
  if (path.startsWith("/api/accounts")) return true;
  return /\/sync$/.test(path) && method === "POST";
}

/**
 * La app puede intentar persistir la cola de supervisión u otros PUT de
 * cuentas; lo importante es que NINGUNA escritura de workspace llegue al
 * servidor (el workspace del usuario queda intacto).
 */
function workspaceWrites(writes: string[]): string[] {
  return writes.filter((entry) => entry.includes("/api/workspaces"));
}

async function openLiveChart(
  page: Page,
  workspace: { id: string; document: unknown },
  writes: string[],
) {
  await installReadOnlyGuards(page, writes);
  await seedMercadoBrowserState(page, {
    accountId: E2E_ACCOUNT_ID,
    workspaceId: workspace.id,
    workspaceDocument: workspace.document as ReturnType<
      typeof mercadoWorkspaceDocument
    >,
    operativaOpen: false,
  });
  await page.goto("/trading");
  const chart = page.getByTestId("ohlcv-chart");
  await expect(chart).toBeVisible({ timeout: 30_000 });
  return chart;
}

async function selectScale(page: Page, optionId: string) {
  await page
    .getByRole("button", { name: /Escala/ })
    .first()
    .click();
  await page
    .getByTestId("chart-zone-menu")
    .locator(`[data-zone-option-id="${optionId}"]`)
    .click();
}

test.describe("GP-V190 — MERCADO gráficos operativa (live read-only)", () => {
  let environmentSkip: string | null = null;
  let workspace: { id: string; document: unknown } | null = null;

  test.beforeAll(async ({ request, baseURL }) => {
    if (!e2eEnabled()) {
      environmentSkip = E2E_SKIP_REASON;
      return;
    }
    if (!integrationEnabled()) {
      environmentSkip =
        "Set E2E_INTEGRATION=1 with the local stack running (:5173 + :8000).";
      return;
    }
    if (!baseURL) {
      environmentSkip = "PLAYWRIGHT_BASE_URL is required for the live spec.";
      return;
    }
    try {
      const response = await request.get("/api/workspaces/default");
      if (!response.ok()) {
        environmentSkip = `GET /api/workspaces/default → ${response.status()}`;
        return;
      }
      const body = (await response.json()) as {
        data?: { id?: string; document?: unknown };
      };
      if (!body.data?.id) {
        environmentSkip = "Default workspace without id/document.";
        return;
      }
      workspace = {
        id: body.data.id,
        document: body.data.document ?? mercadoWorkspaceDocument(),
      };
    } catch (error) {
      environmentSkip = `API no disponible: ${(error as Error).message}`;
    }
  });

  test.beforeEach(() => {
    if (environmentSkip) test.skip(true, environmentSkip);
    if (!workspace) throw new Error("Live workspace fixture missing.");
  });

  test("GP-V190-L01: el gráfico real carga barras y metadatos del workspace", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const writes: string[] = [];
    if (!workspace) throw new Error("workspace required");
    const chart = await openLiveChart(page, workspace, writes);

    await expect(chart).toHaveAttribute("data-has-data", "true", {
      timeout: 25_000,
    });
    await expect
      .poll(async () => Number(await chart.getAttribute("data-bars-count")))
      .toBeGreaterThan(0);
    await expect(chart).toHaveAttribute("data-timeframe", "1d");
    expect(await chart.getAttribute("data-instrument-id")).toBeTruthy();
    expect(await chart.getAttribute("data-visible-range")).toBeTruthy();
    expect(workspaceWrites(writes)).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("GP-V190-L02: cambiar a 1S recalcula contra el stack real sin escrituras", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const writes: string[] = [];
    if (!workspace) throw new Error("workspace required");
    const chart = await openLiveChart(page, workspace, writes);

    await selectScale(page, "1wk");
    await expect(chart).toHaveAttribute("data-timeframe", "1wk", {
      timeout: 25_000,
    });
    await expect
      .poll(async () => Number(await chart.getAttribute("data-bars-count")))
      .toBeGreaterThanOrEqual(0);

    expect(workspaceWrites(writes)).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("GP-V190-L03: invariantes OHLCV/indicadores/frescura del instrumento real", async ({
    page,
    request,
  }) => {
    const errors = collectErrors(page);
    const writes: string[] = [];
    if (!workspace) throw new Error("workspace required");
    const chart = await openLiveChart(page, workspace, writes);
    const instrumentId = await chart.getAttribute("data-instrument-id");
    expect(instrumentId).toBeTruthy();

    const ohlcvResponse = await request.get(
      `/api/instruments/${instrumentId}/ohlcv?limit=120&timeframe=1d`,
    );
    expect(ohlcvResponse.ok()).toBeTruthy();
    const ohlcv = (await ohlcvResponse.json()) as {
      data: { timestamp: string; close: number }[];
      meta: { timeframe: string; count: number };
    };
    expect(ohlcv.meta.count).toBe(ohlcv.data.length);
    expect(ohlcv.data.length).toBeGreaterThan(0);
    const timestamps = ohlcv.data.map((bar) => bar.timestamp);
    expect([...timestamps].sort()).toEqual(timestamps);
    expect(new Set(timestamps).size).toBe(timestamps.length);

    const indicatorsResponse = await request.get(
      `/api/instruments/${instrumentId}/indicators?limit=120&timeframe=1d`,
    );
    expect(indicatorsResponse.ok()).toBeTruthy();
    const indicators = (await indicatorsResponse.json()) as {
      data: { timestamp: string }[];
    };
    expect(indicators.data.length).toBe(ohlcv.data.length);
    expect(indicators.data.map((point) => point.timestamp)).toEqual(timestamps);

    const statusResponse = await request.get(
      `/api/instruments/${instrumentId}/data-status?timeframe=1d`,
    );
    expect(statusResponse.ok()).toBeTruthy();
    const status = (await statusResponse.json()) as {
      data: { freshnessStatus: string; barCount: number };
    };
    expect(["empty", "stale", "current", "gap_detected", "error"]).toContain(
      status.data.freshnessStatus,
    );
    expect(status.data.barCount).toBeGreaterThanOrEqual(0);

    expect(workspaceWrites(writes)).toEqual([]);
    expect(errors).toEqual([]);
  });
});
