/**
 * V1.64 / V1.67 — helpers Playwright: mock vs integración FastAPI+PostgreSQL.
 */

import { randomUUID } from "node:crypto";
import type { APIRequestContext, Page } from "@playwright/test";
import { DEFAULT_CHART_CONFIG } from "@bolsa/shared";

export const E2E_ACCOUNT_ID = "default-account-seed";
export const E2E_INSTRUMENT_ID = "inst-aapl";
export const E2E_SYMBOL = "AAPL";
export const E2E_WORKSPACE_ID = "ws-e2e-mercado";
export const E2E_MERCADO_ACCOUNT_PREFIX = "e2e-v167";

export type MercadoIntegrationFixture = {
  accountId: string;
  instrumentId: string;
  symbol: string;
  workspaceId: string;
  hasOpenPosition: boolean;
  positionId: string | null;
  tradePlanId: string | null;
  decisionId: string | null;
  levels: {
    entry: number | null;
    currentStop: number | null;
    target1: number | null;
    target2: number | null;
  } | null;
  workspaceDocument: ReturnType<typeof mercadoWorkspaceDocument>;
};

export function e2eIntegrationMode(): boolean {
  return process.env.E2E_INTEGRATION === "1";
}

export function e2eMockMode(): boolean {
  return !e2eIntegrationMode();
}

export const E2E_SKIP_INTEGRATION_REASON =
  "Set E2E_INTEGRATION=1 and ensure FastAPI (:8000) + PostgreSQL are running. See spec-v164.";

export const E2E_SKIP_DB_ISOLATION_REASON =
  "Set E2E_ALLOW_DEV_DB=1 to run integrated Mercado E2E against local PostgreSQL (creates ephemeral e2e-v167-* accounts). See spec-v167.";

/** Environment unavailable → SKIP. Fixture/product errors must FAIL. */
export async function gateIntegratedE2eEnvironment(
  request: APIRequestContext,
  baseURL: string | undefined,
  opts: { e2eEnabled: boolean; e2eSkipReason: string },
): Promise<string | null> {
  if (!opts.e2eEnabled) return opts.e2eSkipReason;
  if (!e2eIntegrationMode()) return E2E_SKIP_INTEGRATION_REASON;
  if (!baseURL) return "baseURL required";
  if (process.env.E2E_ALLOW_DEV_DB !== "1") return E2E_SKIP_DB_ISOLATION_REASON;
  try {
    await assertApiHealthy(request, baseURL);
  } catch (err) {
    return String(err);
  }
  return null;
}

/**
 * Fail-closed unless explicitly opted in. Integrated Mercado E2E mutates PG
 * (ephemeral accounts). Prefer `E2E_DATABASE_URL` pointing to a dedicated test DB.
 */
export function assertE2eDatabaseIsolation(): void {
  if (process.env.E2E_ALLOW_DEV_DB === "1") return;
  throw new Error(E2E_SKIP_DB_ISOLATION_REASON);
}

export async function assertApiHealthy(
  request: APIRequestContext,
  baseURL: string,
): Promise<void> {
  const healthUrl = new URL("/api/health", baseURL).toString();
  const res = await request.get(healthUrl);
  if (!res.ok()) {
    throw new Error(
      `API health check failed (${res.status()}). Start FastAPI + PostgreSQL before E2E_INTEGRATION=1.`,
    );
  }
}

export function mercadoWorkspaceDocument(opts?: {
  instrumentId?: string;
  symbol?: string;
  workspaceId?: string;
  name?: string;
}) {
  const tabId = "e2e-tab-mercado";
  const instrumentId = opts?.instrumentId ?? E2E_INSTRUMENT_ID;
  const symbol = opts?.symbol ?? E2E_SYMBOL;
  const workspaceId = opts?.workspaceId ?? E2E_WORKSPACE_ID;
  return {
    version: 1,
    id: workspaceId,
    name: opts?.name ?? "E2E Mercado",
    updatedAt: "2026-09-02T12:00:00.000Z",
    layout: {
      listPanelOpen: true,
      listPanelSizePct: 26,
      rightPanelOpen: false,
      rightPanelSizePct: 22,
      chartInspectorOpen: false,
      activeRoute: "/trading",
    },
    preferences: {
      autoSave: false,
      openOnStartup: true,
    },
    charts: [
      {
        id: tabId,
        instrumentId,
        label: symbol,
        timeframe: "1d",
        seriesType: "candles",
        chart: DEFAULT_CHART_CONFIG,
        indicatorInstances: [],
        drawings: [],
      },
    ],
    activeChartId: tabId,
    chartStateByListInstrument: {},
    chartListContext: null,
    indicatorTemplates: [],
    indicatorPresets: [],
    indicatorFavoritesByListId: {},
    defaultIndicatorTemplateId: null,
    chartToolbarGlobal: {
      defaultTimeframe: "1d",
      defaultSeriesType: "candles",
      activeDrawTool: "select",
      lastDrawToolByGroup: {},
      timeframeFavorites: ["1d"],
      seriesTypeFavorites: ["candles"],
      indicatorTemplateFavorites: [],
      drawToolFavorites: [],
      inspectorBarShortcutFavorites: [],
      chartVisibilityDefaults: {},
      chartLayoutDefaults: {},
    },
    list: {
      carouselListIds: [],
      carouselHiddenListIds: [],
      columnLayoutsByListId: {},
      sortByListId: {},
      visualizationEntries: [],
    },
  };
}

/** Workspace sin pestaña gráfica — journey LISTA→GRÁFICO (GP-V170). */
export function mercadoListFocusWorkspaceDocument(opts?: {
  instrumentId?: string;
  symbol?: string;
  workspaceId?: string;
  name?: string;
}) {
  const base = mercadoWorkspaceDocument(opts);
  return {
    ...base,
    charts: [],
    activeChartId: null,
    chartListContext: null,
    chartStateByListInstrument: {},
  };
}

export function mercadoOpenPosition() {
  return {
    id: "pos-e2e-1",
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    name: "Apple E2E",
    quantity: 10,
    avgCost: 100,
    lastPrice: 102,
    marketValue: 1020,
    unrealizedPnl: 20,
    unrealizedPnlPct: 2,
    operational: {
      status: "PROTECTED",
      direction: "long",
      tradePlanId: "tp-e2e",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 105,
      target2: 110,
      unrealizedR: 0.4,
    },
  };
}

export function mercadoOhlcvBars() {
  const bars = [];
  for (let i = 0; i < 30; i++) {
    const day = String(i + 1).padStart(2, "0");
    bars.push({
      timestamp: `2026-08-${day}T00:00:00.000Z`,
      open: 100 + i * 0.1,
      high: 101 + i * 0.1,
      low: 99 + i * 0.1,
      close: 100.5 + i * 0.1,
      volume: 1_000_000,
      adjClose: null,
      source: "e2e",
    });
  }
  return bars;
}

function chartPersistBackupFromWorkspace(
  workspace: ReturnType<typeof mercadoWorkspaceDocument>,
) {
  return {
    charts: workspace.charts,
    activeChartId: workspace.activeChartId,
    chartStateByListInstrument: workspace.chartStateByListInstrument,
    chartListContext: workspace.chartListContext,
    chartToolbarGlobal: workspace.chartToolbarGlobal,
    indicatorTemplates: workspace.indicatorTemplates,
    indicatorPresets: workspace.indicatorPresets,
    indicatorFavoritesByListId: workspace.indicatorFavoritesByListId,
    defaultIndicatorTemplateId: workspace.defaultIndicatorTemplateId,
    preferences: workspace.preferences,
    chartInspectorOpen: workspace.layout.chartInspectorOpen,
    list: workspace.list,
    updatedAt: workspace.updatedAt,
  };
}

/** Crea cuenta aislada, workspace con gráfico AAPL y buy opcional vía HTTP real. */
export async function ensureMercadoIntegrationFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<MercadoIntegrationFixture> {
  assertE2eDatabaseIsolation();

  const instrumentsRes = await request.get(
    new URL("/api/instruments", baseURL).toString(),
  );
  if (!instrumentsRes.ok()) {
    throw new Error(
      `GET /api/instruments failed (${instrumentsRes.status()}).`,
    );
  }
  const instruments = (await instrumentsRes.json()).data as Array<{
    id: string;
    symbol: string;
  }>;
  const instrument =
    instruments.find((row) => row.id === E2E_INSTRUMENT_ID) ?? instruments[0];
  if (!instrument) {
    throw new Error("No instruments available for Mercado E2E seed.");
  }

  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `${E2E_MERCADO_ACCOUNT_PREFIX}-${suffix}`,
        currency: "EUR",
        initialDeposit: 100_000,
      },
    },
  );
  if (!accountRes.ok()) {
    throw new Error(
      `POST /api/accounts failed (${accountRes.status()}): ${await accountRes.text()}`,
    );
  }
  const accountId = (await accountRes.json()).data.id as string;

  const now = new Date().toISOString();
  const mandateRes = await request.put(
    new URL(`/api/accounts/${accountId}/mandates`, baseURL).toString(),
    {
      data: {
        tenures: [
          {
            id: `mt-e2e-${suffix}`,
            accountId,
            instrumentId: instrument.id,
            effectiveFrom: now,
            actor: "user",
            reason: "adopt",
          },
        ],
        links: [],
      },
    },
  );
  if (!mandateRes.ok()) {
    throw new Error(
      `PUT mandates failed (${mandateRes.status()}): ${await mandateRes.text()}`,
    );
  }

  let hasOpenPosition = false;
  let positionId: string | null = null;
  let tradePlanId: string | null = null;
  let decisionId: string | null = null;
  let levels: MercadoIntegrationFixture["levels"] = null;
  const tradeRes = await request.post(
    new URL("/api/portfolio/trade", baseURL).toString(),
    {
      headers: { "X-Account-Id": accountId },
      data: {
        instrumentId: instrument.id,
        type: "buy",
        quantity: 5,
        price: 50,
        idempotencyKey: `e2e-v167-${suffix}`,
      },
    },
  );
  if (!tradeRes.ok()) {
    throw new Error(
      `POST /api/portfolio/trade failed (${tradeRes.status()}): ${await tradeRes.text()}. Open position seed is required.`,
    );
  }
  hasOpenPosition = true;
  const portfolioRes = await request.get(
    new URL("/api/portfolio", baseURL).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!portfolioRes.ok()) {
    throw new Error(
      `GET /api/portfolio after buy failed (${portfolioRes.status()}): ${await portfolioRes.text()}`,
    );
  }
  const portfolioJson = (await portfolioRes.json()) as {
    data?: {
      positions?: Array<{
        id: string;
        instrumentId: string;
        operational?: {
          tradePlanId?: string;
          decisionId?: string;
          operationalView?: {
            positionId?: string;
            tradePlanId?: string;
            decisionId?: string | null;
            levels?: {
              entry?: number | null;
              currentStop?: number | null;
              target1?: number | null;
              target2?: number | null;
            };
          };
        };
      }>;
    };
  };
  const seeded = portfolioJson.data?.positions?.find(
    (row) => row.instrumentId === instrument.id,
  );
  if (!seeded) {
    throw new Error(
      `Portfolio buy seed did not persist an open position for ${instrument.symbol}.`,
    );
  }
  positionId = seeded.operational?.operationalView?.positionId ?? seeded.id;
  tradePlanId =
    seeded.operational?.operationalView?.tradePlanId ??
    seeded.operational?.tradePlanId ??
    null;
  decisionId =
    seeded.operational?.operationalView?.decisionId ??
    seeded.operational?.decisionId ??
    null;
  const viewLevels = seeded.operational?.operationalView?.levels;
  levels = viewLevels
    ? {
        entry: viewLevels.entry ?? null,
        currentStop: viewLevels.currentStop ?? null,
        target1: viewLevels.target1 ?? null,
        target2: viewLevels.target2 ?? null,
      }
    : null;

  const workspaceDocument = mercadoWorkspaceDocument({
    instrumentId: instrument.id,
    symbol: instrument.symbol,
    name: `E2E Mercado ${suffix}`,
  });
  const workspaceRes = await request.post(
    new URL("/api/workspaces", baseURL).toString(),
    {
      data: {
        name: workspaceDocument.name,
        document: workspaceDocument,
        isDefault: false,
      },
    },
  );
  if (!workspaceRes.ok()) {
    throw new Error(
      `POST /api/workspaces failed (${workspaceRes.status()}): ${await workspaceRes.text()}`,
    );
  }
  const workspaceId = (await workspaceRes.json()).data.id as string;
  const workspaceDocumentWithId = {
    ...workspaceDocument,
    id: workspaceId,
  };

  return {
    accountId,
    instrumentId: instrument.id,
    symbol: instrument.symbol,
    workspaceId,
    hasOpenPosition,
    positionId,
    tradePlanId,
    decisionId,
    levels,
    workspaceDocument: workspaceDocumentWithId,
  };
}

/** Seed cuenta activa + workspace + layout DECISIÓN antes de navegar a /trading. */
export async function seedMercadoBrowserState(
  page: Page,
  opts?: {
    accountId?: string;
    workspaceId?: string;
    workspaceDocument?: ReturnType<typeof mercadoWorkspaceDocument>;
    operativaOpen?: boolean;
    chartsOpen?: boolean;
  },
): Promise<void> {
  const accountId = opts?.accountId ?? E2E_ACCOUNT_ID;
  const workspaceDocument =
    opts?.workspaceDocument ?? mercadoWorkspaceDocument();
  const workspaceId = opts?.workspaceId ?? workspaceDocument.id;
  const chartPersistBackup = chartPersistBackupFromWorkspace(workspaceDocument);
  const operativaOpen = opts?.operativaOpen ?? true;
  const chartsOpen = opts?.chartsOpen ?? true;

  await page.addInitScript(
    ({
      accountId,
      workspaceId,
      chartPersistBackup,
      operativaOpen,
      chartsOpen,
    }) => {
      const zustand = (key: string, partial: Record<string, unknown>) => {
        localStorage.setItem(
          key,
          JSON.stringify({ state: partial, version: 0 }),
        );
      };
      zustand("bolsa-active-account", { activeAccountId: accountId });
      zustand("bolsa-trading-layout-v1", {
        listsOpen: true,
        chartsOpen,
        operationsOpen: false,
        operativaOpen,
        listsMaximized: false,
        chartsMaximized: false,
        operationsMaximized: false,
        listsWidthPct: 26,
        operationsHeightPct: 22,
        operativaWidthPct: 28,
        operativaSections: {
          recommendation: false,
          info: true,
          config: true,
        },
        operativaSectionHeights: {
          recommendation: 320,
          info: 200,
          config: 180,
        },
        namedLayoutId: "trader",
      });
      localStorage.setItem(
        "bolsa-mercado-decision-surface-v1",
        JSON.stringify({ placement: "panel" }),
      );
      localStorage.setItem(
        "bolsa-workspace-meta",
        JSON.stringify({
          state: {
            activeWorkspaceId: workspaceId,
            recents: [workspaceId],
            chartPersistBackup,
          },
          version: 0,
        }),
      );
    },
    { accountId, workspaceId, chartPersistBackup, operativaOpen, chartsOpen },
  );
}

export const E2E_HOY_ACCOUNT_PREFIX = "e2e-v168";

export type HoyIntegrationFixture = {
  accountId: string;
  hasAutoDesk: boolean;
  entryProposed: number;
};

/** Cuenta aislada para Hoy / Paper Autonomous Desk E2E. */
export async function ensureHoyIntegrationFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<HoyIntegrationFixture> {
  assertE2eDatabaseIsolation();

  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `${E2E_HOY_ACCOUNT_PREFIX}-${suffix}`,
        currency: "EUR",
        initialDeposit: 100_000,
      },
    },
  );
  if (!accountRes.ok()) {
    throw new Error(
      `POST /api/accounts failed (${accountRes.status()}): ${await accountRes.text()}`,
    );
  }
  const accountId = (await accountRes.json()).data.id as string;

  const reportRes = await request.get(
    new URL(
      `/api/paper-desk/daily-report?accountId=${encodeURIComponent(accountId)}`,
      baseURL,
    ).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!reportRes.ok()) {
    throw new Error(
      `GET /paper-desk/daily-report failed (${reportRes.status()}): ${await reportRes.text()}`,
    );
  }
  const autoDesk = (await reportRes.json()).data?.autoDesk as
    | { entry?: { proposed?: number } }
    | undefined;

  return {
    accountId,
    hasAutoDesk: Boolean(autoDesk),
    entryProposed: autoDesk?.entry?.proposed ?? 0,
  };
}

/** Seed cuenta activa antes de navegar a /mesa. */
export async function seedHoyBrowserState(
  page: Page,
  opts?: { accountId?: string },
): Promise<void> {
  const accountId = opts?.accountId ?? E2E_ACCOUNT_ID;
  await page.addInitScript(
    ({ accountId }) => {
      localStorage.setItem(
        "bolsa-active-account",
        JSON.stringify({ state: { activeAccountId: accountId }, version: 0 }),
      );
    },
    { accountId },
  );
}
