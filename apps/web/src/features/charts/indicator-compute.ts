import type { ChartIndicatorInstance, IndicatorPointDto, OhlcvBarDto } from '@bolsa/shared';
import {
  computeAiGlobalScoreSeries,
  computeBarDataQualitySeries,
  computeGatePassSeriesFromPreset,
  computeTechnicalRatingComponentSeries,
  computeTechnicalRatingSeries,
  dataParametersKey,
  findIndicatorDefinition,
  legacyApiKeyForInstance,
  STYLE_PARAMETER_IDS,
} from '@bolsa/shared';
import { barTimeToChartTime, indicatorToLineSeries } from '@/features/charts/chart-utils';
import type { Time } from 'lightweight-charts';

const INDICATOR_RENDER_CACHE_MAX = 128;
const SPEC_SERIES_CACHE_MAX = 96;

function barsFingerprint(bars: OhlcvBarDto[]): string {
  if (bars.length === 0) return '0';
  const first = bars[0]!;
  const last = bars[bars.length - 1]!;
  return `${bars.length}:${first.timestamp}:${first.close}:${last.timestamp}:${last.close}`;
}

/** Huella estable de OHLCV para memo en paneles de indicadores. */
export function buildIndicatorBarsFingerprint(bars: OhlcvBarDto[]): string {
  return barsFingerprint(bars);
}

function dataParamsKey(parameters: Record<string, number | boolean | string>): string {
  const filtered = Object.fromEntries(
    Object.entries(parameters).filter(
      ([key]) => !STYLE_PARAMETER_IDS.includes(key as (typeof STYLE_PARAMETER_IDS)[number]),
    ),
  );
  return dataParametersKey(filtered);
}

function specSeriesCacheKey(
  panel: 'overlay' | 'sub',
  definitionId: string,
  parameters: Record<string, number | boolean | string>,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
  apiKey: string | null,
): string {
  return [
    panel,
    definitionId,
    dataParamsKey(parameters),
    barsFingerprint(bars),
    apiPointsFingerprint(apiPoints, apiKey),
  ].join('|');
}

const specSeriesCache = new Map<string, IndicatorRenderSeries[]>();

let specCacheHits = 0;
let specCacheMisses = 0;

/** Estadísticas del caché por spec (H1) — consumidas por chart-perf-analyzer. */
export function getIndicatorSpecCacheStats(): {
  hits: number;
  misses: number;
  size: number;
  hitRate: number;
} {
  const total = specCacheHits + specCacheMisses;
  return {
    hits: specCacheHits,
    misses: specCacheMisses,
    size: specSeriesCache.size,
    hitRate: total > 0 ? specCacheHits / total : 0,
  };
}

/** Reinicia contadores de caché (p. ej. al iniciar bolsaPerfStart). */
export function resetIndicatorSpecCacheStats(): void {
  specCacheHits = 0;
  specCacheMisses = 0;
}

function readSpecCache(key: string): IndicatorRenderSeries[] | undefined {
  const hit = specSeriesCache.get(key);
  if (!hit) {
    specCacheMisses += 1;
    return undefined;
  }
  specCacheHits += 1;
  specSeriesCache.delete(key);
  specSeriesCache.set(key, hit);
  return hit;
}

function writeSpecCache(key: string, value: IndicatorRenderSeries[]): IndicatorRenderSeries[] {
  if (specSeriesCache.has(key)) specSeriesCache.delete(key);
  specSeriesCache.set(key, value);
  while (specSeriesCache.size > SPEC_SERIES_CACHE_MAX) {
    const oldest = specSeriesCache.keys().next().value;
    if (oldest == null) break;
    specSeriesCache.delete(oldest);
  }
  return value;
}

function withSpecSeriesCache(
  panel: 'overlay' | 'sub',
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
  compute: () => IndicatorRenderSeries[],
): IndicatorRenderSeries[] {
  const apiKey = legacyApiKeyForInstance(instance);
  const key = specSeriesCacheKey(
    panel,
    instance.definitionId,
    instance.parameters,
    bars,
    apiPoints,
    apiKey,
  );
  const cached = readSpecCache(key);
  if (cached) return cached;
  return writeSpecCache(key, compute());
}

function apiPointsFingerprint(apiPoints: IndicatorPointDto[], apiKey: string | null): string {
  if (!apiKey || apiPoints.length === 0) return '0';
  const last = apiPoints[apiPoints.length - 1]!;
  return `${apiKey}:${apiPoints.length}:${last.timestamp}`;
}

function instanceCacheKey(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
  panel: 'overlay' | 'sub',
): string {
  const apiKey = legacyApiKeyForInstance(instance);
  return [
    panel,
    instance.instanceId,
    instance.definitionId,
    instance.visible ? '1' : '0',
    JSON.stringify(instance.parameters),
    barsFingerprint(bars),
    apiPointsFingerprint(apiPoints, apiKey),
  ].join('|');
}

const overlayRenderCache = new Map<string, IndicatorRenderSeries[]>();
const subRenderCache = new Map<string, IndicatorRenderSeries[]>();

function readRenderCache(
  cache: Map<string, IndicatorRenderSeries[]>,
  key: string,
): IndicatorRenderSeries[] | undefined {
  const hit = cache.get(key);
  if (!hit) return undefined;
  cache.delete(key);
  cache.set(key, hit);
  return hit;
}

function writeRenderCache(
  cache: Map<string, IndicatorRenderSeries[]>,
  key: string,
  value: IndicatorRenderSeries[],
): IndicatorRenderSeries[] {
  if (cache.has(key)) cache.delete(key);
  cache.set(key, value);
  while (cache.size > INDICATOR_RENDER_CACHE_MAX) {
    const oldest = cache.keys().next().value;
    if (oldest == null) break;
    cache.delete(oldest);
  }
  return value;
}

/** Limpia memo de series (tests o cambio de instrumento). */
export function clearIndicatorRenderCache(): void {
  overlayRenderCache.clear();
  subRenderCache.clear();
  specSeriesCache.clear();
}

export interface IndicatorLinePoint {
  time: Time;
  value: number;
}

export interface IndicatorRenderSeries {
  key: string;
  title: string;
  points: IndicatorLinePoint[];
  dashed?: boolean;
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

function computeWma(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  const denom = (period * (period + 1)) / 2;
  for (let i = 0; i < closes.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    let sum = 0;
    for (let w = 1; w <= period; w += 1) {
      sum += closes[i - period + w]! * w;
    }
    out.push(sum / denom);
  }
  return out;
}

function computeRsi(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  if (closes.length === 0) return out;
  out.push(null);
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
    if (avgLoss === 0) out.push(100);
    else out.push(100 - 100 / (1 + avgGain / avgLoss));
  }
  return out;
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

/** Williams %R = -100 * (HH - Close) / (HH - LL). */
function computeWilliamsR(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    const slice = bars.slice(i - period + 1, i + 1);
    const high = Math.max(...slice.map((b) => b.high));
    const low = Math.min(...slice.map((b) => b.low));
    const close = bars[i]!.close;
    out.push(high === low ? -50 : (-100 * (high - close)) / (high - low));
  }
  return out;
}

/** Momentum = Close(t) - Close(t - period). */
function computeMomentum(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    if (i < period) {
      out.push(null);
      continue;
    }
    out.push(closes[i]! - closes[i - period]!);
  }
  return out;
}

/** Rolling population stddev of close. */
function computeStdDev(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period;
    out.push(Math.sqrt(variance));
  }
  return out;
}

/** Donchian: upper=max(high), lower=min(low), mid=(upper+lower)/2. */
function computeDonchian(
  bars: OhlcvBarDto[],
  period: number,
): { upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] } {
  const upper: (number | null)[] = [];
  const mid: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    if (i + 1 < period) {
      upper.push(null);
      mid.push(null);
      lower.push(null);
      continue;
    }
    const slice = bars.slice(i - period + 1, i + 1);
    const hi = Math.max(...slice.map((b) => b.high));
    const lo = Math.min(...slice.map((b) => b.low));
    upper.push(hi);
    lower.push(lo);
    mid.push((hi + lo) / 2);
  }
  return { upper, mid, lower };
}

function wilderSmooth(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = Array(values.length).fill(null);
  if (values.length < period) return result;
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result[period - 1] = prev;
  for (let i = period; i < values.length; i += 1) {
    prev = prev - prev / period + values[i]!;
    result[i] = prev;
  }
  return result;
}

function computeAdx(
  bars: OhlcvBarDto[],
  period: number,
): { adx: (number | null)[]; plusDi: (number | null)[]; minusDi: (number | null)[] } {
  const n = bars.length;
  const plusDm = Array(n).fill(0) as number[];
  const minusDm = Array(n).fill(0) as number[];
  const tr = Array(n).fill(0) as number[];
  for (let i = 0; i < n; i += 1) {
    const bar = bars[i]!;
    if (i === 0) {
      tr[i] = bar.high - bar.low;
      continue;
    }
    const prev = bars[i - 1]!;
    const up = bar.high - prev.high;
    const down = prev.low - bar.low;
    plusDm[i] = up > down && up > 0 ? up : 0;
    minusDm[i] = down > up && down > 0 ? down : 0;
    tr[i] = Math.max(
      bar.high - bar.low,
      Math.abs(bar.high - prev.close),
      Math.abs(bar.low - prev.close),
    );
  }
  const sTr = wilderSmooth(tr, period);
  const sPlus = wilderSmooth(plusDm, period);
  const sMinus = wilderSmooth(minusDm, period);
  const plusDi: (number | null)[] = Array(n).fill(null);
  const minusDi: (number | null)[] = Array(n).fill(null);
  const dx: (number | null)[] = Array(n).fill(null);
  for (let i = 0; i < n; i += 1) {
    const strV = sTr[i];
    const sp = sPlus[i];
    const sm = sMinus[i];
    if (strV == null || sp == null || sm == null || strV === 0) continue;
    const pdi = (100 * sp) / strV;
    const mdi = (100 * sm) / strV;
    plusDi[i] = pdi;
    minusDi[i] = mdi;
    const denom = pdi + mdi;
    dx[i] = denom === 0 ? 0 : (100 * Math.abs(pdi - mdi)) / denom;
  }
  const adx: (number | null)[] = Array(n).fill(null);
  const firstDx = period - 1;
  if (n >= firstDx + period) {
    const seedVals: number[] = [];
    for (let i = firstDx; i < firstDx + period; i += 1) {
      const v = dx[i];
      if (v != null) seedVals.push(v);
    }
    if (seedVals.length === period) {
      let prev = seedVals.reduce((a, b) => a + b, 0) / period;
      const start = firstDx + period - 1;
      adx[start] = prev;
      for (let i = start + 1; i < n; i += 1) {
        const cur = dx[i];
        if (cur == null) {
          adx[i] = null;
          continue;
        }
        prev = (prev * (period - 1) + cur) / period;
        adx[i] = prev;
      }
    }
  }
  return { adx, plusDi, minusDi };
}

function smaOfSeries(values: (number | null)[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < values.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    const window = values.slice(i - period + 1, i + 1);
    if (window.some((v) => v == null)) {
      out.push(null);
      continue;
    }
    out.push(window.reduce((a, b) => a! + b!, 0)! / period);
  }
  return out;
}

function computeStochRsi(
  closes: number[],
  rsiPeriod: number,
  stochPeriod: number,
  kPeriod: number,
  dPeriod: number,
): { k: (number | null)[]; d: (number | null)[] } {
  const rsi = computeRsi(closes, rsiPeriod);
  const raw: (number | null)[] = [];
  for (let i = 0; i < rsi.length; i += 1) {
    if (i + 1 < stochPeriod) {
      raw.push(null);
      continue;
    }
    const window = rsi.slice(i - stochPeriod + 1, i + 1);
    if (window.some((v) => v == null)) {
      raw.push(null);
      continue;
    }
    const vals = window as number[];
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const cur = rsi[i];
    if (cur == null) raw.push(null);
    else if (hi === lo) raw.push(50);
    else raw.push((100 * (cur - lo)) / (hi - lo));
  }
  const k = kPeriod > 1 ? smaOfSeries(raw, kPeriod) : raw;
  const d = smaOfSeries(k, dPeriod);
  return { k, d };
}

function computeSuperTrend(
  bars: OhlcvBarDto[],
  atrPeriod: number,
  multiplier: number,
): (number | null)[] {
  const atr = computeAtr(bars, atrPeriod);
  const n = bars.length;
  const result: (number | null)[] = Array(n).fill(null);
  const finalUb: (number | null)[] = Array(n).fill(null);
  const finalLb: (number | null)[] = Array(n).fill(null);
  let trend = 1;
  for (let i = 0; i < n; i += 1) {
    const atrV = atr[i];
    if (atrV == null) continue;
    const hl2 = (bars[i]!.high + bars[i]!.low) / 2;
    const basicUb = hl2 + multiplier * atrV;
    const basicLb = hl2 - multiplier * atrV;
    if (i === 0 || finalUb[i - 1] == null) {
      finalUb[i] = basicUb;
      finalLb[i] = basicLb;
    } else {
      const prevUb = finalUb[i - 1]!;
      const prevLb = finalLb[i - 1]!;
      const prevClose = bars[i - 1]!.close;
      finalUb[i] = basicUb < prevUb || prevClose > prevUb ? basicUb : prevUb;
      finalLb[i] = basicLb > prevLb || prevClose < prevLb ? basicLb : prevLb;
    }
    const close = bars[i]!.close;
    if (i > 0 && finalUb[i - 1] != null && close > finalUb[i - 1]!) trend = 1;
    else if (i > 0 && finalLb[i - 1] != null && close < finalLb[i - 1]!) trend = -1;
    result[i] = trend === 1 ? (finalLb[i] ?? null) : (finalUb[i] ?? null);
  }
  return result;
}

function computeVwap(bars: OhlcvBarDto[]): (number | null)[] {
  const out: (number | null)[] = [];
  let cumPv = 0;
  let cumVol = 0;
  for (const bar of bars) {
    const tp = (bar.high + bar.low + bar.close) / 3;
    const vol = bar.volume;
    if (vol <= 0) {
      out.push(cumVol === 0 ? null : cumPv / cumVol);
      continue;
    }
    cumPv += tp * vol;
    cumVol += vol;
    out.push(cumPv / cumVol);
  }
  return out;
}

function computeObv(bars: OhlcvBarDto[]): (number | null)[] {
  const out: (number | null)[] = [];
  let obv = 0;
  for (let i = 0; i < bars.length; i += 1) {
    if (i === 0) {
      out.push(0);
      continue;
    }
    const prev = bars[i - 1]!.close;
    const close = bars[i]!.close;
    if (close > prev) obv += bars[i]!.volume;
    else if (close < prev) obv -= bars[i]!.volume;
    out.push(obv);
  }
  return out;
}

function computeRoc(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < closes.length; i += 1) {
    if (i < period) {
      out.push(null);
      continue;
    }
    const prev = closes[i - period]!;
    out.push(prev === 0 ? null : (100 * (closes[i]! - prev)) / prev);
  }
  return out;
}

function computeMfi(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const typical = bars.map((b) => (b.high + b.low + b.close) / 3);
  const rawMf = typical.map((tp, i) => tp * bars[i]!.volume);
  const out: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    if (i < period) {
      out.push(null);
      continue;
    }
    let pos = 0;
    let neg = 0;
    for (let j = i - period + 1; j <= i; j += 1) {
      if (j === 0) continue;
      if (typical[j]! > typical[j - 1]!) pos += rawMf[j]!;
      else if (typical[j]! < typical[j - 1]!) neg += rawMf[j]!;
    }
    out.push(neg === 0 ? 100 : 100 - 100 / (1 + pos / neg));
  }
  return out;
}

function computeAroon(
  bars: OhlcvBarDto[],
  period: number,
): { up: (number | null)[]; down: (number | null)[] } {
  const up: (number | null)[] = [];
  const down: (number | null)[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    if (i + 1 < period) {
      up.push(null);
      down.push(null);
      continue;
    }
    const window = bars.slice(i - period + 1, i + 1);
    const hi = Math.max(...window.map((b) => b.high));
    const lo = Math.min(...window.map((b) => b.low));
    let sinceHigh = 0;
    let sinceLow = 0;
    for (let o = 0; o < window.length; o += 1) {
      if (window[window.length - 1 - o]!.high === hi) {
        sinceHigh = o;
        break;
      }
    }
    for (let o = 0; o < window.length; o += 1) {
      if (window[window.length - 1 - o]!.low === lo) {
        sinceLow = o;
        break;
      }
    }
    up.push((100 * (period - sinceHigh)) / period);
    down.push((100 * (period - sinceLow)) / period);
  }
  return { up, down };
}

function smma(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = Array(values.length).fill(null);
  if (values.length < period) return result;
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result[period - 1] = prev;
  for (let i = period; i < values.length; i += 1) {
    prev = (prev * (period - 1) + values[i]!) / period;
    result[i] = prev;
  }
  return result;
}

function computeAlligator(bars: OhlcvBarDto[]): {
  jaw: (number | null)[];
  teeth: (number | null)[];
  lips: (number | null)[];
} {
  const median = bars.map((b) => (b.high + b.low) / 2);
  const jawRaw = smma(median, 13);
  const teethRaw = smma(median, 8);
  const lipsRaw = smma(median, 5);
  const n = bars.length;
  const jaw: (number | null)[] = Array(n).fill(null);
  const teeth: (number | null)[] = Array(n).fill(null);
  const lips: (number | null)[] = Array(n).fill(null);
  for (let i = 0; i < n; i += 1) {
    if (i >= 8 && jawRaw[i - 8] != null) jaw[i] = jawRaw[i - 8]!;
    if (i >= 5 && teethRaw[i - 5] != null) teeth[i] = teethRaw[i - 5]!;
    if (i >= 3 && lipsRaw[i - 3] != null) lips[i] = lipsRaw[i - 3]!;
  }
  return { jaw, teeth, lips };
}

function computeBearsPower(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const ema = computeEma(
    bars.map((b) => b.close),
    period,
  );
  return bars.map((b, i) => (ema[i] == null ? null : b.low - ema[i]!));
}

function computeBullsPower(bars: OhlcvBarDto[], period: number): (number | null)[] {
  const ema = computeEma(
    bars.map((b) => b.close),
    period,
  );
  return bars.map((b, i) => (ema[i] == null ? null : b.high - ema[i]!));
}

function computePsar(bars: OhlcvBarDto[], step = 0.02, maxAf = 0.2): (number | null)[] {
  const n = bars.length;
  if (n === 0) return [];
  const result: (number | null)[] = Array(n).fill(null);
  let bull = true;
  let af = step;
  let ep = bars[0]!.high;
  let sar = bars[0]!.low;
  result[0] = sar;
  for (let i = 1; i < n; i += 1) {
    const prevSar = sar;
    sar = prevSar + af * (ep - prevSar);
    if (bull) {
      sar = Math.min(sar, bars[i - 1]!.low);
      if (i >= 2) sar = Math.min(sar, bars[i - 2]!.low);
      if (bars[i]!.low < sar) {
        bull = false;
        sar = ep;
        ep = bars[i]!.low;
        af = step;
      } else if (bars[i]!.high > ep) {
        ep = bars[i]!.high;
        af = Math.min(af + step, maxAf);
      }
    } else {
      sar = Math.max(sar, bars[i - 1]!.high);
      if (i >= 2) sar = Math.max(sar, bars[i - 2]!.high);
      if (bars[i]!.high > sar) {
        bull = true;
        sar = ep;
        ep = bars[i]!.high;
        af = step;
      } else if (bars[i]!.low < ep) {
        ep = bars[i]!.low;
        af = Math.min(af + step, maxAf);
      }
    }
    result[i] = sar;
  }
  return result;
}

function computeFractals(bars: OhlcvBarDto[]): {
  up: (number | null)[];
  down: (number | null)[];
} {
  const n = bars.length;
  const up: (number | null)[] = Array(n).fill(null);
  const down: (number | null)[] = Array(n).fill(null);
  for (let i = 2; i < n - 2; i += 1) {
    const highs = [0, 1, 2, 3, 4].map((o) => bars[i - 2 + o]!.high);
    const lows = [0, 1, 2, 3, 4].map((o) => bars[i - 2 + o]!.low);
    const hi = bars[i]!.high;
    const lo = bars[i]!.low;
    if (hi === Math.max(...highs) && highs.filter((h) => h === hi).length === 1) up[i] = hi;
    if (lo === Math.min(...lows) && lows.filter((l) => l === lo).length === 1) down[i] = lo;
  }
  return { up, down };
}

function midpointHl(bars: OhlcvBarDto[], period: number, index: number): number | null {
  if (index + 1 < period) return null;
  const window = bars.slice(index - period + 1, index + 1);
  return (Math.max(...window.map((b) => b.high)) + Math.min(...window.map((b) => b.low))) / 2;
}

function computeIchimoku(
  bars: OhlcvBarDto[],
  tenkanPeriod: number,
  kijunPeriod: number,
  senkouBPeriod: number,
  displacement: number,
): {
  tenkan: (number | null)[];
  kijun: (number | null)[];
  spanA: (number | null)[];
  spanB: (number | null)[];
  chikou: (number | null)[];
} {
  const n = bars.length;
  const tenkan = bars.map((_, i) => midpointHl(bars, tenkanPeriod, i));
  const kijun = bars.map((_, i) => midpointHl(bars, kijunPeriod, i));
  const spanBRaw = bars.map((_, i) => midpointHl(bars, senkouBPeriod, i));
  const spanA: (number | null)[] = Array(n).fill(null);
  const spanB: (number | null)[] = Array(n).fill(null);
  const chikou: (number | null)[] = Array(n).fill(null);
  for (let i = 0; i < n; i += 1) {
    const src = i - displacement;
    if (src >= 0) {
      const t = tenkan[src];
      const k = kijun[src];
      if (t != null && k != null) spanA[i] = (t + k) / 2;
      spanB[i] = spanBRaw[src] ?? null;
    }
    if (i + displacement < n) chikou[i] = bars[i + displacement]!.close;
  }
  return { tenkan, kijun, spanA, spanB, chikou };
}

function computeMacdLine(
  closes: number[],
  fast: number,
  slow: number,
): (number | null)[] {
  const fastEma = computeEma(closes, fast);
  const slowEma = computeEma(closes, slow);
  return fastEma.map((f, i) => (f != null && slowEma[i] != null ? f - slowEma[i]! : null));
}

function seriesFromComputed(
  bars: OhlcvBarDto[],
  values: (number | null)[],
): IndicatorLinePoint[] {
  const points: IndicatorLinePoint[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    const value = values[i];
    if (value == null || !Number.isFinite(value)) continue;
    points.push({ time: barTimeToChartTime(bars[i]!.timestamp), value });
  }
  return points;
}

function computeBollinger(
  closes: number[],
  period: number,
  stdDev: number,
): { mid: (number | null)[]; upper: (number | null)[]; lower: (number | null)[] } {
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
  return { mid, upper, lower };
}

function computeOverlayRenderSeries(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
): IndicatorRenderSeries[] {
  return withSpecSeriesCache('overlay', instance, bars, apiPoints, () => {
    if (!instance.visible) return [];
    const apiKey = legacyApiKeyForInstance(instance);
    if (apiKey && apiPoints.length > 0) {
      return [
        {
          key: 'main',
          title: instance.definitionId,
          points: indicatorToLineSeries(apiPoints, apiKey),
        },
      ];
    }

    const closes = bars.map((bar) => bar.close);
    const period = Number(instance.parameters.period);

    if (instance.definitionId === 'sma' && Number.isFinite(period)) {
      return [{ key: 'main', title: 'SMA', points: seriesFromComputed(bars, computeSma(closes, period)) }];
    }
    if (instance.definitionId === 'ema' && Number.isFinite(period)) {
      return [{ key: 'main', title: 'EMA', points: seriesFromComputed(bars, computeEma(closes, period)) }];
    }
    if (instance.definitionId === 'wma' && Number.isFinite(period)) {
      return [{ key: 'main', title: 'WMA', points: seriesFromComputed(bars, computeWma(closes, period)) }];
    }
    if (instance.definitionId === 'bb' && Number.isFinite(period)) {
      const stdDev = Number(instance.parameters.stdDev ?? 2);
      const bands = computeBollinger(closes, period, stdDev);
      return [
        { key: 'upper', title: 'BB sup', points: seriesFromComputed(bars, bands.upper), dashed: true },
        { key: 'mid', title: 'BB', points: seriesFromComputed(bars, bands.mid) },
        { key: 'lower', title: 'BB inf', points: seriesFromComputed(bars, bands.lower), dashed: true },
      ];
    }
    if (instance.definitionId === 'dc' && Number.isFinite(period)) {
      const channel = computeDonchian(bars, period);
      return [
        { key: 'upper', title: 'DC sup', points: seriesFromComputed(bars, channel.upper), dashed: true },
        { key: 'mid', title: 'DC', points: seriesFromComputed(bars, channel.mid) },
        { key: 'lower', title: 'DC inf', points: seriesFromComputed(bars, channel.lower), dashed: true },
      ];
    }
    if (instance.definitionId === 'st') {
      const atrPeriod = Number(instance.parameters.atrPeriod ?? 10);
      const multiplier = Number(instance.parameters.multiplier ?? 3);
      if (Number.isFinite(atrPeriod) && Number.isFinite(multiplier)) {
        return [
          {
            key: 'main',
            title: 'ST',
            points: seriesFromComputed(bars, computeSuperTrend(bars, atrPeriod, multiplier)),
          },
        ];
      }
    }
    if (instance.definitionId === 'vwap') {
      return [{ key: 'main', title: 'VWAP', points: seriesFromComputed(bars, computeVwap(bars)) }];
    }
    if (instance.definitionId === 'sar') {
      const step = Number(instance.parameters.step ?? 0.02);
      const maxAf = Number(instance.parameters.maxAf ?? 0.2);
      if (Number.isFinite(step) && Number.isFinite(maxAf)) {
        return [{ key: 'main', title: 'SAR', points: seriesFromComputed(bars, computePsar(bars, step, maxAf)) }];
      }
    }
    if (instance.definitionId === 'ali') {
      const { jaw, teeth, lips } = computeAlligator(bars);
      return [
        { key: 'jaw', title: 'Jaw', points: seriesFromComputed(bars, jaw), dashed: true },
        { key: 'teeth', title: 'Teeth', points: seriesFromComputed(bars, teeth) },
        { key: 'lips', title: 'Lips', points: seriesFromComputed(bars, lips), dashed: true },
      ];
    }
    if (instance.definitionId === 'fr') {
      const { up, down } = computeFractals(bars);
      return [
        { key: 'up', title: 'FR↑', points: seriesFromComputed(bars, up) },
        { key: 'down', title: 'FR↓', points: seriesFromComputed(bars, down) },
      ];
    }
    if (instance.definitionId === 'ich') {
      const tenkanPeriod = Number(instance.parameters.tenkanPeriod ?? 9);
      const kijunPeriod = Number(instance.parameters.kijunPeriod ?? 26);
      const senkouBPeriod = Number(instance.parameters.senkouBPeriod ?? 52);
      const displacement = Number(instance.parameters.displacement ?? 26);
      if (
        Number.isFinite(tenkanPeriod) &&
        Number.isFinite(kijunPeriod) &&
        Number.isFinite(senkouBPeriod) &&
        Number.isFinite(displacement)
      ) {
        const { tenkan, kijun, spanA, spanB, chikou } = computeIchimoku(
          bars,
          tenkanPeriod,
          kijunPeriod,
          senkouBPeriod,
          displacement,
        );
        return [
          { key: 'tenkan', title: 'Tenkan', points: seriesFromComputed(bars, tenkan) },
          { key: 'kijun', title: 'Kijun', points: seriesFromComputed(bars, kijun) },
          { key: 'spanA', title: 'Span A', points: seriesFromComputed(bars, spanA), dashed: true },
          { key: 'spanB', title: 'Span B', points: seriesFromComputed(bars, spanB), dashed: true },
          { key: 'chikou', title: 'Chikou', points: seriesFromComputed(bars, chikou), dashed: true },
        ];
      }
    }
    return [];
  });
}

export function resolveOverlayRenderSeries(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
): IndicatorRenderSeries[] {
  const key = instanceCacheKey(instance, bars, apiPoints, 'overlay');
  const cached = readRenderCache(overlayRenderCache, key);
  if (cached) return cached;
  return writeRenderCache(
    overlayRenderCache,
    key,
    computeOverlayRenderSeries(instance, bars, apiPoints),
  );
}

/** @deprecated usar resolveOverlayRenderSeries */
export function resolveOverlayLineSeries(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
): IndicatorLinePoint[] {
  return resolveOverlayRenderSeries(instance, bars, apiPoints)[0]?.points ?? [];
}

function computeSubRenderSeries(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
): IndicatorRenderSeries[] {
  return withSpecSeriesCache('sub', instance, bars, apiPoints, () => {
  if (!instance.visible) return [];
  const apiKey = legacyApiKeyForInstance(instance);
  if (apiKey && apiPoints.length > 0) {
    return [
      {
        key: 'main',
        title: instance.definitionId,
        points: indicatorToLineSeries(apiPoints, apiKey),
      },
    ];
  }

  const closes = bars.map((bar) => bar.close);
  const period = Number(instance.parameters.period);

  if (instance.definitionId === 'rsi' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'RSI', points: seriesFromComputed(bars, computeRsi(closes, period)) }];
  }
  if (instance.definitionId === 'atr' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'ATR', points: seriesFromComputed(bars, computeAtr(bars, period)) }];
  }
  if (instance.definitionId === 'cci' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'CCI', points: seriesFromComputed(bars, computeCci(bars, period)) }];
  }
  if (instance.definitionId === 'stoch') {
    const kPeriod = Number(instance.parameters.kPeriod ?? 14);
    if (Number.isFinite(kPeriod)) {
      return [{ key: 'main', title: 'Stoch %K', points: seriesFromComputed(bars, computeStochK(bars, kPeriod)) }];
    }
  }
  if (instance.definitionId === 'willr' && Number.isFinite(period)) {
    return [{ key: 'main', title: '%R', points: seriesFromComputed(bars, computeWilliamsR(bars, period)) }];
  }
  if (instance.definitionId === 'mom' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'MOM', points: seriesFromComputed(bars, computeMomentum(closes, period)) }];
  }
  if (instance.definitionId === 'sd' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'SD', points: seriesFromComputed(bars, computeStdDev(closes, period)) }];
  }
  if (instance.definitionId === 'adx' && Number.isFinite(period)) {
    const { adx, plusDi, minusDi } = computeAdx(bars, period);
    return [
      { key: 'main', title: 'ADX', points: seriesFromComputed(bars, adx) },
      { key: 'plus_di', title: '+DI', points: seriesFromComputed(bars, plusDi), dashed: true },
      { key: 'minus_di', title: '−DI', points: seriesFromComputed(bars, minusDi), dashed: true },
    ];
  }
  if (instance.definitionId === 'srsi') {
    const rsiPeriod = Number(instance.parameters.rsiPeriod ?? 14);
    const stochPeriod = Number(instance.parameters.stochPeriod ?? 14);
    const kPeriod = Number(instance.parameters.kPeriod ?? 3);
    const dPeriod = Number(instance.parameters.dPeriod ?? 3);
    if (
      Number.isFinite(rsiPeriod) &&
      Number.isFinite(stochPeriod) &&
      Number.isFinite(kPeriod) &&
      Number.isFinite(dPeriod)
    ) {
      const { k, d } = computeStochRsi(closes, rsiPeriod, stochPeriod, kPeriod, dPeriod);
      return [
        { key: 'main', title: 'StochRSI %K', points: seriesFromComputed(bars, k) },
        { key: 'signal', title: '%D', points: seriesFromComputed(bars, d), dashed: true },
      ];
    }
  }
  if (instance.definitionId === 'obv') {
    return [{ key: 'main', title: 'OBV', points: seriesFromComputed(bars, computeObv(bars)) }];
  }
  if (instance.definitionId === 'roc' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'ROC', points: seriesFromComputed(bars, computeRoc(closes, period)) }];
  }
  if (instance.definitionId === 'mfi' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'MFI', points: seriesFromComputed(bars, computeMfi(bars, period)) }];
  }
  if (instance.definitionId === 'aroon' && Number.isFinite(period)) {
    const { up, down } = computeAroon(bars, period);
    return [
      { key: 'up', title: 'Aroon↑', points: seriesFromComputed(bars, up) },
      { key: 'down', title: 'Aroon↓', points: seriesFromComputed(bars, down), dashed: true },
    ];
  }
  if (instance.definitionId === 'bears' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'Bears', points: seriesFromComputed(bars, computeBearsPower(bars, period)) }];
  }
  if (instance.definitionId === 'bulls' && Number.isFinite(period)) {
    return [{ key: 'main', title: 'Bulls', points: seriesFromComputed(bars, computeBullsPower(bars, period)) }];
  }
  if (instance.definitionId === 'macd') {
    const fast = Number(instance.parameters.fastPeriod ?? 12);
    const slow = Number(instance.parameters.slowPeriod ?? 26);
    if (Number.isFinite(fast) && Number.isFinite(slow)) {
      return [{ key: 'main', title: 'MACD', points: seriesFromComputed(bars, computeMacdLine(closes, fast, slow)) }];
    }
  }
  if (instance.definitionId === 'strategy_hybrid_score_v1') {
    const warmupBars = Number(instance.parameters.warmupBars ?? 50);
    const showComponents = instance.parameters.showComponents === true;
    const showMinScoreLine = instance.parameters.showMinScoreLine !== false;
    const showGateLine = instance.parameters.showGateLine !== false;
    const minScore = Number(instance.parameters.minScore ?? 60);
    const gatePresetKey = String(instance.parameters.gatePresetKey ?? '').trim() || null;
    const ratingSeries = computeTechnicalRatingSeries(bars, warmupBars);
    const series: IndicatorRenderSeries[] = [
      {
        key: 'main',
        title: 'Score estrategia',
        points: seriesFromComputed(bars, ratingSeries),
      },
    ];
    if (showComponents) {
      series.push(
        {
          key: 'trend',
          title: 'Tendencia',
          points: seriesFromComputed(
            bars,
            computeTechnicalRatingComponentSeries(bars, 'trend', warmupBars),
          ),
          dashed: true,
        },
        {
          key: 'momentum',
          title: 'Momentum',
          points: seriesFromComputed(
            bars,
            computeTechnicalRatingComponentSeries(bars, 'momentum', warmupBars),
          ),
          dashed: true,
        },
      );
    }
    const mainPoints = series[0]?.points ?? [];
    if (showMinScoreLine && mainPoints.length > 0 && Number.isFinite(minScore)) {
      series.push({
        key: 'minScore',
        title: 'Umbral',
        points: mainPoints.map((point) => ({ time: point.time, value: minScore })),
        dashed: true,
      });
    }
    if (showGateLine && gatePresetKey) {
      const gateSeries = computeGatePassSeriesFromPreset(bars, gatePresetKey);
      series.push({
        key: 'gate',
        title: 'Gate',
        points: seriesFromComputed(bars, gateSeries),
        dashed: true,
      });
    }
    return series;
  }
  if (instance.definitionId === 'technical_rating_v1') {
    const warmupBars = Number(instance.parameters.warmupBars ?? 50);
    const showComponents = instance.parameters.showComponents === true;
    const series: IndicatorRenderSeries[] = [
      {
        key: 'main',
        title: 'Rating IA',
        points: seriesFromComputed(bars, computeTechnicalRatingSeries(bars, warmupBars)),
      },
    ];
    if (showComponents) {
      series.push(
        {
          key: 'trend',
          title: 'Tendencia',
          points: seriesFromComputed(
            bars,
            computeTechnicalRatingComponentSeries(bars, 'trend', warmupBars),
          ),
          dashed: true,
        },
        {
          key: 'momentum',
          title: 'Momentum',
          points: seriesFromComputed(
            bars,
            computeTechnicalRatingComponentSeries(bars, 'momentum', warmupBars),
          ),
          dashed: true,
        },
      );
    }
    return series;
  }
  if (instance.definitionId === 'bar_data_quality_v1') {
    const gapLookback = Number(instance.parameters.gapLookback ?? 90);
    return [
      {
        key: 'main',
        title: 'Datos',
        points: seriesFromComputed(bars, computeBarDataQualitySeries(bars, gapLookback)),
      },
    ];
  }
  if (instance.definitionId === 'ai_global_score_v1') {
    const setupWeight = Number(instance.parameters.setupWeight ?? 70);
    const dataWeight = Number(instance.parameters.dataWeight ?? 30);
    const warmupBars = Number(instance.parameters.warmupBars ?? 50);
    return [
      {
        key: 'main',
        title: 'Global IA',
        points: seriesFromComputed(
          bars,
          computeAiGlobalScoreSeries(bars, setupWeight, dataWeight, warmupBars),
        ),
      },
    ];
  }
  return [];
  });
}

export function resolveSubRenderSeries(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
): IndicatorRenderSeries[] {
  const key = instanceCacheKey(instance, bars, apiPoints, 'sub');
  const cached = readRenderCache(subRenderCache, key);
  if (cached) return cached;
  return writeRenderCache(
    subRenderCache,
    key,
    computeSubRenderSeries(instance, bars, apiPoints),
  );
}

/** @deprecated usar resolveSubRenderSeries */
export function resolveSubLineSeries(
  instance: ChartIndicatorInstance,
  bars: OhlcvBarDto[],
  apiPoints: IndicatorPointDto[],
): IndicatorLinePoint[] {
  return resolveSubRenderSeries(instance, bars, apiPoints)[0]?.points ?? [];
}

export function hasVolumeInstance(instances: ChartIndicatorInstance[]): boolean {
  return instances.some((item) => item.definitionId === 'volume' && item.visible);
}

export function overlayTrendInstances(instances: ChartIndicatorInstance[]): ChartIndicatorInstance[] {
  return instances.filter((item) => {
    if (!item.visible || item.definitionId === 'volume') return false;
    const def = findIndicatorDefinition(item.definitionId);
    return def?.panel === 'overlay';
  });
}

export function overlayManagementInstances(
  instances: ChartIndicatorInstance[],
): ChartIndicatorInstance[] {
  return instances.filter((item) => {
    const def = findIndicatorDefinition(item.definitionId);
    return def?.panel === 'overlay';
  });
}

export function subPanelInstancesAll(instances: ChartIndicatorInstance[]): ChartIndicatorInstance[] {
  return instances.filter((item) => {
    const def = findIndicatorDefinition(item.definitionId);
    return def?.panel === 'sub';
  });
}

export function subPanelInstances(instances: ChartIndicatorInstance[]): ChartIndicatorInstance[] {
  return instances.filter((item) => {
    if (!item.visible) return false;
    const def = findIndicatorDefinition(item.definitionId);
    return def?.panel === 'sub';
  });
}
