/**
 * Estructura de mercado calculada — soportes, resistencias y tendencia de pivotes
 * (S2 · 2026-11-12). Dominio PURO: sin React, sin IO, sin `Date.now`, sin locale.
 *
 * Qué hace: detecta pivotes de swing confirmados, los agrupa por ATR (tolerancia
 * geométrica), clasifica cada grupo y declara su estado. También describe la
 * estructura de la tendencia a partir de esos pivotes.
 *
 * Qué NO hace: no decide, no puntúa, no genera señales, no alimenta el motor, el
 * gate, el sizing ni el plan operativo. Un nivel aquí es reproducible a partir de
 * las velas y los parámetros declarados; no es un hecho durable.
 *
 * Regla dura: lo que no se puede medir se declara (`insufficient_history` /
 * `no_disponible` con causa) y no produce niveles. Nunca se inventa una línea.
 *
 * @see docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md
 */

import type { OhlcvBarDto } from "./types.js";

export const MARKET_STRUCTURE_METHOD_ID = "swing-atr-v1" as const;
export const MARKET_STRUCTURE_METHOD_VERSION = 1 as const;

/** Parámetros por defecto del método. Todos viajan en el resultado. */
export const MARKET_STRUCTURE_DEFAULTS = {
  /** Velas a cada lado para confirmar un pivote (ventana = 2N + 1). */
  pivotLookback: 3,
  /** Periodo del ATR de Wilder (solo tolerancia geométrica). */
  atrPeriod: 14,
  /** Tolerancia de agrupación: fracción del ATR respecto al centro del grupo. */
  clusterAtrMultiple: 0.75,
  /** «En precio» si el cierre queda dentro de esta fracción de ATR del nivel. */
  inPriceAtrMultiple: 0.25,
  /** «Roto» si el cierre cruza la zona en contra por más de esta fracción de ATR. */
  brokenAtrMultiple: 0.5,
  /** Tolerancia de absorción entre dos niveles del mismo lado. */
  absorbAtrMultiple: 0.25,
  /** Máximo de niveles conservados por lado. */
  maxLevelsPerSide: 3,
  /** Velas mínimas para calcular. Por debajo se declara el hueco. */
  minBars: 80,
  /** Ventana máxima usada (las velas que ya carga el gráfico). */
  maxBars: 500,
  /** Fracción final de la ventana en la que un toque cuenta como reciente. */
  recencyFraction: 0.25,
  /** Pivotes por lado para describir la estructura. */
  structurePivots: 3,
  /** Tolerancia (fracción de ATR) para considerar dos extremos «iguales». */
  structureToleranceAtr: 0.5,
} as const;

export type MarketStructureParamsV1 = {
  pivotLookback: number;
  atrPeriod: number;
  clusterAtrMultiple: number;
  inPriceAtrMultiple: number;
  brokenAtrMultiple: number;
  absorbAtrMultiple: number;
  maxLevelsPerSide: number;
  minBars: number;
  maxBars: number;
  recencyFraction: number;
  structurePivots: number;
  structureToleranceAtr: number;
};

export type MarketStructureStatusV1 =
  | "ok"
  | "insufficient_history"
  | "no_disponible";

export type MarketLevelKindV1 = "support" | "resistance";

export type MarketLevelStateV1 =
  | "detectado"
  | "no_fiable"
  | "roto"
  | "en_precio"
  | "no_disponible";

export type MarketLevelReasonV1 =
  | "sin_velas"
  | "historico_insuficiente"
  | "velas_invalidas"
  | "sin_atr"
  | "sin_pivotes"
  | "un_solo_toque"
  | "sin_toque_reciente"
  | "absorbido_por_nivel_mas_fuerte"
  | "precio_en_nivel"
  | "nivel_roto"
  | "ultima_vela_en_curso";

export type MarketPivotTypeV1 = "high" | "low";

/** Pivote confirmado, con su procedencia exacta. */
export type MarketPivotV1 = {
  /** Índice dentro de la ventana usada. */
  index: number;
  timestamp: string;
  price: number;
  type: MarketPivotTypeV1;
};

export type MarketLevelV1 = {
  kind: MarketLevelKindV1;
  /** Media de los precios de los pivotes del grupo. */
  price: number;
  zoneLow: number;
  zoneHigh: number;
  touches: number;
  state: MarketLevelStateV1;
  reasons: MarketLevelReasonV1[];
  /** Pivotes que originan el nivel (trazabilidad). */
  pivots: MarketPivotV1[];
  lastTouchAt: string | null;
  /** (price − close) / close × 100. */
  distancePct: number | null;
  /** (price − close) / atrRef. */
  distanceAtr: number | null;
};

export type MarketStructureTrendIdV1 =
  | "ascendente"
  | "descendente"
  | "en_rango"
  | "sin_estructura";

export type MarketStructureTrendV1 = {
  id: MarketStructureTrendIdV1;
  /** Tolerancia aplicada (fracción de ATR × atrRef), para reproducir la lectura. */
  tolerance: number | null;
  /** Últimos máximos confirmados usados (procedencia). */
  highs: MarketPivotV1[];
  /** Últimos mínimos confirmados usados (procedencia). */
  lows: MarketPivotV1[];
};

export type MarketStructureWindowV1 = {
  from: string | null;
  to: string | null;
  bars: number;
  timeframe: string;
};

export type MarketStructureResultV1 = {
  methodId: typeof MARKET_STRUCTURE_METHOD_ID;
  methodVersion: typeof MARKET_STRUCTURE_METHOD_VERSION;
  params: MarketStructureParamsV1;
  window: MarketStructureWindowV1;
  /** Huella estable de ventana + parámetros + extremos de la serie. */
  inputSignature: string;
  status: MarketStructureStatusV1;
  reasons: MarketLevelReasonV1[];
  atrRef: number | null;
  close: number | null;
  supports: MarketLevelV1[];
  resistances: MarketLevelV1[];
  structure: MarketStructureTrendV1;
  /** Hecho declarado: la última vela puede seguir en curso. */
  lastBarMayBeOpen: boolean;
};

export type ComputeMarketStructureInput = {
  bars: readonly OhlcvBarDto[];
  timeframe?: string | null;
  params?: Partial<MarketStructureParamsV1>;
};

const EPS = 1e-9;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseTime(timestamp: string): number {
  if (typeof timestamp !== "string" || timestamp.trim() === "") return NaN;
  return Date.parse(timestamp);
}

function resolveParams(
  overrides: Partial<MarketStructureParamsV1> | undefined,
): MarketStructureParamsV1 {
  const merged: MarketStructureParamsV1 = { ...MARKET_STRUCTURE_DEFAULTS };
  if (!overrides) return merged;
  for (const key of Object.keys(merged) as (keyof MarketStructureParamsV1)[]) {
    const value = overrides[key];
    if (isFiniteNumber(value) && value > 0) merged[key] = value;
  }
  return merged;
}

function stableHash(value: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function emptyStructure(): MarketStructureTrendV1 {
  return { id: "sin_estructura", tolerance: null, highs: [], lows: [] };
}

/** ATR de Wilder. Devuelve `null` donde aún no hay medición. */
export function computeWilderAtr(
  bars: readonly OhlcvBarDto[],
  period: number,
): (number | null)[] {
  const out: (number | null)[] = [];
  if (bars.length === 0 || period <= 0) return out;
  const tr: number[] = [];
  for (let i = 0; i < bars.length; i += 1) {
    const bar = bars[i]!;
    const prev = bars[i - 1];
    tr.push(
      prev
        ? Math.max(
            bar.high - bar.low,
            Math.abs(bar.high - prev.close),
            Math.abs(bar.low - prev.close),
          )
        : bar.high - bar.low,
    );
  }
  let atr: number | null = null;
  for (let i = 0; i < tr.length; i += 1) {
    if (i + 1 < period) {
      out.push(null);
      continue;
    }
    if (atr == null) {
      let sum = 0;
      for (let j = 0; j < period; j += 1) sum += tr[j]!;
      atr = sum / period;
    } else {
      atr = (atr * (period - 1) + tr[i]!) / period;
    }
    out.push(atr);
  }
  return out;
}

/** Pivotes confirmados de la ventana. Comparación estricta: un empate no cuenta. */
export function detectSwings(
  bars: readonly OhlcvBarDto[],
  lookback: number,
): { highs: MarketPivotV1[]; lows: MarketPivotV1[] } {
  const highs: MarketPivotV1[] = [];
  const lows: MarketPivotV1[] = [];
  const n = bars.length;
  if (lookback <= 0 || n < lookback * 2 + 1) return { highs, lows };
  for (let i = lookback; i < n - lookback; i += 1) {
    const bar = bars[i]!;
    let isHigh = true;
    let isLow = true;
    for (let k = 1; k <= lookback; k += 1) {
      const left = bars[i - k]!;
      const right = bars[i + k]!;
      if (!(bar.high > left.high && bar.high > right.high)) isHigh = false;
      if (!(bar.low < left.low && bar.low < right.low)) isLow = false;
      if (!isHigh && !isLow) break;
    }
    if (isHigh) {
      highs.push({
        index: i,
        timestamp: bar.timestamp,
        price: bar.high,
        type: "high",
      });
    }
    if (isLow) {
      lows.push({
        index: i,
        timestamp: bar.timestamp,
        price: bar.low,
        type: "low",
      });
    }
  }
  return { highs, lows };
}

export type MarketPivotClusterV1 = {
  pivots: MarketPivotV1[];
  price: number;
  zoneLow: number;
  zoneHigh: number;
};

/**
 * Agrupa pivotes en niveles. La tolerancia se mide contra el **centro** del grupo
 * (media de sus precios), no contra el último pivote: así una secuencia escalonada
 * no se encadena hasta fusionar un rango entero.
 */
export function groupPivotsByAtr(
  pivots: readonly MarketPivotV1[],
  tolerance: number,
): MarketPivotClusterV1[] {
  const ordered = [...pivots].sort((a, b) => a.price - b.price);
  const groups: { pivots: MarketPivotV1[]; sum: number }[] = [];
  for (const pivot of ordered) {
    const target = groups[groups.length - 1];
    if (target) {
      const center = target.sum / target.pivots.length;
      if (Math.abs(pivot.price - center) <= tolerance + EPS) {
        target.pivots.push(pivot);
        target.sum += pivot.price;
        continue;
      }
    }
    groups.push({ pivots: [pivot], sum: pivot.price });
  }
  return groups.map((group) => {
    const prices = group.pivots.map((pivot) => pivot.price);
    return {
      pivots: group.pivots,
      price: group.sum / group.pivots.length,
      zoneLow: Math.min(...prices),
      zoneHigh: Math.max(...prices),
    };
  });
}

function trendOfExtremes(
  values: readonly number[],
  tolerance: number,
): "up" | "down" | "flat" | "mixed" {
  if (values.length < 2) return "mixed";
  let up = true;
  let down = true;
  let flat = true;
  for (let i = 1; i < values.length; i += 1) {
    const diff = values[i]! - values[i - 1]!;
    if (diff <= tolerance + EPS) up = false;
    if (diff >= -tolerance - EPS) down = false;
    if (Math.abs(diff) > tolerance + EPS) flat = false;
  }
  if (up) return "up";
  if (down) return "down";
  if (flat) return "flat";
  return "mixed";
}

/**
 * Estructura de la tendencia a partir de los últimos pivotes confirmados.
 * No usa el estudio ni ADX: es estructura de precio, con vocabulario propio.
 */
export function describeMarketStructure(input: {
  highs: readonly MarketPivotV1[];
  lows: readonly MarketPivotV1[];
  atrRef: number | null;
  params?: Partial<MarketStructureParamsV1>;
}): MarketStructureTrendV1 {
  const params = resolveParams(input.params);
  const need = Math.max(2, Math.round(params.structurePivots));
  const lastHighs = input.highs.slice(-need);
  const lastLows = input.lows.slice(-need);
  const tolerance =
    input.atrRef == null
      ? null
      : input.atrRef * params.structureToleranceAtr;
  if (tolerance == null || lastHighs.length < need || lastLows.length < need) {
    return {
      id: "sin_estructura",
      tolerance,
      highs: lastHighs,
      lows: lastLows,
    };
  }
  const highTrend = trendOfExtremes(
    lastHighs.map((pivot) => pivot.price),
    tolerance,
  );
  const lowTrend = trendOfExtremes(
    lastLows.map((pivot) => pivot.price),
    tolerance,
  );
  let id: MarketStructureTrendIdV1 = "sin_estructura";
  if (highTrend === "up" && lowTrend === "up") id = "ascendente";
  else if (highTrend === "down" && lowTrend === "down") id = "descendente";
  else if (highTrend === "flat" && lowTrend === "flat") id = "en_rango";
  return { id, tolerance, highs: lastHighs, lows: lastLows };
}

/**
 * Evalúa un grupo de pivotes como nivel. Precedencia declarada y falsable:
 * en precio → roto → no fiable → detectado.
 */
export function buildMarketLevel(input: {
  kind: MarketLevelKindV1;
  pivots: readonly MarketPivotV1[];
  close: number;
  atrRef: number;
  barsCount: number;
  params?: Partial<MarketStructureParamsV1>;
}): MarketLevelV1 {
  const params = resolveParams(input.params);
  const pivots = [...input.pivots].sort((a, b) => a.index - b.index);
  const prices = pivots.map((pivot) => pivot.price);
  const price = prices.reduce((total, value) => total + value, 0) / prices.length;
  const zoneLow = Math.min(...prices);
  const zoneHigh = Math.max(...prices);
  const lastPivot = pivots[pivots.length - 1]!;
  const reasons: MarketLevelReasonV1[] = [];
  let state: MarketLevelStateV1 = "detectado";

  // 1) ¿Existe el nivel? Con un solo toque, o dos toques antiguos, no hay nivel:
  //    no se puede «romper» ni estar «en precio» algo que nunca fue estructura.
  if (pivots.length < 2) {
    state = "no_fiable";
    reasons.push("un_solo_toque");
  } else if (pivots.length === 2) {
    const recencyWindow = Math.max(
      1,
      Math.ceil(input.barsCount * params.recencyFraction),
    );
    if (lastPivot.index < input.barsCount - recencyWindow) {
      state = "no_fiable";
      reasons.push("sin_toque_reciente");
    }
  }

  // 2) ¿Dónde está el precio respecto al nivel ya confirmado?
  if (state === "detectado") {
    if (
      Math.abs(input.close - price) <=
      input.atrRef * params.inPriceAtrMultiple + EPS
    ) {
      state = "en_precio";
      reasons.push("precio_en_nivel");
    } else {
      const broken =
        input.kind === "support"
          ? input.close <
            zoneLow - input.atrRef * params.brokenAtrMultiple - EPS
          : input.close >
            zoneHigh + input.atrRef * params.brokenAtrMultiple + EPS;
      if (broken) {
        state = "roto";
        reasons.push("nivel_roto");
      }
    }
  }

  const distance = price - input.close;
  return {
    kind: input.kind,
    price,
    zoneLow,
    zoneHigh,
    touches: pivots.length,
    state,
    reasons,
    pivots,
    lastTouchAt: lastPivot.timestamp,
    distancePct: input.close === 0 ? null : (distance / input.close) * 100,
    distanceAtr: input.atrRef === 0 ? null : distance / input.atrRef,
  };
}

function applyAbsorption(
  levels: MarketLevelV1[],
  atrRef: number,
  params: MarketStructureParamsV1,
): void {
  const tolerance = atrRef * params.absorbAtrMultiple;
  const ordered = [...levels].sort((a, b) => b.touches - a.touches);
  for (let i = 0; i < ordered.length; i += 1) {
    const strong = ordered[i]!;
    for (let j = i + 1; j < ordered.length; j += 1) {
      const weak = ordered[j]!;
      if (Math.abs(strong.price - weak.price) > tolerance + EPS) continue;
      if (weak.touches >= strong.touches) continue;
      if (weak.reasons.includes("absorbido_por_nivel_mas_fuerte")) continue;
      weak.state = "no_fiable";
      weak.reasons = [
        ...weak.reasons.filter((reason) => reason !== "un_solo_toque"),
        "absorbido_por_nivel_mas_fuerte",
      ];
    }
  }
}

function pickLevels(levels: readonly MarketLevelV1[], max: number): MarketLevelV1[] {
  // `levels` ya viene ordenado por distancia al cierre; el sort es estable y solo
  // adelanta los detectados (son los únicos que se dibujan).
  return [...levels]
    .sort((a, b) => {
      const aRank = a.state === "detectado" ? 0 : 1;
      const bRank = b.state === "detectado" ? 0 : 1;
      return aRank - bRank;
    })
    .slice(0, Math.max(0, max));
}

function baseResult(input: {
  params: MarketStructureParamsV1;
  window: MarketStructureWindowV1;
  inputSignature: string;
  status: MarketStructureStatusV1;
  reasons: MarketLevelReasonV1[];
  close: number | null;
  atrRef: number | null;
  lastBarMayBeOpen: boolean;
}): MarketStructureResultV1 {
  return {
    methodId: MARKET_STRUCTURE_METHOD_ID,
    methodVersion: MARKET_STRUCTURE_METHOD_VERSION,
    params: input.params,
    window: input.window,
    inputSignature: input.inputSignature,
    status: input.status,
    reasons: input.reasons,
    atrRef: input.atrRef,
    close: input.close,
    supports: [],
    resistances: [],
    structure: emptyStructure(),
    lastBarMayBeOpen: input.lastBarMayBeOpen,
  };
}

function isUsableBar(bar: OhlcvBarDto): boolean {
  if (!isFiniteNumber(parseTime(bar.timestamp))) return false;
  if (!isFiniteNumber(bar.open)) return false;
  if (!isFiniteNumber(bar.high)) return false;
  if (!isFiniteNumber(bar.low)) return false;
  if (!isFiniteNumber(bar.close)) return false;
  return bar.high >= bar.low;
}

function sortByDistance(
  levels: readonly MarketLevelV1[],
  close: number,
): MarketLevelV1[] {
  return [...levels].sort(
    (a, b) => Math.abs(a.price - close) - Math.abs(b.price - close),
  );
}

/**
 * Calcula la estructura de mercado de una serie de velas.
 *
 * Determinista: mismos `bars` + `params` ⇒ mismo resultado. No muta la entrada.
 */
export function computeMarketStructure(
  input: ComputeMarketStructureInput,
): MarketStructureResultV1 {
  const params = resolveParams(input.params);
  const timeframe = input.timeframe?.trim() || "1d";
  const rawBars = input.bars ?? [];
  const maxBars = Math.max(1, Math.floor(params.maxBars));
  const timesValid = rawBars.every((bar) =>
    isFiniteNumber(parseTime(bar.timestamp)),
  );

  // Normaliza por tiempo ascendente sobre una copia y recorta a la ventana. Si
  // los timestamps no son legibles, no se ordena: se declara la barra inválida.
  const ordered = timesValid
    ? [...rawBars].sort((a, b) => parseTime(a.timestamp) - parseTime(b.timestamp))
    : [...rawBars];
  const bars = ordered.slice(-maxBars);
  const window: MarketStructureWindowV1 = {
    from: bars[0]?.timestamp ?? null,
    to: bars[bars.length - 1]?.timestamp ?? null,
    bars: bars.length,
    timeframe,
  };

  const inputSignature = stableHash(
    [
      MARKET_STRUCTURE_METHOD_ID,
      MARKET_STRUCTURE_METHOD_VERSION,
      timeframe,
      JSON.stringify(params),
      window.bars,
      window.from ?? "",
      bars[0]?.close ?? "",
      window.to ?? "",
      bars[bars.length - 1]?.close ?? "",
    ].join("|"),
  );

  if (rawBars.length === 0) {
    return baseResult({
      params,
      window: { from: null, to: null, bars: 0, timeframe },
      inputSignature,
      status: "no_disponible",
      reasons: ["sin_velas"],
      close: null,
      atrRef: null,
      lastBarMayBeOpen: false,
    });
  }

  if (!bars.every(isUsableBar)) {
    return baseResult({
      params,
      window,
      inputSignature,
      status: "no_disponible",
      reasons: ["velas_invalidas"],
      close: null,
      atrRef: null,
      lastBarMayBeOpen: true,
    });
  }

  if (bars.length < params.minBars) {
    return baseResult({
      params,
      window,
      inputSignature,
      status: "insufficient_history",
      reasons: ["historico_insuficiente"],
      close: bars[bars.length - 1]?.close ?? null,
      atrRef: null,
      lastBarMayBeOpen: true,
    });
  }

  const atrSeries = computeWilderAtr(bars, Math.floor(params.atrPeriod));
  let atrRef: number | null = null;
  for (let i = atrSeries.length - 1; i >= 0; i -= 1) {
    const value = atrSeries[i];
    if (value != null && Number.isFinite(value) && value > 0) {
      atrRef = value;
      break;
    }
  }
  const close = bars[bars.length - 1]!.close;

  if (atrRef == null) {
    return baseResult({
      params,
      window,
      inputSignature,
      status: "no_disponible",
      reasons: ["sin_atr"],
      close,
      atrRef: null,
      lastBarMayBeOpen: true,
    });
  }

  const swings = detectSwings(bars, Math.floor(params.pivotLookback));
  if (swings.highs.length === 0 && swings.lows.length === 0) {
    return baseResult({
      params,
      window,
      inputSignature,
      status: "no_disponible",
      reasons: ["sin_pivotes"],
      close,
      atrRef,
      lastBarMayBeOpen: true,
    });
  }

  const tolerance = atrRef * params.clusterAtrMultiple;
  const supports = groupPivotsByAtr(swings.lows, tolerance).map((cluster) =>
    buildMarketLevel({
      kind: "support",
      pivots: cluster.pivots,
      close,
      atrRef: atrRef!,
      barsCount: bars.length,
      params,
    }),
  );
  const resistances = groupPivotsByAtr(swings.highs, tolerance).map((cluster) =>
    buildMarketLevel({
      kind: "resistance",
      pivots: cluster.pivots,
      close,
      atrRef: atrRef!,
      barsCount: bars.length,
      params,
    }),
  );

  applyAbsorption(supports, atrRef, params);
  applyAbsorption(resistances, atrRef, params);

  const structure = describeMarketStructure({
    highs: swings.highs,
    lows: swings.lows,
    atrRef,
    params,
  });

  return {
    methodId: MARKET_STRUCTURE_METHOD_ID,
    methodVersion: MARKET_STRUCTURE_METHOD_VERSION,
    params,
    window,
    inputSignature,
    status: "ok",
    reasons: [],
    atrRef,
    close,
    supports: pickLevels(
      sortByDistance(supports, close),
      Math.floor(params.maxLevelsPerSide),
    ),
    resistances: pickLevels(
      sortByDistance(resistances, close),
      Math.floor(params.maxLevelsPerSide),
    ),
    structure,
    lastBarMayBeOpen: true,
  };
}

/** ¿Este nivel se puede dibujar como línea válida? Solo los `detectado`. */
export function marketLevelIsDrawable(level: MarketLevelV1): boolean {
  return level.state === "detectado";
}

/** Todos los niveles del resultado, en orden soporte → resistencia. */
export function marketStructureLevels(
  result: MarketStructureResultV1,
): MarketLevelV1[] {
  return [...result.supports, ...result.resistances];
}
