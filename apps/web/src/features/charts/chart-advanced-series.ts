import type { ChartSeriesTypeParams, OhlcvBarDto } from "@bolsa/shared";
import type { Time } from "lightweight-charts";
import {
  type ChartCandle,
  barTimeToChartTime,
} from "@/features/charts/chart-utils";

export const DEFAULT_LINE_BREAK_LINES = 3;
export const DEFAULT_POINT_AND_FIGURE_REVERSAL = 3;
export const DEFAULT_KAGI_REVERSAL_PCT = 4;

function averageClose(bars: OhlcvBarDto[]): number {
  if (bars.length === 0) return 1;
  let sum = 0;
  for (const bar of bars) sum += bar.close;
  return sum / bars.length;
}

/** Tamaño de caja/ladrillo automático (~0,5 % del precio medio). */
export function defaultPriceBoxSize(bars: OhlcvBarDto[]): number {
  const avg = averageClose(bars);
  return Math.max(0.01, Number((avg * 0.005).toFixed(4)));
}

export function resolveRenkoBrickSize(
  bars: OhlcvBarDto[],
  params?: ChartSeriesTypeParams,
): number {
  const raw = params?.renkoBrickSize;
  if (raw != null && raw > 0) return raw;
  return defaultPriceBoxSize(bars);
}

export function resolvePointAndFigureBox(
  bars: OhlcvBarDto[],
  params?: ChartSeriesTypeParams,
): number {
  const raw = params?.pointAndFigureBox;
  if (raw != null && raw > 0) return raw;
  return defaultPriceBoxSize(bars);
}

export function resolvePointAndFigureReversal(
  params?: ChartSeriesTypeParams,
): number {
  const raw = params?.pointAndFigureReversal;
  return raw != null && raw >= 1
    ? Math.floor(raw)
    : DEFAULT_POINT_AND_FIGURE_REVERSAL;
}

export function resolveLineBreakLines(params?: ChartSeriesTypeParams): number {
  const raw = params?.lineBreakLines;
  return raw != null && raw >= 1 ? Math.floor(raw) : DEFAULT_LINE_BREAK_LINES;
}

export function resolveKagiReversalPct(params?: ChartSeriesTypeParams): number {
  const raw = params?.kagiReversal;
  return raw != null && raw > 0 ? raw : DEFAULT_KAGI_REVERSAL_PCT;
}

/** Asigna tiempos a lo largo del histórico OHLC (no comprimidos al inicio). */
class SyntheticTimeAssigner {
  private lastBarIndex = -1;
  private seq = 0;
  private lastUnix = -Infinity;

  constructor(private bars: OhlcvBarDto[]) {}

  at(barIndex: number): Time {
    if (barIndex !== this.lastBarIndex) {
      this.lastBarIndex = barIndex;
      this.seq = 0;
    } else {
      this.seq++;
    }

    const base = barTimeToChartTime(this.bars[barIndex]!.timestamp);
    let unix =
      typeof base === "string"
        ? Math.floor(Date.parse(base) / 1000) + this.seq
        : (base as number) + this.seq;

    if (unix <= this.lastUnix) {
      unix = this.lastUnix + 1;
    }
    this.lastUnix = unix;
    return unix as Time;
  }
}

function pushCandle(
  result: ChartCandle[],
  time: Time,
  open: number,
  close: number,
  upColor: string,
  downColor: string,
) {
  const bullish = close >= open;
  const color = bullish ? upColor : downColor;
  result.push({
    time,
    open,
    high: Math.max(open, close),
    low: Math.min(open, close),
    close,
    color,
    borderColor: color,
    wickColor: color,
  });
}

/** Renko clásico: reversión a 2 ladrillos. */
export function barsToRenkoSeries(
  bars: OhlcvBarDto[],
  brickSize: number,
  upColor: string,
  downColor: string,
): ChartCandle[] {
  if (bars.length === 0 || brickSize <= 0) return [];

  const result: ChartCandle[] = [];
  const nextTime = new SyntheticTimeAssigner(bars);

  let brickClose = Math.round(bars[0]!.close / brickSize) * brickSize;
  let direction: 1 | -1 | 0 = 0;

  for (let i = 1; i < bars.length; i++) {
    const price = bars[i]!.close;

    if (direction >= 0) {
      while (price >= brickClose + brickSize) {
        const open = brickClose;
        brickClose += brickSize;
        pushCandle(
          result,
          nextTime.at(i),
          open,
          brickClose,
          upColor,
          downColor,
        );
        direction = 1;
      }
      if (direction === 1 && price <= brickClose - 2 * brickSize) {
        direction = -1;
        while (price <= brickClose - brickSize) {
          const open = brickClose;
          brickClose -= brickSize;
          pushCandle(
            result,
            nextTime.at(i),
            open,
            brickClose,
            upColor,
            downColor,
          );
        }
      }
    }

    if (direction <= 0) {
      while (price <= brickClose - brickSize) {
        const open = brickClose;
        brickClose -= brickSize;
        pushCandle(
          result,
          nextTime.at(i),
          open,
          brickClose,
          upColor,
          downColor,
        );
        direction = -1;
      }
      if (direction === -1 && price >= brickClose + 2 * brickSize) {
        direction = 1;
        while (price >= brickClose + brickSize) {
          const open = brickClose;
          brickClose += brickSize;
          pushCandle(
            result,
            nextTime.at(i),
            open,
            brickClose,
            upColor,
            downColor,
          );
        }
      }
    }
  }

  if (result.length === 0) {
    const open = brickClose - (direction === -1 ? brickSize : 0);
    const close =
      direction === -1
        ? brickClose
        : brickClose + (direction === 1 ? 0 : brickSize);
    pushCandle(
      result,
      nextTime.at(0),
      open,
      close || bars[0]!.close,
      upColor,
      downColor,
    );
  }

  return result;
}

interface LineBreakBlock {
  open: number;
  close: number;
  high: number;
  low: number;
  bullish: boolean;
}

/** Ruptura de línea (N-line break). */
export function barsToLineBreakSeries(
  bars: OhlcvBarDto[],
  lineCount: number,
  upColor: string,
  downColor: string,
): ChartCandle[] {
  if (bars.length === 0 || lineCount < 1) return [];

  const result: ChartCandle[] = [];
  const nextTime = new SyntheticTimeAssigner(bars);
  const blocks: LineBreakBlock[] = [];

  const first = bars[0]!;
  blocks.push({
    open: first.open,
    close: first.close,
    high: first.high,
    low: first.low,
    bullish: first.close >= first.open,
  });
  pushCandle(
    result,
    nextTime.at(0),
    first.open,
    first.close,
    upColor,
    downColor,
  );

  for (let i = 1; i < bars.length; i++) {
    const close = bars[i]!.close;
    const recent = blocks.slice(-lineCount);
    const refHigh = Math.max(...recent.map((b) => b.high));
    const refLow = Math.min(...recent.map((b) => b.low));
    const last = blocks[blocks.length - 1]!;

    if (close > refHigh) {
      if (last.bullish) {
        last.close = close;
        last.high = Math.max(last.high, close);
        result[result.length - 1] = {
          time: result[result.length - 1]!.time,
          open: last.open,
          high: last.high,
          low: last.low,
          close,
          color: upColor,
          borderColor: upColor,
          wickColor: upColor,
        };
      } else {
        blocks.push({
          open: last.close,
          close,
          high: close,
          low: last.close,
          bullish: true,
        });
        pushCandle(
          result,
          nextTime.at(i),
          last.close,
          close,
          upColor,
          downColor,
        );
      }
    } else if (close < refLow) {
      if (!last.bullish) {
        last.close = close;
        last.low = Math.min(last.low, close);
        result[result.length - 1] = {
          time: result[result.length - 1]!.time,
          open: last.open,
          high: last.high,
          low: last.low,
          close,
          color: downColor,
          borderColor: downColor,
          wickColor: downColor,
        };
      } else {
        blocks.push({
          open: last.close,
          close,
          high: last.close,
          low: close,
          bullish: false,
        });
        pushCandle(
          result,
          nextTime.at(i),
          last.close,
          close,
          upColor,
          downColor,
        );
      }
    } else if (last.bullish && close > last.close) {
      last.close = close;
      last.high = Math.max(last.high, close);
      result[result.length - 1] = {
        time: result[result.length - 1]!.time,
        open: last.open,
        high: last.high,
        low: last.low,
        close,
        color: upColor,
        borderColor: upColor,
        wickColor: upColor,
      };
    } else if (!last.bullish && close < last.close) {
      last.close = close;
      last.low = Math.min(last.low, close);
      result[result.length - 1] = {
        time: result[result.length - 1]!.time,
        open: last.open,
        high: last.high,
        low: last.low,
        close,
        color: downColor,
        borderColor: downColor,
        wickColor: downColor,
      };
    }
  }

  return result;
}

/** Kagi: grosor/color según tendencia; reversión en % del precio. */
export function barsToKagiSeries(
  bars: OhlcvBarDto[],
  reversalPct: number,
  upColor: string,
  downColor: string,
): ChartCandle[] {
  if (bars.length === 0 || reversalPct <= 0) return [];

  const result: ChartCandle[] = [];
  const nextTime = new SyntheticTimeAssigner(bars);

  let direction: 1 | -1 = 1;
  let extreme = bars[0]!.close;
  let legStart = bars[0]!.close;
  let legBarIndex = 0;

  const reversalAt = (ref: number) => ref * (reversalPct / 100);

  for (let i = 1; i < bars.length; i++) {
    const close = bars[i]!.close;

    if (direction === 1) {
      if (close >= extreme) {
        extreme = close;
        continue;
      }
      if (extreme - close >= reversalAt(extreme)) {
        pushCandle(
          result,
          nextTime.at(legBarIndex),
          legStart,
          extreme,
          upColor,
          downColor,
        );
        direction = -1;
        legStart = extreme;
        extreme = close;
        legBarIndex = i;
      }
    } else if (close <= extreme) {
      extreme = close;
    } else if (close - extreme >= reversalAt(extreme)) {
      pushCandle(
        result,
        nextTime.at(legBarIndex),
        legStart,
        extreme,
        upColor,
        downColor,
      );
      direction = 1;
      legStart = extreme;
      extreme = close;
      legBarIndex = i;
    }
  }

  pushCandle(
    result,
    nextTime.at(legBarIndex),
    legStart,
    extreme,
    upColor,
    downColor,
  );
  return result;
}

interface PnfState {
  bullish: boolean;
  high: number;
  low: number;
}

/** Punto y figura: columnas de cajas renderizadas como velas apiladas. */
export function barsToPointAndFigureSeries(
  bars: OhlcvBarDto[],
  boxSize: number,
  reversalBoxes: number,
  upColor: string,
  downColor: string,
): ChartCandle[] {
  if (bars.length === 0 || boxSize <= 0 || reversalBoxes < 1) return [];

  const result: ChartCandle[] = [];
  const nextTime = new SyntheticTimeAssigner(bars);

  const base = Math.floor(bars[0]!.close / boxSize) * boxSize;
  let state: PnfState = { bullish: true, high: base + boxSize, low: base };
  pushCandle(result, nextTime.at(0), base, base + boxSize, upColor, downColor);

  for (let i = 1; i < bars.length; i++) {
    const price = bars[i]!.close;

    if (state.bullish) {
      while (price >= state.high + boxSize) {
        const open = state.high;
        state.high += boxSize;
        pushCandle(
          result,
          nextTime.at(i),
          open,
          state.high,
          upColor,
          downColor,
        );
      }
      if (price <= state.high - reversalBoxes * boxSize) {
        state = { bullish: false, high: state.high, low: state.high - boxSize };
        while (price <= state.low - boxSize) {
          const open = state.low;
          state.low -= boxSize;
          pushCandle(
            result,
            nextTime.at(i),
            open,
            state.low,
            upColor,
            downColor,
          );
        }
      }
    } else {
      while (price <= state.low - boxSize) {
        const open = state.low;
        state.low -= boxSize;
        pushCandle(result, nextTime.at(i), open, state.low, upColor, downColor);
      }
      if (price >= state.low + reversalBoxes * boxSize) {
        state = { bullish: true, low: state.low, high: state.low + boxSize };
        while (price >= state.high + boxSize) {
          const open = state.high;
          state.high += boxSize;
          pushCandle(
            result,
            nextTime.at(i),
            open,
            state.high,
            upColor,
            downColor,
          );
        }
      }
    }
  }

  return result;
}
