/**
 * Mercado mock builders + browser seed (V1.67+).
 */
import type { Page } from "@playwright/test";
import { DEFAULT_CHART_CONFIG } from "@bolsa/shared";
import {
  E2E_ACCOUNT_ID,
  E2E_ENTRY_ONLY_INSTRUMENT,
  E2E_INSTRUMENT_ID,
  E2E_MULTI_POSITION_INSTRUMENTS,
  E2E_SYMBOL,
  E2E_WORKSPACE_ID,
  type MercadoInstrumentSlice,
  type MercadoLevels,
} from "./ids";

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
        decisionId: null as string | null,
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

export type MercadoOpenPosition = ReturnType<typeof mercadoOpenPosition>;

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

export function chartPersistBackupFromWorkspace(
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

export type PortfolioPositionRow = {
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

export function sliceFromPortfolioPosition(
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
