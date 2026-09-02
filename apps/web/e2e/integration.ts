/**
 * V1.64 / V1.67 — helpers Playwright: mock vs integración FastAPI+PostgreSQL.
 */

import { randomUUID } from "node:crypto";
import type { APIRequestContext, Page } from "@playwright/test";
import { buildPaperDailyReport, DEFAULT_CHART_CONFIG } from "@bolsa/shared";

export const E2E_ACCOUNT_ID = "default-account-seed";
export const E2E_INSTRUMENT_ID = "inst-aapl";
export const E2E_SYMBOL = "AAPL";
export const E2E_WORKSPACE_ID = "ws-e2e-mercado";
export const E2E_MERCADO_ACCOUNT_PREFIX = "e2e-v167";
export const E2E_MERCADO_MULTI_ACCOUNT_PREFIX = "e2e-v173";

/** Mock / preferred symbols for multi-instrument integrity (V1.73). */
export const E2E_MULTI_POSITION_INSTRUMENTS = [
  { id: "inst-aapl", symbol: "AAPL", name: "Apple E2E" },
  { id: "inst-msft", symbol: "MSFT", name: "Microsoft E2E" },
  { id: "inst-googl", symbol: "GOOGL", name: "Alphabet E2E" },
] as const;

export const E2E_ENTRY_ONLY_INSTRUMENT = {
  id: "inst-nvda",
  symbol: "NVDA",
  name: "NVIDIA E2E",
} as const;

export type MercadoLevels = {
  entry: number | null;
  currentStop: number | null;
  target1: number | null;
  target2: number | null;
};

export type MercadoInstrumentSlice = {
  instrumentId: string;
  symbol: string;
  positionId: string;
  tradePlanId: string | null;
  decisionId: string | null;
  levels: MercadoLevels | null;
};

export type MercadoIntegrationFixture = {
  accountId: string;
  instrumentId: string;
  symbol: string;
  workspaceId: string;
  hasOpenPosition: boolean;
  positionId: string | null;
  tradePlanId: string | null;
  decisionId: string | null;
  levels: MercadoLevels | null;
  workspaceDocument: ReturnType<typeof mercadoWorkspaceDocument>;
};

/** ≥3 posiciones PAPER + instrumento Entry-only (sin qty) cuando el catálogo lo permite. */
export type MultiInstrumentMercadoFixture = {
  accountId: string;
  workspaceId: string;
  instruments: MercadoInstrumentSlice[];
  entryOnly: { instrumentId: string; symbol: string } | null;
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

/** Workspace con gráfico de posición + Entry-only (dos pestañas). */
export function mercadoEntryPositionWorkspaceDocument(opts?: {
  positionInstrumentId?: string;
  positionSymbol?: string;
  entryInstrumentId?: string;
  entrySymbol?: string;
  workspaceId?: string;
  name?: string;
}) {
  const positionInstrumentId =
    opts?.positionInstrumentId ?? E2E_MULTI_POSITION_INSTRUMENTS[0].id;
  const positionSymbol =
    opts?.positionSymbol ?? E2E_MULTI_POSITION_INSTRUMENTS[0].symbol;
  const entryInstrumentId =
    opts?.entryInstrumentId ?? E2E_ENTRY_ONLY_INSTRUMENT.id;
  const entrySymbol = opts?.entrySymbol ?? E2E_ENTRY_ONLY_INSTRUMENT.symbol;
  const workspaceId = opts?.workspaceId ?? E2E_WORKSPACE_ID;
  const positionTabId = "e2e-tab-position";
  const entryTabId = "e2e-tab-entry";
  const base = mercadoWorkspaceDocument({
    instrumentId: positionInstrumentId,
    symbol: positionSymbol,
    workspaceId,
    name: opts?.name,
  });
  return {
    ...base,
    charts: [
      {
        ...base.charts[0]!,
        id: positionTabId,
        instrumentId: positionInstrumentId,
        label: positionSymbol,
      },
      {
        ...base.charts[0]!,
        id: entryTabId,
        instrumentId: entryInstrumentId,
        label: entrySymbol,
      },
    ],
    activeChartId: positionTabId,
  };
}

export function mercadoOpenPosition(opts?: {
  id?: string;
  instrumentId?: string;
  symbol?: string;
  name?: string;
  tradePlanId?: string;
  currentStop?: number;
  target1?: number;
  target2?: number;
  avgCost?: number;
  lastPrice?: number;
}) {
  const instrumentId = opts?.instrumentId ?? E2E_INSTRUMENT_ID;
  const symbol = opts?.symbol ?? E2E_SYMBOL;
  const avgCost = opts?.avgCost ?? 100;
  const lastPrice = opts?.lastPrice ?? avgCost + 2;
  const qty = 10;
  return {
    id: opts?.id ?? "pos-e2e-1",
    instrumentId,
    symbol,
    name: opts?.name ?? "Apple E2E",
    quantity: qty,
    avgCost,
    lastPrice,
    marketValue: lastPrice * qty,
    unrealizedPnl: (lastPrice - avgCost) * qty,
    unrealizedPnlPct: ((lastPrice - avgCost) / avgCost) * 100,
    operational: {
      status: "PROTECTED",
      direction: "long",
      tradePlanId: opts?.tradePlanId ?? "tp-e2e",
      plannedEntry: avgCost,
      actualEntry: avgCost,
      initialStop: opts?.currentStop ?? avgCost - 5,
      currentStop: opts?.currentStop ?? avgCost - 5,
      target1: opts?.target1 ?? avgCost + 5,
      target2: opts?.target2 ?? avgCost + 10,
      unrealizedR: 0.4,
      operationalView: {
        positionId: opts?.id ?? "pos-e2e-1",
        tradePlanId: opts?.tradePlanId ?? "tp-e2e",
        decisionId: null,
        levels: {
          entry: avgCost,
          currentStop: opts?.currentStop ?? avgCost - 5,
          target1: opts?.target1 ?? avgCost + 5,
          target2: opts?.target2 ?? avgCost + 10,
        },
      },
    },
  };
}

/** Tres posiciones mock + instrumento Entry-only (NVDA). */
export function mercadoMultiOpenPositions() {
  return E2E_MULTI_POSITION_INSTRUMENTS.map((row, index) =>
    mercadoOpenPosition({
      id: `pos-e2e-${index + 1}`,
      instrumentId: row.id,
      symbol: row.symbol,
      name: row.name,
      tradePlanId: `tp-e2e-${index + 1}`,
      avgCost: 100 + index * 10,
      currentStop: 95 + index * 10,
      target1: 105 + index * 10,
      target2: 110 + index * 10,
    }),
  );
}

export function mercadoMultiInstrumentSlicesFromMock(): MercadoInstrumentSlice[] {
  return mercadoMultiOpenPositions().map((pos) => ({
    instrumentId: pos.instrumentId,
    symbol: pos.symbol,
    positionId: pos.operational.operationalView.positionId,
    tradePlanId: pos.operational.tradePlanId,
    decisionId: pos.operational.operationalView.decisionId,
    levels: pos.operational.operationalView.levels,
  }));
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

type PortfolioPositionRow = {
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
};

function sliceFromPortfolioPosition(
  seeded: PortfolioPositionRow,
  symbol: string,
): MercadoInstrumentSlice {
  const viewLevels = seeded.operational?.operationalView?.levels;
  return {
    instrumentId: seeded.instrumentId,
    symbol,
    positionId: seeded.operational?.operationalView?.positionId ?? seeded.id,
    tradePlanId:
      seeded.operational?.operationalView?.tradePlanId ??
      seeded.operational?.tradePlanId ??
      null,
    decisionId:
      seeded.operational?.operationalView?.decisionId ??
      seeded.operational?.decisionId ??
      null,
    levels: viewLevels
      ? {
          entry: viewLevels.entry ?? null,
          currentStop: viewLevels.currentStop ?? null,
          target1: viewLevels.target1 ?? null,
          target2: viewLevels.target2 ?? null,
        }
      : null,
  };
}

/**
 * Cuenta aislada con ≥3 buys PAPER + mandato Entry-only (4º instrumento) si el catálogo lo permite.
 * FAIL-closed si hay menos de 3 instrumentos disponibles.
 */
export async function ensureMultiInstrumentMercadoFixture(
  request: APIRequestContext,
  baseURL: string,
): Promise<MultiInstrumentMercadoFixture> {
  assertE2eDatabaseIsolation();

  const instrumentsRes = await request.get(
    new URL("/api/instruments", baseURL).toString(),
  );
  if (!instrumentsRes.ok()) {
    throw new Error(
      `GET /api/instruments failed (${instrumentsRes.status()}).`,
    );
  }
  const catalog = (await instrumentsRes.json()).data as Array<{
    id: string;
    symbol: string;
  }>;
  if (catalog.length < 3) {
    throw new Error(
      `Multi-instrument Mercado E2E requires ≥3 instruments in catalog (got ${catalog.length}).`,
    );
  }

  const preferredIds = new Set(
    E2E_MULTI_POSITION_INSTRUMENTS.map((row) => row.id),
  );
  const preferred = catalog.filter((row) => preferredIds.has(row.id));
  const rest = catalog.filter((row) => !preferredIds.has(row.id));
  const ordered = [...preferred, ...rest];
  const buyTargets = ordered.slice(0, 3);
  const entryTarget = ordered.length >= 4 ? ordered[3]! : null;

  const suffix = randomUUID().slice(0, 8);
  const accountRes = await request.post(
    new URL("/api/accounts", baseURL).toString(),
    {
      data: {
        name: `${E2E_MERCADO_MULTI_ACCOUNT_PREFIX}-${suffix}`,
        currency: "EUR",
        initialDeposit: 250_000,
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
  const mandateInstruments = entryTarget
    ? [...buyTargets, entryTarget]
    : buyTargets;
  const mandateRes = await request.put(
    new URL(`/api/accounts/${accountId}/mandates`, baseURL).toString(),
    {
      data: {
        tenures: mandateInstruments.map((instrument, index) => ({
          id: `mt-e2e-v173-${suffix}-${index}`,
          accountId,
          instrumentId: instrument.id,
          effectiveFrom: now,
          actor: "user",
          reason: "adopt",
        })),
        links: [],
      },
    },
  );
  if (!mandateRes.ok()) {
    throw new Error(
      `PUT mandates failed (${mandateRes.status()}): ${await mandateRes.text()}`,
    );
  }

  for (let i = 0; i < buyTargets.length; i++) {
    const instrument = buyTargets[i]!;
    const tradeRes = await request.post(
      new URL("/api/portfolio/trade", baseURL).toString(),
      {
        headers: { "X-Account-Id": accountId },
        data: {
          instrumentId: instrument.id,
          type: "buy",
          quantity: 5,
          price: 50 + i * 5,
          idempotencyKey: `e2e-v173-${suffix}-${i}`,
        },
      },
    );
    if (!tradeRes.ok()) {
      throw new Error(
        `POST /api/portfolio/trade failed for ${instrument.symbol} (${tradeRes.status()}): ${await tradeRes.text()}.`,
      );
    }
  }

  const portfolioRes = await request.get(
    new URL("/api/portfolio", baseURL).toString(),
    { headers: { "X-Account-Id": accountId } },
  );
  if (!portfolioRes.ok()) {
    throw new Error(
      `GET /api/portfolio after buys failed (${portfolioRes.status()}): ${await portfolioRes.text()}`,
    );
  }
  const portfolioJson = (await portfolioRes.json()) as {
    data?: { positions?: PortfolioPositionRow[] };
  };
  const positions = portfolioJson.data?.positions ?? [];
  const instruments: MercadoInstrumentSlice[] = buyTargets.map((target) => {
    const seeded = positions.find((row) => row.instrumentId === target.id);
    if (!seeded) {
      throw new Error(
        `Portfolio buy seed missing open position for ${target.symbol}.`,
      );
    }
    return sliceFromPortfolioPosition(seeded, target.symbol);
  });
  if (instruments.length < 3) {
    throw new Error(
      `Multi-instrument fixture expected ≥3 open positions (got ${instruments.length}).`,
    );
  }

  const workspaceDocument = mercadoListFocusWorkspaceDocument({
    instrumentId: instruments[0]!.instrumentId,
    symbol: instruments[0]!.symbol,
    name: `E2E Mercado Multi ${suffix}`,
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

  return {
    accountId,
    workspaceId,
    instruments,
    entryOnly: entryTarget
      ? { instrumentId: entryTarget.id, symbol: entryTarget.symbol }
      : null,
    workspaceDocument: { ...workspaceDocument, id: workspaceId },
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
export const E2E_PAPER_DAY_ACCOUNT_PREFIX = "e2e-v174";

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

/** Posición AAPL con T1 alcanzado (lastPrice ≥ target1) para día autónomo mock. */
export function paperAutonomousDayT1Position() {
  const avgCost = 100;
  const target1 = 105;
  return mercadoOpenPosition({
    id: "pos-e2e-day-aapl",
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    name: "Apple E2E",
    tradePlanId: "tp-e2e-day-aapl",
    avgCost,
    lastPrice: target1 + 1,
    currentStop: 95,
    target1,
    target2: 110,
  });
}

export type PaperAutonomousDaySlice = {
  instrumentId: string;
  symbol: string;
  positionId: string;
  tradePlanId: string;
  levels: MercadoLevels;
};

/** Identidad activa del día mock (AAPL T1). */
export function paperAutonomousDaySlice(): PaperAutonomousDaySlice {
  const pos = paperAutonomousDayT1Position();
  return {
    instrumentId: pos.instrumentId,
    symbol: pos.symbol,
    positionId: pos.operational.operationalView.positionId,
    tradePlanId: pos.operational.tradePlanId,
    levels: pos.operational.operationalView.levels,
  };
}

/** autoDesk V1.74 — Estudio→ranking→TradePlan→OpeningGate (dryRun, sin execute). */
export function paperAutonomousDayAutoDesk(accountId = E2E_ACCOUNT_ID) {
  const candidates = [
    {
      decisionId: "dec-e2e-msft-day",
      instrumentId: "inst-msft",
      rank: 1,
      score: 8.2,
      symbol: "MSFT",
      autoSource: "estudio_ranking",
      templateId: "moderate",
      tradePlan: {
        decisionId: "dec-e2e-msft-day",
        instrumentId: "inst-msft",
        direction: "long" as const,
        status: "ARMED" as const,
        quantity: 10,
        riskPct: 0.5,
        whyNot: [],
        executionAllowed: true,
        entry: 420,
        structuralStop: 400,
        target1: 440,
        target2: 460,
      },
      entry: 420,
      structuralStop: 400,
      target1: 440,
      target2: 460,
    },
    {
      decisionId: "dec-e2e-nvda-skip",
      instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
      rank: 2,
      score: 7.1,
      symbol: E2E_ENTRY_ONLY_INSTRUMENT.symbol,
      reasonCode: "ENTRY_NO_TRIGGER" as const,
      humanMessage: "Sin disparador — ranking ≠ BUY.",
      tradePlan: {
        decisionId: "dec-e2e-nvda-skip",
        instrumentId: E2E_ENTRY_ONLY_INSTRUMENT.id,
        direction: "long" as const,
        status: "ARMED" as const,
        quantity: 5,
        riskPct: 0.5,
        whyNot: ["no_trigger"],
        executionAllowed: false,
        entry: 118,
        structuralStop: 110,
        target1: 130,
        target2: 140,
      },
    },
  ];

  const base = buildPaperDailyReport({
    accountId,
    asOf: "2026-09-02",
    dryRun: true,
    paperDExecute: false,
    entry: {
      status: "dry_run",
      proposedCount: candidates.length,
      executedCount: 0,
    },
    positions: [
      {
        instrumentId: E2E_INSTRUMENT_ID,
        status: "held",
        decisionVerdict: "REDUCE",
        nextAction: "REDUCE",
        operatingState: "T1_READY",
      },
    ],
    notes: [
      "dryRun=true — cadena Estudio→ranking→TradePlan→OpeningGate (E2E V1.74).",
      "AUTO armado · PAPER_D_EXECUTE off — sin ejecución ledger.",
    ],
  });

  return {
    ...base,
    entry: {
      ...base.entry,
      candidates,
      skipped: [],
    },
  };
}

/** DailyOps envelope mínimo para GET /paper-desk/daily-report mock. */
export function paperAutonomousDayDailyOpsEnvelope(accountId = E2E_ACCOUNT_ID) {
  const autoDesk = paperAutonomousDayAutoDesk(accountId);
  return {
    schemaVersion: "daily_ops_report_v1",
    asOf: "2026-09-02",
    generatedAt: "2026-09-02T12:00:00.000Z",
    accountId,
    summary: {
      accountId,
      cash: 100_000,
      totalEquity: 101_060,
      openPositions: 1,
      dayPnl: 60,
      dayPnlPct: 0.06,
    },
    ledgerToday: [],
    tradesToday: [],
    week: [],
    f3PendingCount: 0,
    channels: { alarma: 0, aviso: 0, none: 0 },
    opinions: [],
    notes: autoDesk.notes,
    estudioStatus: "ok",
    estudioCount: 3,
    autoDesk,
  };
}

/** Seed Hoy + AUTO armado + workspace Mercado (AAPL) para journey día mock. */
export async function seedPaperDayBrowserState(
  page: Page,
  opts?: {
    accountId?: string;
    workspaceDocument?: ReturnType<typeof mercadoListFocusWorkspaceDocument>;
  },
): Promise<void> {
  const accountId = opts?.accountId ?? E2E_ACCOUNT_ID;
  const slice = paperAutonomousDaySlice();
  const workspaceDocument =
    opts?.workspaceDocument ??
    mercadoListFocusWorkspaceDocument({
      instrumentId: slice.instrumentId,
      symbol: slice.symbol,
      name: "E2E Paper Day",
    });
  const workspaceId = workspaceDocument.id || E2E_WORKSPACE_ID;
  const chartPersistBackup = chartPersistBackupFromWorkspace(workspaceDocument);

  await page.addInitScript(
    ({ accountId, workspaceId, chartPersistBackup, workspaceDocument }) => {
      localStorage.setItem(
        "bolsa-active-account",
        JSON.stringify({ state: { activeAccountId: accountId }, version: 0 }),
      );
      localStorage.setItem(
        "bolsa-demo-book-auto-arm-v1",
        JSON.stringify({
          armed: true,
          armedAt: "2026-09-02T08:00:00.000Z",
          confirmPhrase: "ACTIVAR AUTO",
        }),
      );
      localStorage.setItem(
        "bolsa-demo-book-prefs-v1",
        JSON.stringify({
          mode: "auto",
          maxOpenPositions: 10,
          defaultSizePctOfCash: 10,
          countryPrefer: "home_first",
        }),
      );
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
      localStorage.setItem(
        "bolsa-trading-layout-v1",
        JSON.stringify({
          state: {
            operativaOpen: true,
            chartsOpen: true,
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
          },
          version: 0,
        }),
      );
      void workspaceDocument;
    },
    { accountId, workspaceId, chartPersistBackup, workspaceDocument },
  );
}

/** V1.75 — candidato ENTRY_STALE_DATA (deny honesto ≠ 0 oportunidades silenciosas). */
export function staleNoExecuteStaleCandidate() {
  return {
    decisionId: "dec-e2e-msft-stale",
    instrumentId: "inst-msft",
    rank: 1,
    score: 8.2,
    symbol: "MSFT",
    autoSource: "estudio_ranking",
    templateId: "moderate",
    freshness: "stale" as const,
    reasonCode: "ENTRY_STALE_DATA" as const,
    humanMessage: "Datos obsoletos — no proponer.",
    vetoes: ["data_freshness:stale"],
    tradePlan: {
      decisionId: "dec-e2e-msft-stale",
      instrumentId: "inst-msft",
      direction: "long" as const,
      status: "ARMED" as const,
      quantity: 10,
      riskPct: 0.5,
      whyNot: [],
      executionAllowed: false,
      entry: 420,
      structuralStop: 400,
      target1: 440,
      target2: 460,
    },
    entry: 420,
    structuralStop: 400,
    target1: 440,
    target2: 460,
  };
}

/** autoDesk V1.75 — stale deny + dryRun · sin execute. */
export function staleNoExecuteAutoDesk(accountId = E2E_ACCOUNT_ID) {
  const candidates = [staleNoExecuteStaleCandidate()];
  const base = buildPaperDailyReport({
    accountId,
    asOf: "2026-09-02",
    dryRun: true,
    paperDExecute: false,
    entry: {
      status: "dry_run",
      proposedCount: candidates.length,
      executedCount: 0,
    },
    positions: [
      {
        instrumentId: E2E_INSTRUMENT_ID,
        status: "held",
        reason: "data_stale",
        decisionVerdict: "HOLD",
        nextAction: "REVISAR_DATOS_NO_FRESCOS",
        operatingState: "OPEN",
      },
    ],
    notes: [
      "dryRun=true — V1.75 stale → no-execute.",
      "ENTRY_STALE_DATA · AUTO armado · PAPER_D_EXECUTE off.",
    ],
  });

  return {
    ...base,
    entry: {
      ...base.entry,
      candidates,
      skipped: [],
    },
  };
}

/** DailyOps envelope mock para GET /paper-desk/daily-report (stale). */
export function staleNoExecuteDailyOpsEnvelope(accountId = E2E_ACCOUNT_ID) {
  const autoDesk = staleNoExecuteAutoDesk(accountId);
  return {
    schemaVersion: "daily_ops_report_v1",
    asOf: "2026-09-02",
    generatedAt: "2026-09-02T12:00:00.000Z",
    accountId,
    summary: {
      accountId,
      cash: 100_000,
      totalEquity: 101_060,
      openPositions: 1,
      dayPnl: 60,
      dayPnlPct: 0.06,
    },
    ledgerToday: [],
    tradesToday: [],
    week: [],
    f3PendingCount: 0,
    channels: { alarma: 0, aviso: 0, none: 0 },
    opinions: [],
    notes: autoDesk.notes,
    estudioStatus: "ok",
    estudioCount: 2,
    autoDesk,
  };
}

/** SubmitIntent send_attempted → ExecutionState UNKNOWN (OR-2). */
export function staleNoExecuteUnknownSubmitIntent(accountId = E2E_ACCOUNT_ID) {
  return {
    decisionId: "dec-e2e-aapl-unknown",
    intentId: "intent-e2e-aapl-unknown",
    orderId: "ord-e2e-aapl-unknown",
    accountId,
    phase: "send_attempted" as const,
    venueOrderId: null,
    reason: "crash_before_venue_ack",
    venue: "paper",
    sendAttemptedAt: "2026-09-02T11:55:00.000Z",
    instrumentId: E2E_INSTRUMENT_ID,
  };
}

/** Incidente abierto — copy Sin auto-heal (DEX-3). */
export function staleNoExecuteOpenIncident(accountId = E2E_ACCOUNT_ID) {
  return {
    incidentId: "inc-e2e-stale-1",
    accountId,
    kind: "portfolio_drift",
    status: "open",
    snapshot: "portfolio_drift",
    openedAt: "2026-09-02T11:00:00.000Z",
    reviewedAt: null,
    reviewedBy: null,
    resolvedAt: null,
    resolvedBy: null,
    resolutionNote: null,
    clearedAt: null,
  };
}

/** Seed browser state para journey stale/UNKNOWN (reusa armado AUTO). */
export async function seedStaleNoExecuteBrowserState(
  page: Page,
  opts?: {
    accountId?: string;
    workspaceDocument?: ReturnType<typeof mercadoListFocusWorkspaceDocument>;
  },
): Promise<void> {
  await seedPaperDayBrowserState(page, {
    accountId: opts?.accountId,
    workspaceDocument:
      opts?.workspaceDocument ??
      mercadoListFocusWorkspaceDocument({
        instrumentId: E2E_INSTRUMENT_ID,
        symbol: E2E_SYMBOL,
        name: "E2E Stale No-Execute",
      }),
  });
}
