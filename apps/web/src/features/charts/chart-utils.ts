import type { IndicatorPointDto, OhlcvBarDto } from "@bolsa/shared";
import type { Time } from "lightweight-charts";
import {
  chartPerfRecordReflowEvent,
  chartPerfRecordReflowRequest,
} from "@/features/charts/chart-perf-analyzer";

export interface ChartCandle {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  color?: string;
  borderColor?: string;
  wickColor?: string;
}

export interface ChartVolumeBar {
  time: Time;
  value: number;
  color: string;
}

export const CHART_THEME = {
  upColor: "#22c55e",
  downColor: "#ef4444",
  gridColor: "rgba(148, 163, 184, 0.2)",
  textColor: "#94a3b8",
  volumeUpColor: "rgba(34, 197, 94, 0.5)",
  volumeDownColor: "rgba(239, 68, 68, 0.5)",
  sma20Color: "#38bdf8",
  sma50Color: "#a78bfa",
  ema20Color: "#fbbf24",
} as const;

export function barTimeToChartTime(timestamp: string): Time {
  if (/^\d{4}-\d{2}-\d{2}$/.test(timestamp)) {
    return timestamp;
  }
  const ms = Date.parse(timestamp);
  if (Number.isNaN(ms)) {
    return timestamp;
  }
  return Math.floor(ms / 1000) as Time;
}

export function chartTimeToDate(time: Time): Date {
  if (typeof time === "number") {
    return new Date(time * 1000);
  }
  if (typeof time === "string") {
    if (/^\d{4}-\d{2}-\d{2}$/.test(time)) {
      return new Date(`${time}T12:00:00`);
    }
    return new Date(time);
  }
  return new Date(time.year, time.month - 1, time.day, 12, 0, 0);
}

/** Etiqueta del eje temporal: «jue 18 jun' 26 16:00». */
export function formatChartTimeAxisLabel(
  time: Time,
  showTime: boolean,
): string {
  const date = chartTimeToDate(time);
  const weekday = date
    .toLocaleDateString("es-ES", { weekday: "short" })
    .replace(/\.$/, "")
    .toLowerCase();
  const day = date.getDate();
  const month = date
    .toLocaleDateString("es-ES", { month: "short" })
    .replace(/\.$/, "")
    .toLowerCase();
  const year = String(date.getFullYear()).slice(-2);
  let label = `${weekday} ${day} ${month}' ${year}`;
  if (showTime) {
    const hours = date.toLocaleTimeString("es-ES", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    label += ` ${hours}`;
  }
  return label;
}

export function barsToChartSeries(bars: OhlcvBarDto[]): ChartCandle[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
  }));
}

export function barsToCloseLineSeries(
  bars: OhlcvBarDto[],
): { time: Time; value: number }[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    value: bar.close,
  }));
}

export function barsToTypicalPriceLineSeries(
  bars: OhlcvBarDto[],
): { time: Time; value: number }[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    value: (bar.high + bar.low + bar.close) / 3,
  }));
}

/** Barras HLC: marca de apertura en el cierre (sin mecha de open). */
export function barsToHlcBarSeries(bars: OhlcvBarDto[]): ChartCandle[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    open: bar.close,
    high: bar.high,
    low: bar.low,
    close: bar.close,
  }));
}

/** Rango máx.-mín. como barra vertical low→high. */
export function barsToHighLowBarSeries(bars: OhlcvBarDto[]): ChartCandle[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    open: bar.low,
    high: bar.high,
    low: bar.low,
    close: bar.high,
  }));
}

export function barsToCloseColumnSeries(
  bars: OhlcvBarDto[],
  upColor: string,
  downColor: string,
): { time: Time; value: number; color: string }[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    value: bar.close,
    color: bar.close >= bar.open ? upColor : downColor,
  }));
}

function applyColorAlpha(color: string, alpha: number): string {
  const clamped = Math.min(1, Math.max(0, alpha));
  if (color.startsWith("#") && color.length === 7) {
    const r = Number.parseInt(color.slice(1, 3), 16);
    const g = Number.parseInt(color.slice(3, 5), 16);
    const b = Number.parseInt(color.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${clamped})`;
  }
  return color;
}

/** Heikin-Ashi: transformación OHLC estándar. */
export function barsToHeikinAshiSeries(bars: OhlcvBarDto[]): ChartCandle[] {
  const result: ChartCandle[] = [];
  let prevOpen = 0;
  let prevClose = 0;

  for (let i = 0; i < bars.length; i++) {
    const bar = bars[i]!;
    const haClose = (bar.open + bar.high + bar.low + bar.close) / 4;
    const haOpen =
      i === 0 ? (bar.open + bar.close) / 2 : (prevOpen + prevClose) / 2;
    const haHigh = Math.max(bar.high, haOpen, haClose);
    const haLow = Math.min(bar.low, haOpen, haClose);
    result.push({
      time: barTimeToChartTime(bar.timestamp),
      open: haOpen,
      high: haHigh,
      low: haLow,
      close: haClose,
    });
    prevOpen = haOpen;
    prevClose = haClose;
  }

  return result;
}

/** Velas con intensidad de color según volumen relativo del histórico visible. */
export function barsToVolumeCandleSeries(
  bars: OhlcvBarDto[],
  upColor: string,
  downColor: string,
): ChartCandle[] {
  if (bars.length === 0) return [];

  let minVol = Infinity;
  let maxVol = -Infinity;
  for (const bar of bars) {
    minVol = Math.min(minVol, bar.volume);
    maxVol = Math.max(maxVol, bar.volume);
  }

  return bars.map((bar) => {
    const bullish = bar.close >= bar.open;
    const base = bullish ? upColor : downColor;
    const ratio =
      maxVol > minVol ? (bar.volume - minVol) / (maxVol - minVol) : 1;
    const alpha = 0.28 + 0.72 * ratio;
    const tinted = applyColorAlpha(base, alpha);
    return {
      time: barTimeToChartTime(bar.timestamp),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      color: tinted,
      borderColor: tinted,
      wickColor: tinted,
    };
  });
}

export function barsToVolumeSeries(
  bars: OhlcvBarDto[],
  upColor: string = CHART_THEME.volumeUpColor,
  downColor: string = CHART_THEME.volumeDownColor,
): ChartVolumeBar[] {
  return bars.map((bar) => ({
    time: barTimeToChartTime(bar.timestamp),
    value: bar.volume,
    color: bar.close >= bar.open ? upColor : downColor,
  }));
}

export function indicatorToLineSeries(
  points: IndicatorPointDto[],
  key: "sma20" | "sma50" | "ema20" | "rsi14",
): { time: Time; value: number }[] {
  return points
    .filter((point) => point[key] != null)
    .map((point) => ({
      time: barTimeToChartTime(point.timestamp),
      value: point[key]!,
    }));
}

export function hasChartData(bars: OhlcvBarDto[]): boolean {
  return bars.length > 0;
}

export function summarizeBars(bars: OhlcvBarDto[]) {
  if (bars.length === 0) {
    return { count: 0, first: null, last: null, minLow: null, maxHigh: null };
  }

  let minLow = bars[0]!.low;
  let maxHigh = bars[0]!.high;

  for (const bar of bars) {
    if (bar.low < minLow) minLow = bar.low;
    if (bar.high > maxHigh) maxHigh = bar.high;
  }

  return {
    count: bars.length,
    first: bars[0]!.timestamp,
    last: bars[bars.length - 1]!.timestamp,
    minLow,
    maxHigh,
  };
}

export function formatPrice(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)} €`;
}

/** Precio OHLC en la barra del gráfico (3 decimales, sin símbolo €). */
export function formatChartBarPrice(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(3);
}

export function barIntraChange(
  bar: OhlcvBarDto,
): { delta: number; pct: number } | null {
  if (!bar.open || bar.open === 0) return null;
  const delta = bar.close - bar.open;
  return { delta, pct: (delta / bar.open) * 100 };
}

/** Δ cierre−apertura de la vela: «+0,055 (+0,14 %)». */
export function formatBarIntraChangeLabel(
  bar: OhlcvBarDto,
): { text: string; isUp: boolean } | null {
  const change = barIntraChange(bar);
  if (!change) return null;
  const isUp = change.delta >= 0;
  const deltaSign = change.delta > 0 ? "+" : "";
  const pctSign = change.pct > 0 ? "+" : "";
  return {
    text: `${deltaSign}${change.delta.toFixed(3)} (${pctSign}${change.pct.toFixed(2)}%)`,
    isUp,
  };
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

/** Precio para campos de coordenadas (sin símbolo €, decimales acotados). */
export function formatCoordinatePrice(
  value: number | null | undefined,
  decimals = 4,
): string {
  if (value == null || Number.isNaN(value)) return "";
  return value.toFixed(decimals);
}

export function parseCoordinatePrice(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export const CHART_REFLOW_EVENT = "bolsa:chart-reflow";
export const CHART_ZOOM_EVENT = "bolsa:chart-zoom";

export type ChartZoomAction = "in" | "out" | "reset";

let reflowRaf: number | null = null;

export function requestChartReflow(source?: string) {
  chartPerfRecordReflowRequest(source);
  if (reflowRaf != null) return;
  reflowRaf = requestAnimationFrame(() => {
    reflowRaf = null;
    chartPerfRecordReflowEvent();
    window.dispatchEvent(new CustomEvent(CHART_REFLOW_EVENT));
  });
}

export function requestChartZoom(
  action: ChartZoomAction,
  chartSyncId?: string,
) {
  window.dispatchEvent(
    new CustomEvent(CHART_ZOOM_EVENT, { detail: { action, chartSyncId } }),
  );
}
