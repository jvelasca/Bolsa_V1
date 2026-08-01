import type { OhlcvBarDto } from './types.js';

export interface TechnicalRatingBreakdownPoint {
  trend: number;
  momentum: number;
  volatility: number;
  meanReversion: number;
  pattern: number;
  total: number;
}

function clamp(value: number, low = 0, high = 100): number {
  return Math.max(low, Math.min(high, value));
}

function computeSma(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j += 1) sum += closes[j]!;
    out.push(sum / period);
  }
  return out;
}

function computeEma(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  const k = 2 / (period + 1);
  let ema: number | null = null;
  for (let i = 0; i < closes.length; i += 1) {
    const close = closes[i]!;
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    if (ema == null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j += 1) sum += closes[j]!;
      ema = sum / period;
    } else {
      ema = close * k + ema * (1 - k);
    }
    out.push(ema);
  }
  return out;
}

function lastValue(series: (number | null)[]): number | null {
  if (series.length === 0) return null;
  return series[series.length - 1] ?? null;
}

function computeRsi(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [null];
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i < closes.length; i += 1) {
    const change = closes[i]! - closes[i - 1]!;
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    if (i < period) {
      avgGain += gain;
      avgLoss += loss;
      out.push(null);
      continue;
    }
    if (i === period) {
      avgGain = (avgGain + gain) / period;
      avgLoss = (avgLoss + loss) / period;
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
    }
    out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  }
  return out;
}

function computeMacdLine(closes: number[], fast: number, slow: number): (number | null)[] {
  const fastEma = computeEma(closes, fast);
  const slowEma = computeEma(closes, slow);
  return fastEma.map((value, index) =>
    value != null && slowEma[index] != null ? value - slowEma[index]! : null,
  );
}

function computeBollinger(
  closes: number[],
  period: number,
  stdDev: number,
): { upper: (number | null)[]; lower: (number | null)[] } {
  const mid = computeSma(closes, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    const m = mid[i];
    if (m == null || i + 1 < period) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    const slice = closes.slice(i - period + 1, i + 1);
    const variance = slice.reduce((acc, c) => acc + (c - m) ** 2, 0) / period;
    const sd = Math.sqrt(variance);
    upper.push(m + stdDev * sd);
    lower.push(m - stdDev * sd);
  }
  return { upper, lower };
}

function computeAtr(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  let atr: number | null = null;
  for (let i = 0; i < bars.length; i += 1) {
    const bar = bars[i]!;
    const prev = bars[i - 1];
    const tr = prev
      ? Math.max(bar.high - bar.low, Math.abs(bar.high - prev.close), Math.abs(bar.low - prev.close))
      : bar.high - bar.low;
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    if (atr == null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j += 1) {
        const b = bars[j]!;
        const p = bars[j - 1];
        const t = p
          ? Math.max(b.high - b.low, Math.abs(b.high - p.close), Math.abs(b.low - p.close))
          : b.high - b.low;
        sum += t;
      }
      atr = sum / period;
    } else {
      atr = (atr * (period - 1) + tr) / period;
    }
    out.push(atr);
  }
  return out;
}

function computeStochK(bars: OhlcvBarDto[], kPeriod: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    if (i + 1 < kPeriod) {
      out.push(null);
      continue;
    }
    const slice = bars.slice(i - kPeriod + 1, i + 1);
    const low = Math.min(...slice.map((b) => b.low));
    const high = Math.max(...slice.map((b) => b.high));
    const close = bars[i]!.close;
    out.push(high === low ? 50 : ((close - low) / (high - low)) * 100);
  }
  return out;
}

function computeCci(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const tp = bars.map((b) => (b.high + b.low + b.close) / 3);
  const out: (number | null)[] = [];
  for (let i = 0; i < tp.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    const slice = tp.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const md = slice.reduce((a, b) => a + Math.abs(b - mean), 0) / period;
    out.push(md === 0 ? 0 : (tp[i]! - mean) / (0.015 * md));
  }
  return out;
}

function scoreTrend(closes: number[], index: number): number {
  const sma20 = computeSma(closes, 20);
  const sma50 = computeSma(closes, 50);
  const sma200 = computeSma(closes, 200);
  const price = closes[index]!;
  const s20 = sma20[index];
  const s50 = sma50[index];
  const s200 = sma200[index];
  let score = 50;
  if (s20 != null && s50 != null) score += s20 > s50 ? 15 : -15;
  if (s50 != null && s200 != null) score += s50 > s200 ? 15 : -15;
  if (s200 != null) score += price > s200 ? 20 : -20;
  return clamp(score);
}

function scoreMomentum(closes: number[]): number {
  const rsi = lastValue(computeRsi(closes, 14));
  const macd = lastValue(computeMacdLine(closes, 12, 26));
  let score = 50;
  if (rsi != null) {
    if (rsi >= 55) score += Math.min(30, (rsi - 50) * 1.2);
    else if (rsi <= 45) score -= Math.min(30, (50 - rsi) * 1.2);
  }
  if (macd != null) score += macd > 0 ? 20 : -20;
  return clamp(score);
}

function scoreVolatility(bars: OhlcvBarDto[], closes: number[], index: number): number {
  const price = closes[index]!;
  const { upper, lower } = computeBollinger(closes, 20, 2);
  const upperV = upper[index];
  const lowerV = lower[index];
  const atrSeries = computeAtr(bars, 14);
  const atr = atrSeries[index];
  let score = 50;
  if (upperV != null && lowerV != null && upperV > lowerV) {
    const position = (price - lowerV) / (upperV - lowerV);
    if (position >= 0.55) score += 25;
    else if (position <= 0.35) score -= 10;
    else score += 10;
  }
  if (atr != null && index >= 20) {
    const window = closes.slice(index - 19, index + 1);
    const avg = window.reduce((a, b) => a + b, 0) / window.length;
    if (avg > 0) {
      const atrPct = (atr / avg) * 100;
      if (atrPct >= 1 && atrPct <= 4) score += 10;
      else if (atrPct > 6) score -= 10;
    }
  }
  return clamp(score);
}

function scoreMeanReversion(bars: OhlcvBarDto[], closes: number[]): number {
  const stoch = lastValue(computeStochK(bars, 14));
  const cci = lastValue(computeCci(bars, 20));
  let score = 50;
  if (stoch != null) {
    if (stoch >= 40 && stoch <= 60) score += 10;
    else if (stoch < 25) score += 15;
    else if (stoch > 80) score -= 15;
  }
  if (cci != null) {
    if (cci >= -50 && cci <= 50) score += 5;
    else if (cci < -100) score += 10;
    else if (cci > 100) score -= 10;
  }
  return clamp(score);
}

export function computeTechnicalRatingAtIndex(
  bars: OhlcvBarDto[],
  index: number,
): TechnicalRatingBreakdownPoint | null {
  if (index + 1 < 50) return null;
  const slice = bars.slice(0, index + 1);
  const closes = slice.map((bar) => bar.close);
  const trend = scoreTrend(closes, closes.length - 1);
  const momentum = scoreMomentum(closes);
  const volatility = scoreVolatility(slice, closes, closes.length - 1);
  const meanReversion = scoreMeanReversion(slice, closes);
  const pattern = 50;
  const total = clamp(
    trend * 0.38 + momentum * 0.28 + volatility * 0.14 + meanReversion * 0.14 + pattern * 0.06,
  );
  return { trend, momentum, volatility, meanReversion, pattern, total };
}

export function computeTechnicalRatingSeries(
  bars: OhlcvBarDto[],
  warmupBars = 50,
): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    const rating = i + 1 >= warmupBars ? computeTechnicalRatingAtIndex(bars, i) : null;
    out.push(rating?.total ?? null);
  }
  return out;
}

export function computeTechnicalRatingComponentSeries(
  bars: OhlcvBarDto[],
  component: keyof Omit<TechnicalRatingBreakdownPoint, 'total'>,
  warmupBars = 50,
): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    const rating = i + 1 >= warmupBars ? computeTechnicalRatingAtIndex(bars, i) : null;
    out.push(rating?.[component] ?? null);
  }
  return out;
}

function businessDaysBetween(start: Date, end: Date): number {
  if (end <= start) return 0;
  let count = 0;
  const current = new Date(start);
  current.setDate(current.getDate() + 1);
  while (current <= end) {
    if (current.getDay() !== 0 && current.getDay() !== 6) count += 1;
    current.setDate(current.getDate() + 1);
  }
  return count;
}

function countWeekdayGaps(timestamps: string[]): number {
  const dates = timestamps
    .map((ts) => new Date(ts.slice(0, 10)))
    .filter((date) => !Number.isNaN(date.getTime()))
    .sort((a, b) => a.getTime() - b.getTime());
  if (dates.length < 2) return 0;
  let gaps = 0;
  for (let i = 1; i < dates.length; i += 1) {
    const missing = businessDaysBetween(dates[i - 1]!, dates[i]!) - 1;
    if (missing > 0) gaps += missing;
  }
  return gaps;
}

function scoreBarDepth(barCount: number): number {
  if (barCount >= 500) return 100;
  if (barCount >= 200) return 85;
  if (barCount >= 50) return 65 + ((barCount - 50) / (200 - 50)) * 20;
  return clamp((barCount / 50) * 50);
}

function scoreGaps(gapCount: number): number {
  if (gapCount <= 0) return 100;
  if (gapCount === 1) return 75;
  if (gapCount <= 3) return 45;
  return 15;
}

export function computeBarDataQualityAtIndex(
  bars: OhlcvBarDto[],
  index: number,
  gapLookback = 90,
): number | null {
  if (index < 0) return null;
  const slice = bars.slice(0, index + 1);
  const timestamps = slice.slice(-gapLookback).map((bar) => bar.timestamp);
  const barDepth = scoreBarDepth(slice.length);
  const gaps = scoreGaps(countWeekdayGaps(timestamps));
  return clamp(barDepth * 0.6 + gaps * 0.4);
}

export function computeBarDataQualitySeries(
  bars: OhlcvBarDto[],
  gapLookback = 90,
): (number | null)[] {
  return bars.map((_, index) => computeBarDataQualityAtIndex(bars, index, gapLookback));
}

export function computeAiGlobalScoreSeries(
  bars: OhlcvBarDto[],
  setupWeight = 70,
  dataWeight = 30,
  warmupBars = 50,
  gapLookback = 90,
): (number | null)[] {
  const totalWeight = setupWeight + dataWeight;
  const setupRatio = totalWeight > 0 ? setupWeight / totalWeight : 0.7;
  const dataRatio = totalWeight > 0 ? dataWeight / totalWeight : 0.3;
  const setupSeries = computeTechnicalRatingSeries(bars, warmupBars);
  const dataSeries = computeBarDataQualitySeries(bars, gapLookback);
  return bars.map((_, index) => {
    const setup = setupSeries[index];
    const data = dataSeries[index];
    if (setup == null || data == null) return null;
    return clamp(setup * setupRatio + data * dataRatio);
  });
}

export function computeGlobalScore(setupScore: number, dataScore: number, setupWeight = 70, dataWeight = 30): number {
  const totalWeight = setupWeight + dataWeight;
  const setupRatio = totalWeight > 0 ? setupWeight / totalWeight : 0.7;
  const dataRatio = totalWeight > 0 ? dataWeight / totalWeight : 0.3;
  return clamp(setupScore * setupRatio + dataScore * dataRatio);
}
