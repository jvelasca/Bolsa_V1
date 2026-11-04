/**
 * Mercado / gráficos — fixture realista y mocks HTTP para la operativa gráfica.
 *
 * Sustituye el `mercadoOhlcvBars()` plano (30 barras 1D para cualquier timeframe)
 * por series deterministas por resolución, con hueco de mercado, volumen y
 * indicadores alineados 1:1 por timestamp. Además instala un workspace stateful
 * para poder validar persistencia (recarga) sin tocar la BD del usuario.
 */
import type { Page, Route } from "@playwright/test";
import {
  DEFAULT_CHART_CONFIG,
  type ChartDrawing,
  type ChartIndicatorInstance,
  type ChartSeriesType,
  type ChartTimeframe,
  type IndicatorPointDto,
  type InstrumentDataStatusDto,
  type OhlcvBarDto,
} from "@bolsa/shared";
import { installMercadoApiMocks } from "./e2e-mock-installers";
import { jsonResponse } from "./e2e-mock-routes";
import {
  getMercadoMockWorkspaceDocument,
  setMercadoMockWorkspaceDocument,
} from "./e2e-mock-runtime";
import { mercadoWorkspaceDocument } from "./mercado";
import { E2E_INSTRUMENT_ID, E2E_SYMBOL, E2E_WORKSPACE_ID } from "./ids";

export const CHART_E2E_SECOND_INSTRUMENT = {
  id: "inst-msft",
  symbol: "MSFT",
  name: "Microsoft E2E",
} as const;

export type ChartMarketMode = "ok" | "empty" | "error" | "slow";
export type ChartMarketFreshness =
  | "current"
  | "gap_detected"
  | "stale"
  | "error";

export type ChartMarketFixtureOptions = {
  mode?: ChartMarketMode;
  /** Fuerza el estado de `/data-status` (por defecto `current`). */
  freshness?: ChartMarketFreshness;
  /** `two` añade una pestaña MSFT para probar aislamiento de dibujos. */
  tabs?: "one" | "two";
  seriesType?: ChartSeriesType;
  timeframe?: ChartTimeframe;
  drawings?: ChartDrawing[];
  indicatorInstances?: ChartIndicatorInstance[];
  /** Retardo del modo `slow` antes de responder OHLCV (ms). */
  slowDelayMs?: number;
};

/** Overlay SMA + subpanel RSI para certificar el reflow de indicadores. */
export function chartMarketIndicatorInstances(): ChartIndicatorInstance[] {
  return [
    {
      instanceId: "e2e-ind-sma",
      definitionId: "sma",
      parameters: { period: 20 },
      visible: true,
    },
    {
      instanceId: "e2e-ind-rsi",
      definitionId: "rsi",
      parameters: { period: 14 },
      visible: true,
    },
  ];
}

export type ChartMarketFixture = {
  instrumentId: string;
  symbol: string;
  workspaceId: string;
  mode: ChartMarketMode;
  freshness: ChartMarketFreshness;
  barsByTimeframe: Record<string, OhlcvBarDto[]>;
  indicatorsByTimeframe: Record<string, IndicatorPointDto[]>;
  statusByTimeframe: Record<string, InstrumentDataStatusDto>;
};

const DAILY_GAP_START = "2026-09-14";
const DAILY_GAP_END = "2026-09-25";
const CHART_TIMEFRAMES: ChartTimeframe[] = [
  "1m",
  "5m",
  "15m",
  "30m",
  "1h",
  "4h",
  "1d",
  "1wk",
  "1mo",
];

function isoDateFromMs(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function businessDaysEndingAt(endIso: string, count: number): string[] {
  const out: string[] = [];
  const cursor = new Date(`${endIso}T00:00:00.000Z`);
  while (out.length < count) {
    const day = cursor.getUTCDay();
    if (day !== 0 && day !== 6) out.push(isoDateFromMs(cursor.getTime()));
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return out.reverse();
}

/** 1D con un hueco real de dos semanas (14→25 sep) para probar gaps. */
function dailyTimestamps(): string[] {
  return businessDaysEndingAt("2026-10-30", 70)
    .filter((day) => day < DAILY_GAP_START || day > DAILY_GAP_END)
    .map((day) => `${day}T00:00:00.000Z`);
}

function weeklyTimestamps(): string[] {
  return businessDaysEndingAt("2026-10-30", 240)
    .filter((day) => new Date(`${day}T00:00:00.000Z`).getUTCDay() === 5)
    .slice(-30)
    .map((day) => `${day}T05:00:00.000Z`);
}

function monthlyTimestamps(): string[] {
  const out: string[] = [];
  for (let month = 0; month < 24; month += 1) {
    const year = 2024 + Math.floor(month / 12);
    const monthIndex = month % 12;
    out.push(new Date(Date.UTC(year, monthIndex, 1, 5, 0, 0)).toISOString());
  }
  return out;
}

/** Sesiones regulares 13:30→20:00 UTC, de la más reciente hacia atrás. */
function intradayTimestamps(count: number, stepMinutes: number): string[] {
  const windowMinutes = 390;
  const perSession = Math.floor(windowMinutes / stepMinutes) + 1;
  const sessionsNeeded = Math.min(
    120,
    Math.max(1, Math.ceil(count / perSession)),
  );
  const sessions: string[][] = [];
  const cursor = new Date(Date.UTC(2026, 9, 30));
  while (sessions.length < sessionsNeeded) {
    const day = cursor.getUTCDay();
    if (day !== 0 && day !== 6) {
      const session: string[] = [];
      const start = Date.UTC(
        cursor.getUTCFullYear(),
        cursor.getUTCMonth(),
        cursor.getUTCDate(),
        13,
        30,
      );
      for (let minute = 0; minute <= windowMinutes; minute += stepMinutes) {
        session.push(new Date(start + minute * 60_000).toISOString());
      }
      sessions.push(session);
    }
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return sessions.reverse().flat().slice(-count);
}

function buildBars(
  timestamps: string[],
  opts?: { basePrice?: number; gapStartIndex?: number },
): OhlcvBarDto[] {
  const basePrice = opts?.basePrice ?? 182;
  let previousClose = basePrice;
  return timestamps.map((timestamp, index) => {
    const drift = index * 0.34 + Math.sin(index / 4.1) * 2.4;
    const open = previousClose + Math.sin(index / 2.3) * 0.65;
    const close = basePrice + drift + Math.cos(index / 5.7) * 1.1;
    const wick = 0.55 + Math.abs(Math.sin(index / 1.9)) * 0.9;
    const high = Math.max(open, close) + wick;
    const low = Math.min(open, close) - wick;
    const gapBoost =
      opts?.gapStartIndex != null && index === opts.gapStartIndex ? 1.8 : 1;
    previousClose = close;
    return {
      timestamp,
      open: round2(open),
      high: round2(high),
      low: round2(low),
      close: round2(close),
      volume: Math.round(
        (920_000 + Math.abs(Math.sin(index / 1.7)) * 1_450_000) * gapBoost,
      ),
      adjClose: round2(close),
      source: "yahoo",
    };
  });
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function sma(values: number[], period: number): (number | null)[] {
  return values.map((_, index) => {
    if (index + 1 < period) return null;
    const slice = values.slice(index + 1 - period, index + 1);
    return round2(slice.reduce((sum, value) => sum + value, 0) / period);
  });
}

function ema(values: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const out: (number | null)[] = [];
  let previous: number | null = null;
  values.forEach((value, index) => {
    if (index + 1 < period) {
      out.push(null);
      return;
    }
    previous = previous == null ? value : value * k + previous * (1 - k);
    out.push(round2(previous));
  });
  return out;
}

function rsi(values: number[], period = 14): (number | null)[] {
  const out: (number | null)[] = [];
  let avgGain: number | null = null;
  let avgLoss: number | null = null;
  values.forEach((value, index) => {
    if (index === 0) {
      out.push(null);
      return;
    }
    const change = value - values[index - 1]!;
    const gain = Math.max(change, 0);
    const loss = Math.max(-change, 0);
    if (index < period) {
      out.push(null);
      return;
    }
    if (avgGain == null || avgLoss == null) {
      const window = values.slice(1, index + 1);
      let gains = 0;
      let losses = 0;
      for (let i = 1; i < window.length; i += 1) {
        const delta = window[i]! - window[i - 1]!;
        gains += Math.max(delta, 0);
        losses += Math.max(-delta, 0);
      }
      avgGain = gains / period;
      avgLoss = losses / period;
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
    }
    if (avgLoss === 0) {
      out.push(100);
      return;
    }
    const rs = avgGain / avgLoss;
    out.push(round2(100 - 100 / (1 + rs)));
  });
  return out;
}

function buildIndicators(bars: OhlcvBarDto[]): IndicatorPointDto[] {
  const closes = bars.map((bar) => bar.close);
  const sma20 = sma(closes, 20);
  const sma50 = sma(closes, 50);
  const ema20 = ema(closes, 20);
  const rsi14 = rsi(closes, 14);
  return bars.map((bar, index) => ({
    timestamp: bar.timestamp,
    sma20: sma20[index] ?? null,
    sma50: sma50[index] ?? null,
    ema20: ema20[index] ?? null,
    rsi14: rsi14[index] ?? null,
  }));
}

function countMissingSessions(bars: OhlcvBarDto[]): number {
  if (bars.length < 2) return 0;
  let gaps = 0;
  for (let index = 1; index < bars.length; index += 1) {
    const previous = new Date(bars[index - 1]!.timestamp);
    const current = new Date(bars[index]!.timestamp);
    const days = Math.round(
      (current.getTime() - previous.getTime()) / 86_400_000,
    );
    if (days > 4) gaps += 1;
  }
  return gaps;
}

function buildStatus(
  timeframe: ChartTimeframe,
  bars: OhlcvBarDto[],
  mode: ChartMarketMode,
  freshness: ChartMarketFreshness,
): InstrumentDataStatusDto {
  const lastBarDate = bars.at(-1)?.timestamp ?? null;
  const empty = mode === "empty" || bars.length === 0;
  const status: InstrumentDataStatusDto["freshnessStatus"] = empty
    ? "empty"
    : mode === "error" || freshness === "error"
      ? "error"
      : freshness;
  return {
    timeframe,
    lastBarDate:
      status === "stale"
        ? (bars.at(-8)?.timestamp ?? lastBarDate)
        : lastBarDate,
    expectedLastBarDate: lastBarDate ?? "2026-10-30T00:00:00.000Z",
    freshnessStatus: status,
    barCount: bars.length,
    lastSyncStatus:
      mode === "error" || freshness === "error" ? "error" : "success",
    lastSyncAt: "2026-10-30T21:10:00.000Z",
    lastSyncError:
      mode === "error" || freshness === "error"
        ? "Yahoo no disponible (E2E)"
        : null,
    sanityWarnings: [],
    gapCount: status === "gap_detected" ? countMissingSessions(bars) : 0,
    xtbVsCloseDeviationPct: 0.42,
    lastXtbQuoteAt: "2026-10-30T20:59:00.000Z",
  };
}

export function buildChartMarketFixture(
  opts?: ChartMarketFixtureOptions,
): ChartMarketFixture {
  const mode = opts?.mode ?? "ok";
  const freshness = opts?.freshness ?? "current";
  const instrumentId = E2E_INSTRUMENT_ID;
  const symbol = E2E_SYMBOL;

  const daily = buildBars(dailyTimestamps(), {
    basePrice: 186,
    gapStartIndex: businessDaysEndingAt("2026-10-30", 70)
      .filter((day) => day < DAILY_GAP_START || day > DAILY_GAP_END)
      .findIndex((day) => day > DAILY_GAP_END),
  });
  const weekly = buildBars(weeklyTimestamps(), { basePrice: 174 });
  const monthly = buildBars(monthlyTimestamps(), { basePrice: 150 });
  const intraday: Record<string, OhlcvBarDto[]> = {
    "1m": buildBars(intradayTimestamps(200, 1), { basePrice: 190 }),
    "5m": buildBars(intradayTimestamps(160, 5), { basePrice: 190 }),
    "15m": buildBars(intradayTimestamps(120, 15), { basePrice: 190 }),
    "30m": buildBars(intradayTimestamps(90, 30), { basePrice: 189 }),
    "1h": buildBars(intradayTimestamps(72, 60), { basePrice: 188 }),
    "4h": buildBars(intradayTimestamps(48, 240), { basePrice: 187 }),
  };

  const barsByTimeframe: Record<string, OhlcvBarDto[]> = {
    "1d": mode === "empty" ? [] : daily,
    "1wk": mode === "empty" ? [] : weekly,
    "1mo": mode === "empty" ? [] : monthly,
    ...Object.fromEntries(
      Object.entries(intraday).map(([tf, bars]) => [
        tf,
        mode === "empty" ? [] : bars,
      ]),
    ),
  };

  const indicatorsByTimeframe: Record<string, IndicatorPointDto[]> =
    Object.fromEntries(
      CHART_TIMEFRAMES.map((timeframe) => [
        timeframe,
        buildIndicators(barsByTimeframe[timeframe] ?? []),
      ]),
    );

  const statusByTimeframe: Record<string, InstrumentDataStatusDto> =
    Object.fromEntries(
      CHART_TIMEFRAMES.map((timeframe) => [
        timeframe,
        buildStatus(
          timeframe,
          barsByTimeframe[timeframe] ?? [],
          mode,
          freshness,
        ),
      ]),
    );

  return {
    instrumentId,
    symbol,
    workspaceId: E2E_WORKSPACE_ID,
    mode,
    freshness,
    barsByTimeframe,
    indicatorsByTimeframe,
    statusByTimeframe,
  };
}

export function chartMarketWorkspaceDocument(
  opts?: ChartMarketFixtureOptions,
): ReturnType<typeof mercadoWorkspaceDocument> {
  const fixture = buildChartMarketFixture(opts);
  const base = mercadoWorkspaceDocument();
  const timeframe = opts?.timeframe ?? "1d";
  const seriesType = opts?.seriesType ?? "candles";
  const charts = [
    {
      id: "e2e-tab-mercado",
      instrumentId: fixture.instrumentId,
      label: fixture.symbol,
      timeframe,
      seriesType,
      chart: DEFAULT_CHART_CONFIG,
      indicatorInstances: opts?.indicatorInstances ?? [],
      drawings: opts?.drawings ?? [],
    },
  ];
  if ((opts?.tabs ?? "one") === "two") {
    charts.push({
      id: "e2e-tab-mercado-msft",
      instrumentId: CHART_E2E_SECOND_INSTRUMENT.id,
      label: CHART_E2E_SECOND_INSTRUMENT.symbol,
      timeframe,
      seriesType,
      chart: DEFAULT_CHART_CONFIG,
      indicatorInstances: opts?.indicatorInstances ?? [],
      drawings: [],
    });
  }
  return {
    ...base,
    charts,
    activeChartId: charts[0]!.id,
    chartToolbarGlobal: {
      ...base.chartToolbarGlobal,
      activeDrawTool: "select",
      drawToolFavorites: ["line", "horizontal"],
      timeframeFavorites: ["1d", "1wk"],
      seriesTypeFavorites: ["candles", "line"],
    },
  };
}

function timeframeFromUrl(url: string): ChartTimeframe {
  try {
    const value = new URL(url).searchParams.get("timeframe");
    return (value ?? "1d") as ChartTimeframe;
  } catch {
    return "1d";
  }
}

function pathnameOf(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill(jsonResponse(body, status));
}

/**
 * Instala el stack mock de MERCADO y encima las rutas gráficas ricas.
 * Devuelve el fixture para que los specs calculen expectativas.
 */
export async function installChartMarketMocks(
  page: Page,
  opts?: ChartMarketFixtureOptions,
): Promise<ChartMarketFixture> {
  const fixture = buildChartMarketFixture(opts);
  const workspaceDocument = chartMarketWorkspaceDocument(opts);
  setMercadoMockWorkspaceDocument(workspaceDocument);

  // Base: workspace, catálogo, listas, posiciones y todo lo no gráfico.
  await installMercadoApiMocks(page);

  // Workspace stateful (PUT guarda el documento → recarga = persistencia real).
  await page.route(
    /\/api\/workspaces\/[^/]+(\/charts\/close)?$/,
    async (route) => {
      const request = route.request();
      const method = request.method().toUpperCase();
      const path = pathnameOf(request.url());
      if (method === "PUT") {
        const body = (request.postDataJSON() ?? {}) as {
          document?: unknown;
          name?: string;
        };
        if (body.document) {
          setMercadoMockWorkspaceDocument(
            body.document as ReturnType<typeof mercadoWorkspaceDocument>,
          );
        }
        await fulfillJson(route, { data: { ok: true } });
        return;
      }
      if (method === "POST" && path.endsWith("/charts/close")) {
        await fulfillJson(route, { data: { ok: true } });
        return;
      }
      const current = getMercadoMockWorkspaceDocument() ?? workspaceDocument;
      const doc = current as unknown as Record<string, unknown>;
      await fulfillJson(route, {
        data: {
          id: fixture.workspaceId,
          name: "E2E Mercado",
          isDefault: true,
          updatedAt: current.updatedAt,
          document: { ...doc, id: fixture.workspaceId },
          dockLayout: null,
        },
      });
    },
  );

  await page.route(/\/api\/instruments\/[^/]+\/ohlcv/, async (route) => {
    const timeframe = timeframeFromUrl(route.request().url());
    if (fixture.mode === "error") {
      await fulfillJson(route, { detail: "Yahoo no disponible (E2E)" }, 500);
      return;
    }
    if (fixture.mode === "slow") {
      await new Promise((resolve) =>
        setTimeout(resolve, opts?.slowDelayMs ?? 1_200),
      );
    }
    const bars = fixture.barsByTimeframe[timeframe] ?? [];
    await fulfillJson(route, {
      data: bars,
      meta: { timeframe, count: bars.length },
    });
  });

  await page.route(/\/api\/instruments\/[^/]+\/indicators/, async (route) => {
    const timeframe = timeframeFromUrl(route.request().url());
    if (fixture.mode === "error") {
      await fulfillJson(
        route,
        { detail: "Indicadores no disponibles (E2E)" },
        500,
      );
      return;
    }
    const points = fixture.indicatorsByTimeframe[timeframe] ?? [];
    await fulfillJson(route, {
      data: points,
      meta: {
        timeframe,
        count: points.length,
        indicators: ["sma20", "sma50", "ema20", "rsi14"],
        signals: { rsiZone: "neutral", smaCross: "bullish" },
      },
    });
  });

  await page.route(/\/api\/instruments\/[^/]+\/data-status/, async (route) => {
    const timeframe = timeframeFromUrl(route.request().url());
    const status =
      fixture.statusByTimeframe[timeframe] ?? fixture.statusByTimeframe["1d"]!;
    await fulfillJson(route, { data: status });
  });

  await page.route(/\/api\/instruments\/[^/]+\/sync/, async (route) => {
    const bars = fixture.barsByTimeframe["1d"] ?? [];
    await fulfillJson(route, {
      data: {
        synced: true,
        barCount: bars.length,
        lastBarDate: bars.at(-1)?.timestamp ?? null,
      },
    });
  });

  return fixture;
}
