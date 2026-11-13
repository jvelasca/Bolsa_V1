/**
 * Glosario canónico de mercado (S1 · 2026-11-12) — UNA sola fuente de etiquetas.
 *
 * Traduce las claves internas del motor a lenguaje de producto **sin tocar la
 * decisión**: `compute_stance` sigue emitiendo las 7 posturas y los 19 motivos
 * tal cual; aquí solo se les pone nombre visible. Nada de este módulo participa
 * en el cálculo, el gate, el sizing ni la ejecución.
 *
 * Reglas duras (ver `docs/engineering/glosario-mercado-asesor-2026-11-12.md`):
 * - Ninguna clave interna (`snake_case`) se pinta: siempre pasa por una tabla.
 * - La tendencia NO es la recomendación: `Lateral` significa rango (ADX ≤ 25) y
 *   `Mixta` significa que las medias no coinciden en una estructura. No se
 *   fusionan: fusionarlas corregiría el vocabulario creando un error de sentido.
 * - Un dato ausente se declara (`Sin medir`, `Sin entrada publicada`), nunca se
 *   rellena con 0 ni con una postura inventada.
 * - El termómetro es **display**: se deriva de precio + entrada + niveles en el
 *   cliente y jamás se presenta como orden ni como autorización.
 *
 * @see docs/engineering/glosario-mercado-asesor-2026-11-12.md
 */

import type {
  InstrumentDailyOpinionReasonCode,
  InstrumentDailyOpinionStance,
} from "./instrument-daily-opinion.js";
import type {
  MarketLevelKindV1,
  MarketLevelReasonV1,
  MarketLevelStateV1,
  MarketStructureTrendIdV1,
} from "./market-structure.js";

// ─────────────────────────────────────────────────────────────────────────────
// 1 · Recomendación (las 7 posturas, renombradas)
// ─────────────────────────────────────────────────────────────────────────────

export const MARKET_STANCE_FAMILIES = [
  "alcista",
  "neutral",
  "bajista",
  "sin_senal",
] as const;

export type MarketStanceFamily = (typeof MARKET_STANCE_FAMILIES)[number];

export type MarketStanceDefinitionV1 = {
  /** Clave interna del motor. No se pinta nunca. */
  stance: InstrumentDailyOpinionStance;
  /** Denominación visible, única y estable. */
  label: string;
  family: MarketStanceFamily;
  /** Qué tiene que pasar en el motor para llegar aquí (producto, no umbrales). */
  trigger: string;
  /** Qué significa y, sobre todo, qué NO significa. */
  meaning: string;
};

/**
 * Las 7 denominaciones. La clave interna viaja intacta en el DTO; solo cambia
 * el nombre visible. `no_trade` se afina por causa con `marketStanceLabel`.
 */
export const MARKET_STANCE_DEFINITIONS: Record<
  InstrumentDailyOpinionStance,
  MarketStanceDefinitionV1
> = {
  buy: {
    stance: "buy",
    label: "Comprar",
    family: "alcista",
    trigger:
      "Sin posición abierta, calidad de señal alta y la estrategia #1 del Lab con respaldo.",
    meaning:
      "Hay una señal de compra respaldada por el Lab. No es una orden: la firma vive en Confirm.",
  },
  hold_watch: {
    stance: "hold_watch",
    label: "Mantener",
    family: "neutral",
    trigger:
      "Con posición abierta: la señal no pide ni salir ni reforzar. Sin posición: no hay entrada hoy.",
    meaning:
      "Ni compra ni venta. Con posición se conserva; sin posición se espera. El matiz se declara en la justificación.",
  },
  overbought: {
    stance: "overbought",
    label: "Sin respaldo",
    family: "sin_senal",
    trigger:
      "Posición abierta, estrategia #1 del Lab sin respaldo y calidad de señal por encima del nivel de salida.",
    meaning:
      "La estrategia que sostenía la posición ya no la respalda, pero no hay señal de salida. No es sobrecompra técnica.",
  },
  reduce: {
    stance: "reduce",
    label: "Reducir",
    family: "bajista",
    trigger:
      "Posición abierta y señal de salida parcial (alerta fundamental o calidad de señal baja sin llegar al mínimo de salida).",
    meaning:
      "Se propone reducir el tamaño. SOLO se emite con posición medida y abierta.",
  },
  sell_exit: {
    stance: "sell_exit",
    label: "Vender",
    family: "bajista",
    trigger:
      "Posición abierta y calidad de señal en el mínimo de salida, sin alerta fundamental.",
    meaning:
      "Se propone cerrar la posición. SOLO se emite con posición medida y abierta.",
  },
  no_trade: {
    stance: "no_trade",
    label: "No operar",
    family: "sin_senal",
    trigger:
      "Falta un término de la decisión: cierre de sesión, cartera medida, alerta fundamental o filtro de riesgo.",
    meaning:
      "El motor no emite recomendación de entrada o salida. La causa concreta se declara siempre (`marketStanceLabel`).",
  },
  review_strategy: {
    stance: "review_strategy",
    label: "Revisar estrategia",
    family: "sin_senal",
    trigger:
      "No hay estrategia #1 del Lab o lleva más de 30 días sin actualizar.",
    meaning:
      "Falta el respaldo del Lab, no la tesis del valor. Se revisa la estrategia, no se inventa una postura.",
  },
};

/** Denominación por defecto de cada postura (misma clave que el contrato). */
export const INSTRUMENT_DAILY_OPINION_STANCE_LABELS: Record<
  InstrumentDailyOpinionStance,
  string
> = {
  buy: MARKET_STANCE_DEFINITIONS.buy.label,
  hold_watch: MARKET_STANCE_DEFINITIONS.hold_watch.label,
  overbought: MARKET_STANCE_DEFINITIONS.overbought.label,
  reduce: MARKET_STANCE_DEFINITIONS.reduce.label,
  sell_exit: MARKET_STANCE_DEFINITIONS.sell_exit.label,
  no_trade: MARKET_STANCE_DEFINITIONS.no_trade.label,
  review_strategy: MARKET_STANCE_DEFINITIONS.review_strategy.label,
};

/**
 * Causas de `no_trade`, en orden de precedencia. La primera que aparezca manda:
 * «No evaluable» (no se midió) gana a «No operar» (sí se midió y no se opera).
 */
const NO_TRADE_CAUSE_PRECEDENCE: ReadonlyArray<{
  reason: InstrumentDailyOpinionReasonCode;
  label: string;
  detail: string;
  /** Solo diagnóstico: no es un estado operativo alcanzable en producto. */
  diagnosticOnly?: boolean;
}> = [
  {
    reason: "position_unmeasured",
    label: "No evaluable",
    detail: "Cartera sin medir",
  },
  {
    reason: "position_closed",
    label: "No evaluable",
    detail: "Posición no confirmada",
  },
  {
    reason: "gate_veto",
    label: "Operativa bloqueada",
    detail: "Filtro de riesgo en veto",
    diagnosticOnly: true,
  },
  {
    reason: "eod_data_stale",
    label: "No operar",
    detail: "Sin cierre de sesión",
  },
  {
    reason: "fa_distress",
    label: "No operar",
    detail: "Alerta fundamental",
  },
];

export type MarketStanceLabelV1 = {
  /** Clave interna intacta. */
  stance: InstrumentDailyOpinionStance;
  label: string;
  family: MarketStanceFamily;
  /** Causa declarada de la postura (obligatoria en `no_trade` cuando se conoce). */
  detail: string | null;
  /** `true` = estado que el producto no debe pintar como postura alcanzable. */
  diagnosticOnly: boolean;
};

/**
 * Etiqueta visible de una postura. `no_trade` se afina por causa; el resto usa
 * su denominación única. Nunca devuelve una clave interna.
 */
export function marketStanceLabel(input: {
  stance: InstrumentDailyOpinionStance;
  reasons?: readonly string[] | null;
}): MarketStanceLabelV1 {
  const definition = MARKET_STANCE_DEFINITIONS[input.stance];
  const base: MarketStanceLabelV1 = {
    stance: input.stance,
    label: definition.label,
    family: definition.family,
    detail: null,
    diagnosticOnly: false,
  };
  if (input.stance !== "no_trade") return base;

  const reasons = input.reasons ?? [];
  for (const cause of NO_TRADE_CAUSE_PRECEDENCE) {
    if (!reasons.includes(cause.reason)) continue;
    return {
      ...base,
      label: cause.label,
      detail: cause.detail,
      diagnosticOnly: cause.diagnosticOnly === true,
    };
  }
  return base;
}

/**
 * Igual que `marketStanceLabel` pero para superficies que reciben la clave como
 * `string` (p. ej. el parte diario de Estudio). Una clave desconocida NO se pinta
 * en crudo: devuelve `null` y el llamante declara el hueco.
 */
export function marketStanceLabelFromKey(input: {
  stance: string | null | undefined;
  reasons?: readonly string[] | null;
}): MarketStanceLabelV1 | null {
  const key = input.stance?.trim();
  if (!key) return null;
  const definition = MARKET_STANCE_DEFINITIONS[key as InstrumentDailyOpinionStance];
  if (!definition) return null;
  return marketStanceLabel({
    stance: definition.stance,
    reasons: input.reasons,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 2 · Motivos (los 19 códigos del motor)
// ─────────────────────────────────────────────────────────────────────────────

export const MARKET_REASON_LABELS: Record<
  InstrumentDailyOpinionReasonCode,
  string
> = {
  eod_data_stale: "Sin cierre de sesión",
  gate_veto: "Filtro de riesgo en veto",
  stale_top: "Estrategia del Lab desactualizada",
  no_valid_top: "Sin estrategia del Lab",
  fa_distress: "Alerta fundamental",
  strong_buy_signal: "Señal de compra fuerte",
  neutral_no_position: "Sin señal de entrada",
  // El código es heredado; el significado es «señal de salida», NUNCA sobrecompra.
  overbought_or_exit: "Señal de salida",
  holding_position: "Posición abierta: se mantiene",
  top_high: "Estrategia del Lab con respaldo alto",
  top_medium: "Estrategia del Lab con respaldo suficiente",
  top_low: "Estrategia del Lab sin respaldo",
  io_high: "Calidad de señal alta",
  io_low: "Calidad de señal baja",
  // Sin rango numérico: el código se emite también con señales altas o sin medir.
  io_medium: "Calidad de señal sin señal de compra",
  position_open: "Ya hay posición abierta",
  position_closed: "Posición no confirmada",
  position_unmeasured: "Cartera sin medir",
  io_unmeasured: "Calidad de señal sin medir",
};

/** Motivos que solo tienen sentido en diagnóstico, nunca en producto. */
export const MARKET_DIAGNOSTIC_ONLY_REASONS: ReadonlySet<InstrumentDailyOpinionReasonCode> =
  new Set(["gate_veto"]);

/** Códigos que declaran un hueco de medición, no una lectura neutra. */
export const MARKET_UNMEASURED_REASONS: ReadonlySet<InstrumentDailyOpinionReasonCode> =
  new Set(["position_unmeasured", "io_unmeasured"]);

/** Etiqueta visible de un motivo; `null` si el código no está en la tabla. */
export function marketReasonLabel(reason: string): string | null {
  return (
    MARKET_REASON_LABELS[reason as InstrumentDailyOpinionReasonCode] ?? null
  );
}

export type MarketVisibleReasonsV1 = {
  /** Etiquetas traducidas, sin duplicados y ya filtradas. */
  visible: string[];
  /** Etiquetas que no caben en el primer nivel (van al tooltip). */
  hidden: string[];
  hiddenCount: number;
};

const DEFAULT_MAX_VISIBLE_REASONS = 3;

/**
 * Motivos listos para pintar. Puras reglas de presentación:
 * - `gate_veto` nunca entra (no es estado operativo alcanzable).
 * - `io_medium` se suprime con señal alta o sin medir: en esos casos afirmaría
 *   una falta de compra que el motor no está diciendo.
 * - `position_open` se calla si `holding_position` ya lo dice.
 * - sin duplicados de etiqueta, máximo 3 visibles.
 */
export function visibleReasons(
  reasons: readonly string[] | null | undefined,
  options: { ioScore?: number | null; maxVisible?: number } = {},
): MarketVisibleReasonsV1 {
  const maxVisible = options.maxVisible ?? DEFAULT_MAX_VISIBLE_REASONS;
  const ioScore = options.ioScore ?? null;
  const ordered: string[] = [];
  const raw = reasons ?? [];

  for (const reason of raw) {
    if (MARKET_DIAGNOSTIC_ONLY_REASONS.has(reason as InstrumentDailyOpinionReasonCode))
      continue;
    if (reason === "io_medium" && (ioScore == null || ioScore >= 80)) continue;
    if (reason === "position_open" && raw.includes("holding_position")) continue;
    const label = marketReasonLabel(reason);
    if (!label || ordered.includes(label)) continue;
    ordered.push(label);
  }

  const visible = ordered.slice(0, Math.max(0, maxVisible));
  const hidden = ordered.slice(visible.length);
  return { visible, hidden, hiddenCount: hidden.length };
}

// ─────────────────────────────────────────────────────────────────────────────
// 3 · Tendencia (rango ≠ mixta ≠ neutra)
// ─────────────────────────────────────────────────────────────────────────────

export const MARKET_TREND_TONES = [
  "bullish",
  "bearish",
  "range",
  "mixed",
  "neutral",
  "unknown",
] as const;

export type MarketTrendToneV1 = (typeof MARKET_TREND_TONES)[number];

export type MarketTrendDefinitionV1 = {
  label: string;
  tone: MarketTrendToneV1;
  /** Por qué se llama así; viaja en tooltip, no en el primer nivel. */
  basis: string;
};

/**
 * Valores canónicos de `study.trends` → etiqueta y tono. `weak` es rango
 * literal (ADX ≤ 25); `mixed` es desacuerdo de medias; `neutral` es ausencia de
 * dirección. Los tres son cosas distintas y no se pueden pintar igual.
 */
export const MARKET_TREND_DEFINITIONS: Record<string, MarketTrendDefinitionV1> = {
  strong_bullish: {
    label: "Alcista fuerte",
    tone: "bullish",
    basis: "Tendencia primaria alcista con fuerza (ADX + DI).",
  },
  bullish: {
    label: "Alcista",
    tone: "bullish",
    basis: "Tendencia primaria alcista.",
  },
  bullish_stack: {
    label: "Alineada alcista",
    tone: "bullish",
    basis: "Medias alineadas al alza.",
  },
  weak: {
    label: "Lateral",
    tone: "range",
    basis: "Tendencia débil o rango: ADX sin fuerza suficiente.",
  },
  neutral: {
    label: "Neutra",
    tone: "neutral",
    basis: "Sin dirección declarada por el estudio. No es un rango medido.",
  },
  mixed: {
    label: "Mixta",
    tone: "mixed",
    basis: "Las medias no coinciden en una estructura. No implica rango.",
  },
  bearish: {
    label: "Bajista",
    tone: "bearish",
    basis: "Tendencia primaria bajista.",
  },
  strong_bearish: {
    label: "Bajista fuerte",
    tone: "bearish",
    basis: "Tendencia primaria bajista con fuerza (ADX + DI).",
  },
  bearish_stack: {
    label: "Alineada bajista",
    tone: "bearish",
    basis: "Medias alineadas a la baja.",
  },
};

/** Etiqueta visible de un valor de tendencia; `null` si el estudio no lo declara. */
export function marketTrendDefinition(
  value: string | null | undefined,
): MarketTrendDefinitionV1 | null {
  if (!value) return null;
  return MARKET_TREND_DEFINITIONS[value] ?? null;
}

/** Tono de presentación de un valor de tendencia; `unknown` si no hay dato. */
export function marketTrendTone(
  value: string | null | undefined,
): MarketTrendToneV1 {
  return marketTrendDefinition(value)?.tone ?? "unknown";
}

/**
 * Etiqueta para pintar una tendencia. Se prefiere el texto que ya trae el parte
 * (`display`); si falta, se traduce el valor canónico. Un valor desconocido no
 * se pinta en crudo: se declara el hueco.
 */
export function marketTrendLabel(input: {
  value?: string | null;
  display?: string | null;
}): string {
  const display = input.display?.trim();
  if (display) return display;
  return marketTrendDefinition(input.value)?.label ?? "Sin dato de tendencia";
}

// ─────────────────────────────────────────────────────────────────────────────
// 4 · Termómetro de proximidad (display, nunca orden)
// ─────────────────────────────────────────────────────────────────────────────

/** Declarado: el termómetro se deriva en el cliente, no es un dato del motor. */
export const THERMOMETER_SOURCE = "display" as const;

/** Distancia (en %) a la que la entrada se considera cerca: ±3 %. */
export const THERMOMETER_NEAR_ENTRY_PCT = 3;

export const THERMOMETER_STATE_IDS = [
  "sin_entrada",
  "frio",
  "templado",
  "caliente",
  "extendido",
] as const;

export type ThermometerStateId = (typeof THERMOMETER_STATE_IDS)[number];

export type ThermometerStateV1 = {
  id: ThermometerStateId;
  label: string;
  /** Orden de precedencia: el primero que encaja manda. */
  precedence: number;
  /** Qué significa; nunca se lee como autorización. */
  meaning: string;
};

export const THERMOMETER_STATES: ReadonlyArray<ThermometerStateV1> = [
  {
    id: "sin_entrada",
    label: "Sin entrada",
    precedence: 0,
    meaning:
      "No hay entrada publicada o falta el precio: no se puede medir la proximidad.",
  },
  {
    id: "extendido",
    label: "Extendido",
    precedence: 1,
    meaning: "El precio ya superó el Objetivo 1: comprar aquí es perseguir.",
  },
  {
    id: "caliente",
    label: "Caliente",
    precedence: 2,
    meaning: "El precio ya está en la zona de activación.",
  },
  {
    id: "templado",
    label: "Templado",
    precedence: 3,
    meaning: "El precio está cerca de la entrada, sin activarla.",
  },
  {
    id: "frio",
    label: "Frío",
    precedence: 4,
    meaning: "El precio está lejos de la entrada.",
  },
];

export type ThermometerResolutionV1 = {
  state: ThermometerStateId;
  label: string;
  /** Por qué está en ese estado, en lenguaje de producto. */
  detail: string | null;
  /** Siempre `display`: no es una orden ni un dato del motor. */
  source: typeof THERMOMETER_SOURCE;
};

function thermometerState(id: ThermometerStateId): ThermometerStateV1 {
  const found = THERMOMETER_STATES.find((state) => state.id === id);
  if (!found) throw new Error(`Estado de termómetro desconocido: ${id}`);
  return found;
}

/**
 * Resuelve el termómetro con precedencia declarada. Todo lo que falta se
 * declara: sin entrada o sin precio → `Sin entrada`, sin inventar temperaturas.
 */
export function resolveThermometer(input: {
  markPrice: number | null | undefined;
  entry: number | null | undefined;
  invalidacion?: number | null;
  target1?: number | null;
}): ThermometerResolutionV1 {
  const mark = Number.isFinite(input.markPrice) ? Number(input.markPrice) : null;
  const entry = Number.isFinite(input.entry) ? Number(input.entry) : null;
  const target1 = Number.isFinite(input.target1) ? Number(input.target1) : null;
  const invalidacion = Number.isFinite(input.invalidacion)
    ? Number(input.invalidacion)
    : null;

  const resolve = (
    id: ThermometerStateId,
    detail: string | null,
  ): ThermometerResolutionV1 => ({
    state: id,
    label: thermometerState(id).label,
    detail,
    source: THERMOMETER_SOURCE,
  });

  if (entry == null || mark == null) {
    return resolve(
      "sin_entrada",
      entry == null
        ? "Sin entrada publicada: no hay nada que medir."
        : "Sin precio de referencia: no se puede medir la proximidad.",
    );
  }

  const invalidNote =
    invalidacion != null && mark <= invalidacion
      ? " El precio está por debajo de la invalidación: la geometría publicada ya no es válida."
      : "";

  if (target1 != null && mark >= target1) {
    return resolve(
      "extendido",
      `Precio ${formatLevel(mark)} en o por encima del Objetivo 1 (${formatLevel(target1)}).${invalidNote}`,
    );
  }
  if (mark >= entry) {
    return resolve(
      "caliente",
      `Precio ${formatLevel(mark)} en la zona de activación (entrada ${formatLevel(entry)}).${invalidNote}`,
    );
  }
  const distancePct = ((mark - entry) / entry) * 100;
  const distance = formatDistanceToEntry(distancePct);
  if (Math.abs(distancePct) <= THERMOMETER_NEAR_ENTRY_PCT) {
    return resolve(
      "templado",
      `El precio está ${distance}; la entrada se considera cerca dentro del ${formatDecimalEs(THERMOMETER_NEAR_ENTRY_PCT, 0, 2)} %.${invalidNote}`,
    );
  }
  return resolve(
    "frio",
    `El precio está ${distance}; fuera de la banda del ${formatDecimalEs(THERMOMETER_NEAR_ENTRY_PCT, 0, 2)} %.${invalidNote}`,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 5 · Formateadores (es-ES, sin inventar ceros)
// ─────────────────────────────────────────────────────────────────────────────

const ES_LOCALE = "es-ES";

function formatDecimalEs(
  value: number,
  minimumFractionDigits: number,
  maximumFractionDigits: number,
): string {
  return value.toLocaleString(ES_LOCALE, {
    minimumFractionDigits,
    maximumFractionDigits,
  });
}

/** Precio de nivel con 2 decimales es-ES; ausencia declarada. */
export function formatLevel(price: number | null | undefined): string {
  if (price == null || !Number.isFinite(price)) return "Sin nivel medido";
  return formatDecimalEs(price, 2, 2);
}

/** «Comprar por encima de 9,72» — precio de activación. */
export function formatEntryAbove(price: number | null | undefined): string {
  if (price == null || !Number.isFinite(price)) return "Sin entrada publicada";
  return `Comprar por encima de ${formatLevel(price)}`;
}

/** «Vender por debajo de 9,38» — nivel de invalidación. */
export function formatInvalidationBelow(price: number | null | undefined): string {
  if (price == null || !Number.isFinite(price)) return "Sin invalidación publicada";
  return `Vender por debajo de ${formatLevel(price)}`;
}

/**
 * Distancia relativa a la entrada, tal como la calcula `entryMarkDistance`
 * ((mark − entry) / entry × 100). Positivo = por encima.
 */
export function formatDistanceToEntry(
  distancePct: number | null | undefined,
): string {
  if (distancePct == null || !Number.isFinite(distancePct)) {
    return "sin distancia medida";
  }
  const absolute = formatDecimalEs(Math.abs(distancePct), 1, 2);
  if (Math.abs(distancePct) < 0.05) return "en la entrada";
  return distancePct > 0
    ? `un ${absolute} % por encima de la entrada`
    : `un ${absolute} % por debajo de la entrada`;
}

/** «68 / 100» o «Sin medir» — calidad de señal (IO), nunca un 0 fabricado. */
export function formatConfidence(ioScore: number | null | undefined): string {
  if (ioScore == null || !Number.isFinite(ioScore)) return "Sin medir";
  return `${Math.round(ioScore)} / 100`;
}

/**
 * «★★★★☆» o «Sin medir». Ojo: `map_io_to_stars(null)` devuelve 3 en el motor;
 * la UI no debe pintar ese 3 como una medición.
 */
export function formatDictamenStars(
  stars: number | null | undefined,
): string {
  if (stars == null || !Number.isFinite(stars)) return "Sin medir";
  const clamped = Math.min(5, Math.max(0, Math.round(stars)));
  return `${"★".repeat(clamped)}${"☆".repeat(5 - clamped)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// 6 · Términos retirados (guarda de superficie)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Términos que no deben aparecer en las superficies de recomendación. La guarda
 * los prohíbe SOLO ahí: «Vigilar» sigue siendo válido como categoría WATCH de
 * Mesa y `gate_veto` sigue existiendo como código de diagnóstico.
 */
export const MARKET_VOCABULARY_RETIRED_TERMS: ReadonlyArray<string> = [
  "Postura sugerida hoy",
  "Sobrecomprado",
  "★ dictamen ≠ ★ TOP",
  "trigger",
  "Thaw",
];

// ─────────────────────────────────────────────────────────────────────────────
// 7 · Soportes, resistencias y estructura (S2) — vocabulario propio
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Etiquetas de los niveles CALCULADOS. No se reutilizan para los niveles que el
 * usuario dibuja a mano (`SR_PRESETS`), que conservan «Soporte» / «Resistencia».
 */
export const MARKET_LEVEL_KINDS = ["support", "resistance"] as const;

export const MARKET_LEVEL_STATES = [
  "detectado",
  "no_fiable",
  "roto",
  "en_precio",
  "no_disponible",
] as const;

export const MARKET_LEVEL_REASONS = [
  "sin_velas",
  "historico_insuficiente",
  "velas_invalidas",
  "sin_atr",
  "sin_pivotes",
  "un_solo_toque",
  "sin_toque_reciente",
  "absorbido_por_nivel_mas_fuerte",
  "precio_en_nivel",
  "nivel_roto",
  "ultima_vela_en_curso",
] as const;

export const MARKET_STRUCTURE_TREND_IDS = [
  "ascendente",
  "descendente",
  "en_rango",
  "sin_estructura",
] as const;

export const MARKET_LEVEL_KIND_LABELS: Record<MarketLevelKindV1, string> = {
  support: "Soporte calculado",
  resistance: "Resistencia calculada",
};

/** Etiqueta corta para el eje del gráfico (nunca se confunde con lo manual). */
export const MARKET_LEVEL_KIND_SHORT_LABELS: Record<MarketLevelKindV1, string> = {
  support: "S·calc",
  resistance: "R·calc",
};

export const MARKET_LEVEL_STATE_LABELS: Record<MarketLevelStateV1, string> = {
  detectado: "Detectado",
  no_fiable: "No fiable",
  roto: "Roto",
  en_precio: "En precio",
  no_disponible: "No disponible",
};

export const MARKET_LEVEL_REASON_LABELS: Record<MarketLevelReasonV1, string> = {
  sin_velas: "Sin datos OHLCV",
  historico_insuficiente: "Histórico insuficiente",
  velas_invalidas: "Velas inválidas en la ventana",
  sin_atr: "Sin ATR calculable en la ventana",
  sin_pivotes: "Sin pivotes confirmados en la ventana",
  un_solo_toque: "Un solo toque",
  sin_toque_reciente: "Dos toques sin toque reciente",
  absorbido_por_nivel_mas_fuerte: "Absorbido por un nivel más fuerte",
  precio_en_nivel: "El precio está en el nivel",
  nivel_roto: "Nivel roto por el precio",
  ultima_vela_en_curso:
    "Última vela en curso: el ATR puede variar; los pivotes confirmados no repintan",
};

/**
 * Estructura de pivotes. **No** es la tendencia del parte diario: `Lateral` de
 * S1 significa ADX ≤ 25 y aquí no se usa. Una estructura «en rango» describe
 * pivotes que no progresan, no una fuerza medida.
 */
export const MARKET_STRUCTURE_TREND_LABELS: Record<
  MarketStructureTrendIdV1,
  string
> = {
  ascendente: "Estructura ascendente",
  descendente: "Estructura descendente",
  en_rango: "Estructura en rango",
  sin_estructura: "Sin estructura suficiente",
};

/** Nombre del método, para la leyenda de procedencia. */
export const MARKET_STRUCTURE_METHOD_LABEL =
  "Pivotes de swing agrupados por ATR";

export function marketLevelKindLabel(
  kind: MarketLevelKindV1,
): string {
  return MARKET_LEVEL_KIND_LABELS[kind];
}

export function marketLevelKindShortLabel(
  kind: MarketLevelKindV1,
): string {
  return MARKET_LEVEL_KIND_SHORT_LABELS[kind];
}

/** Etiqueta visible de un estado; `null` si el código no está en la tabla. */
export function marketLevelStateLabel(state: string): string | null {
  return MARKET_LEVEL_STATE_LABELS[state as MarketLevelStateV1] ?? null;
}

/** Etiqueta visible de un motivo; `null` si el código no está en la tabla. */
export function marketLevelReasonLabel(reason: string): string | null {
  return MARKET_LEVEL_REASON_LABELS[reason as MarketLevelReasonV1] ?? null;
}

/** Etiqueta visible de una estructura de pivotes; `null` si no está en la tabla. */
export function marketStructureTrendLabel(
  id: string | null | undefined,
): string | null {
  if (!id) return null;
  return MARKET_STRUCTURE_TREND_LABELS[id as MarketStructureTrendIdV1] ?? null;
}

/**
 * Motivos listos para pintar: traducidos, sin duplicados y sin códigos crudos.
 * Un código desconocido se omite en vez de mostrarse en `snake_case`.
 */
export function visibleLevelReasons(
  reasons: readonly string[] | null | undefined,
  options: { maxVisible?: number } = {},
): { visible: string[]; hidden: string[]; hiddenCount: number } {
  const maxVisible = options.maxVisible ?? 3;
  const ordered: string[] = [];
  for (const reason of reasons ?? []) {
    const label = marketLevelReasonLabel(reason);
    if (!label || ordered.includes(label)) continue;
    ordered.push(label);
  }
  const visible = ordered.slice(0, Math.max(0, maxVisible));
  const hidden = ordered.slice(visible.length);
  return { visible, hidden, hiddenCount: hidden.length };
}
