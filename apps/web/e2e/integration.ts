/**
 * V1.64 — helpers Playwright: mock vs integración FastAPI+PostgreSQL.
 */

import type { APIRequestContext, Page } from "@playwright/test";
import { DEFAULT_CHART_CONFIG } from "@bolsa/shared";

export const E2E_ACCOUNT_ID = "default-account-seed";
export const E2E_INSTRUMENT_ID = "inst-aapl";
export const E2E_SYMBOL = "AAPL";
export const E2E_WORKSPACE_ID = "ws-e2e-mercado";

export function e2eIntegrationMode(): boolean {
  return process.env.E2E_INTEGRATION === "1";
}

export function e2eMockMode(): boolean {
  return !e2eIntegrationMode();
}

export const E2E_SKIP_INTEGRATION_REASON =
  "Set E2E_INTEGRATION=1 and ensure FastAPI (:8000) + PostgreSQL are running. See spec-v164.";

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

export function mercadoWorkspaceDocument() {
  const tabId = "e2e-tab-mercado";
  return {
    version: 1,
    id: E2E_WORKSPACE_ID,
    name: "E2E Mercado",
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
        instrumentId: E2E_INSTRUMENT_ID,
        label: E2E_SYMBOL,
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

/** Seed cuenta activa + layout DECISIÓN abierto antes de navegar a /trading. */
export async function seedMercadoBrowserState(page: Page): Promise<void> {
  await page.addInitScript(
    ({ accountId }) => {
      const zustand = (key: string, partial: Record<string, unknown>) => {
        localStorage.setItem(
          key,
          JSON.stringify({ state: partial, version: 0 }),
        );
      };
      zustand("bolsa-active-account", { activeAccountId: accountId });
      zustand("bolsa-trading-layout-v1", {
        listsOpen: true,
        chartsOpen: true,
        operationsOpen: false,
        operativaOpen: true,
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
    },
    { accountId: E2E_ACCOUNT_ID },
  );
}
