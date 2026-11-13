/**
 * S3 · Cartera del Asesor — proyección de LECTURA de una fila de cartera.
 *
 * Qué hace: reúne, para un valor, la recomendación del dictamen (S1), la tendencia
 * del parte diario, la fuerza del estudio, los soportes/resistencias calculados (S2)
 * y el momento operativo, y clasifica la fila en una de las cinco categorías de
 * presentación.
 *
 * Qué NO hace: **no recomienda**. La única recomendación visible es la del dictamen,
 * ya emitida por el motor. La tendencia, la fuerza, los niveles y el momento son
 * contexto independiente: no se combinan, no se ponderan y no pueden promover una
 * fila a «comprar». El clasificador solo mira dictamen + posición medida + causa de
 * `no_trade`; si mirase la coincidencia de indicadores estaría recomendando.
 *
 * Regla dura: lo que no se midió se declara. `portfolioMeasured=false` nunca se
 * presenta como «sin posición», y una ausencia de niveles no fabrica un nivel 0.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 * @see docs/engineering/glosario-mercado-asesor-2026-11-12.md
 * @see docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md
 */

import type { PositionDto, ListDataFreshnessStatus } from "../types.js";
import {
  type InstrumentDailyOpinionSource,
  type InstrumentDailyOpinionStance,
  type InstrumentDailyOpinionV1,
} from "../instrument-daily-opinion.js";
import {
  JOURNAL_STUDY_STRENGTH_BAND_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  type DecisionJournalStudyViewV1,
  type JournalStudyConsensusV1,
  type JournalStudyVigencia,
} from "./decision-journal-study.js";
import type { MercadoCockpitPhase } from "./mercado-cockpit-phase.js";
import { MERCADO_COCKPIT_PHASE_LABEL } from "./mercado-cockpit-phase.js";
import type { OperationalPlanViewV1 } from "./operational-plan-view.js";
import {
  formatConfidence,
  formatDictamenStars,
  formatLevel,
  marketLevelKindShortLabel,
  marketLevelStateLabel,
  marketStanceLabel,
  marketStructureTrendLabel,
  marketTrendLabel,
  marketTrendTone,
  resolveThermometer,
  visibleReasons,
  type MarketStanceFamily,
  type MarketTrendToneV1,
  type ThermometerResolutionV1,
} from "../market-vocabulary.js";
import {
  marketLevelIsDrawable,
  type MarketLevelV1,
  type MarketStructureResultV1,
} from "../market-structure.js";

// ─────────────────────────────────────────────────────────────────────────────
// 1 · Las cinco categorías de presentación
// ─────────────────────────────────────────────────────────────────────────────

export const ASESOR_CARTERA_STATE_IDS = [
  "recomendacion_favorable",
  "posicion_sin_respaldo",
  "posicion_abierta",
  "evaluado_sin_oportunidad",
  "sin_datos",
] as const;

export type AsesorCarteraStateIdV1 = (typeof ASESOR_CARTERA_STATE_IDS)[number];

export type AsesorCarteraStateDefinitionV1 = {
  id: AsesorCarteraStateIdV1;
  label: string;
  /** Qué significa. Nunca se lee como recomendación de compra o venta. */
  meaning: string;
  /** Orden de presentación en la lista (menor = antes). */
  rank: number;
};

/**
 * Orden de presentación: primero lo accionable por excepción (posición sin
 * respaldo), luego la señal favorable, luego cartera sana y por último lo que no
 * se pudo medir. El orden es de lectura, no de prioridad operativa.
 */
export const ASESOR_CARTERA_STATES: ReadonlyArray<AsesorCarteraStateDefinitionV1> =
  [
    {
      id: "posicion_sin_respaldo",
      label: "Posición sin respaldo",
      meaning:
        "Hay posición abierta y la estrategia del Lab ya no la sostiene. No es sobrecompra técnica ni una orden de venta.",
      rank: 0,
    },
    {
      id: "recomendacion_favorable",
      label: "Recomendación favorable",
      meaning:
        "El dictamen emitió compra y no hay posición abierta. Es una señal del motor, no una orden: la firma vive en Confirm.",
      rank: 1,
    },
    {
      id: "posicion_abierta",
      label: "Posición abierta",
      meaning:
        "Hay posición abierta; la recomendación del dictamen conserva su propio nombre.",
      rank: 2,
    },
    {
      id: "evaluado_sin_oportunidad",
      label: "Sin oportunidad",
      meaning:
        "El dictamen se evaluó y no emitió compra. No es un hueco de datos.",
      rank: 3,
    },
    {
      id: "sin_datos",
      label: "Sin datos suficientes",
      meaning:
        "Falta una medición imprescindible. Nunca se sustituye por una postura inventada.",
      rank: 4,
    },
  ];

export function asesorCarteraStateDefinition(
  id: AsesorCarteraStateIdV1,
): AsesorCarteraStateDefinitionV1 {
  const found = ASESOR_CARTERA_STATES.find((state) => state.id === id);
  if (!found) throw new Error(`Estado de cartera desconocido: ${id}`);
  return found;
}

export function asesorCarteraStateLabel(id: AsesorCarteraStateIdV1): string {
  return asesorCarteraStateDefinition(id).label;
}

// ─────────────────────────────────────────────────────────────────────────────
// 2 · Clasificador (dictamen + posición medida + causa de no_trade)
// ─────────────────────────────────────────────────────────────────────────────

export type AsesorCarteraPositionFactsV1 = {
  /** `false` = la cartera no se leyó: no se puede afirmar «sin posición». */
  measured: boolean;
  hasOpenPosition: boolean;
};

export type ClassifyAsesorCarteraStateInput = {
  opinion: InstrumentDailyOpinionV1 | null;
  position: AsesorCarteraPositionFactsV1;
};

export type AsesorCarteraStateV1 = {
  id: AsesorCarteraStateIdV1;
  label: string;
  /** Matiz de la causa, cuando el estado no basta para explicarla. */
  detail: string | null;
  /** Huecos que impiden clasificar con certeza (vacío si se midió todo). */
  gaps: string[];
};

/** Causas de `no_trade` que declaran un hueco, no una lectura neutra. */
const NO_TRADE_UNMEASURED_CAUSES: ReadonlyArray<{
  reason: string;
  gap: string;
}> = [
  { reason: "position_unmeasured", gap: "Cartera sin medir" },
  { reason: "io_unmeasured", gap: "Calidad de señal sin medir" },
  { reason: "eod_data_stale", gap: "Sin cierre de sesión" },
];

/**
 * Clasifica la fila. Precedencia declarada y falsable:
 *
 * 1. Cartera no medida → `sin_datos` (nunca «sin posición»).
 * 2. Sin dictamen → `sin_datos`.
 * 3. `no_trade` por causa de medición → `sin_datos` con el hueco concreto.
 * 4. Posición abierta + `overbought` / `review_strategy` → `posicion_sin_respaldo`.
 * 5. Posición abierta (resto de posturas evaluadas) → `posicion_abierta`.
 * 6. Sin posición + `buy` → `recomendacion_favorable`.
 * 7. Sin posición + postura evaluada sin compra → `evaluado_sin_oportunidad`.
 * 8. Sin posición + `reduce` / `sell_exit` → `sin_datos` (postura de salida
 *    incoherente sin posición medida: se declara, no se inventa la posición).
 */
export function classifyAsesorCarteraState(
  input: ClassifyAsesorCarteraStateInput,
): AsesorCarteraStateV1 {
  const state = (id: AsesorCarteraStateIdV1, gaps: string[] = []) => ({
    id,
    label: asesorCarteraStateLabel(id),
    detail: null as string | null,
    gaps,
  });

  if (!input.position.measured) {
    return state("sin_datos", ["Cartera sin medir"]);
  }

  const opinion = input.opinion;
  if (!opinion) {
    return state("sin_datos", ["Sin dictamen"]);
  }

  const reasons = opinion.reasons ?? [];
  for (const cause of NO_TRADE_UNMEASURED_CAUSES) {
    if (reasons.includes(cause.reason as never)) {
      return state("sin_datos", [cause.gap]);
    }
  }

  const stance = opinion.stance;

  if (input.position.hasOpenPosition) {
    if (stance === "overbought" || stance === "review_strategy") {
      return {
        ...state("posicion_sin_respaldo"),
        detail:
          stance === "overbought"
            ? "La estrategia del Lab ya no respalda la posición"
            : "La estrategia del Lab falta o está caducada",
      };
    }
    return state("posicion_abierta");
  }

  switch (stance) {
    case "buy":
      return state("recomendacion_favorable");
    case "hold_watch":
    case "no_trade":
    case "review_strategy":
      return state("evaluado_sin_oportunidad");
    case "reduce":
    case "sell_exit":
      return state("sin_datos", ["Dictamen de salida sin posición medida"]);
    default:
      return state("sin_datos", ["Dictamen no reconocido"]);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 3 · Bloques de la fila
// ─────────────────────────────────────────────────────────────────────────────

export type AsesorCarteraQuoteSourceV1 = "mercado" | "cartera";

export type AsesorCarteraQuoteV1 = {
  price: number | null;
  changePct: number | null;
  label: string;
  changeLabel: string;
  measured: boolean;
  /**
   * De dónde sale el precio mostrado: `mercado` = lote de cotizaciones,
   * `cartera` = último precio de la posición. `null` = sin precio medido.
   * La fuente se declara para que un mark de cartera no pase por cierre.
   */
  source: AsesorCarteraQuoteSourceV1 | null;
  /** Fecha del cierre usado como precio (YYYY-MM-DD). No se inventa. */
  lastBarDate: string | null;
  expectedLastBarDate: string | null;
  /** Frescura declarada por el servidor; `null` = no declarada. */
  freshness: ListDataFreshnessStatus | null;
  /** `true` solo si el servidor declaró `stale`. */
  stale: boolean;
  staleLabel: string | null;
};

export type AsesorCarteraRecommendationV1 = {
  measured: boolean;
  stance: InstrumentDailyOpinionStance | null;
  label: string;
  family: MarketStanceFamily | null;
  detail: string | null;
  confidence: number | null;
  confidenceLabel: string;
  starsLabel: string;
  /** ★ numéricas del dictamen; `null` = no medidas (no se fabrican). */
  dictamenStars: number | null;
  strategyStars: number | null;
  faScore: number | null;
  taScore: number | null;
  gateStatus: InstrumentDailyOpinionV1["gateStatus"] | null;
  distress: boolean;
  engineVersion: string | null;
  computedAt: string | null;
  reasons: string[];
  hiddenReasonCount: number;
  reasonsTooltip: string | null;
  asOfBarDate: string | null;
  source: InstrumentDailyOpinionSource | null;
  gaps: string[];
};

export type AsesorCarteraTrendV1 = {
  measured: boolean;
  label: string;
  tone: MarketTrendToneV1;
  basis: string | null;
  vigencia: JournalStudyVigencia | null;
  vigenciaLabel: string | null;
  /** Línea de corto plazo (o la que el parte declare como principal). */
  shortTermLabel: string | null;
  /** Línea de fondo (estructura de medias), si el parte la publica. */
  backgroundLabel: string | null;
  /** Indicador de confirmación (RSI/SMA) declarado por el parte. */
  confirmation: string | null;
  opinion: DecisionJournalStudyViewV1["opinion"];
  gaps: string[];
};

export type AsesorCarteraStrengthV1 = {
  measured: boolean;
  value: number | null;
  bandLabel: string | null;
  label: string;
  gaps: string[];
};

export type AsesorCarteraLevelsStateSummaryV1 = {
  detectado: number;
  enPrecio: number;
  roto: number;
  noFiable: number;
  noDisponible: number;
};

export type AsesorCarteraLevelsV1 = {
  measured: boolean;
  support: number | null;
  resistance: number | null;
  supportLabel: string;
  resistanceLabel: string;
  supportDistancePct: number | null;
  resistanceDistancePct: number | null;
  supportDistanceLabel: string | null;
  resistanceDistanceLabel: string | null;
  /** Estructura de pivotes declarada por S2 (vocabulario propio). */
  structureId: string | null;
  structureLabel: string | null;
  atrRef: number | null;
  close: number | null;
  stateSummary: AsesorCarteraLevelsStateSummaryV1;
  /** Estado del nivel más cercano cuando no hay ninguno dibujable. */
  nearestStateLabel: string | null;
  detail: string;
  gaps: string[];
};

export type AsesorCarteraMomentV1 = {
  phase: MercadoCockpitPhase;
  phaseLabel: string;
  kind: "posicion" | "entrada";
  thermometer: ThermometerResolutionV1 | null;
  entry: number | null;
  invalidation: number | null;
  target1: number | null;
  target2: number | null;
  /** Geometría publicada, lista para leer (`E … · S … · T1 …`). */
  geometryLabel: string | null;
  detail: string | null;
  gaps: string[];
};

export type AsesorCarteraPositionV1 = {
  measured: boolean;
  hasOpenPosition: boolean;
  quantity: number | null;
  avgCost: number | null;
  unrealizedPnlPct: number | null;
  label: string;
  detail: string | null;
  gaps: string[];
};

export type AsesorCarteraStructureProvenanceV1 = {
  methodId: string;
  methodVersion: number;
  timeframe: string;
  bars: number;
  atrRef: number | null;
  inputSignature: string;
  status: MarketStructureResultV1["status"];
  close: number | null;
  supportPivots: number;
  resistancePivots: number;
};

export type AsesorCarteraStudyDetailV1 = {
  consensus: JournalStudyConsensusV1 | null;
  invalidation: string[];
  nextReviewAt: string | null;
  expectedRR: number | null;
  riskAmount: number | null;
  direction: DecisionJournalStudyViewV1["direction"];
  hasOperationalPlan: boolean;
  decisionSummary: string | null;
};

export type AsesorCarteraRowV1 = {
  instrumentId: string;
  symbol: string;
  name: string;
  quote: AsesorCarteraQuoteV1;
  recommendation: AsesorCarteraRecommendationV1;
  trend: AsesorCarteraTrendV1;
  strength: AsesorCarteraStrengthV1;
  levels: AsesorCarteraLevelsV1;
  moment: AsesorCarteraMomentV1;
  position: AsesorCarteraPositionV1;
  state: AsesorCarteraStateV1;
  /** Procedencia de S2 para el detalle técnico. `null` si no se midió. */
  structureProvenance: AsesorCarteraStructureProvenanceV1 | null;
  /** Resto del parte diario para el detalle técnico. `null` si no hay parte. */
  studyDetail: AsesorCarteraStudyDetailV1 | null;
  /** Huecos declarados de la fila, sin duplicados. */
  gaps: string[];
};

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatPctEs(value: number | null): string {
  if (!finite(value)) return "sin variación medida";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2).replace(".", ",")} %`;
}

function uniqueGaps(gaps: ReadonlyArray<string>): string[] {
  return Array.from(new Set(gaps.filter(Boolean)));
}

// ── Precio ──────────────────────────────────────────────────────────────────

function buildQuote(input: {
  price: number | null;
  changePct: number | null;
  source?: AsesorCarteraQuoteSourceV1 | null;
  lastBarDate?: string | null;
  expectedLastBarDate?: string | null;
  freshness?: ListDataFreshnessStatus | null;
}): AsesorCarteraQuoteV1 {
  const measured = finite(input.price);
  const freshness = input.freshness ?? null;
  const stale = freshness === "stale";
  return {
    price: measured ? input.price : null,
    changePct: finite(input.changePct) ? input.changePct : null,
    label: measured ? formatLevel(input.price) : "Sin precio",
    changeLabel: formatPctEs(finite(input.changePct) ? input.changePct : null),
    measured,
    source: measured ? (input.source ?? null) : null,
    lastBarDate: input.lastBarDate ?? null,
    expectedLastBarDate: input.expectedLastBarDate ?? null,
    freshness,
    stale,
    staleLabel: stale ? "Cierre desactualizado" : null,
  };
}

// ── Recomendación (siempre la del dictamen) ─────────────────────────────────

function buildRecommendation(
  opinion: InstrumentDailyOpinionV1 | null,
): AsesorCarteraRecommendationV1 {
  if (!opinion) {
    return {
      measured: false,
      stance: null,
      label: "Sin dictamen",
      family: null,
      detail: null,
      confidence: null,
      confidenceLabel: "Sin medir",
      starsLabel: "Sin medir",
      dictamenStars: null,
      strategyStars: null,
      faScore: null,
      taScore: null,
      gateStatus: null,
      distress: false,
      engineVersion: null,
      computedAt: null,
      reasons: [],
      hiddenReasonCount: 0,
      reasonsTooltip: null,
      asOfBarDate: null,
      source: null,
      gaps: ["Sin dictamen"],
    };
  }

  const stanceLabel = marketStanceLabel({
    stance: opinion.stance,
    reasons: opinion.reasons ?? [],
  });
  const ioScore = finite(opinion.ioScore) ? opinion.ioScore : null;
  const visible = visibleReasons(opinion.reasons, { ioScore });
  const strategyStars = finite(opinion.strategyStars)
    ? opinion.strategyStars
    : null;
  const tooltipParts = [...visible.visible, ...visible.hidden];

  return {
    measured: true,
    stance: opinion.stance,
    label: stanceLabel.label,
    family: stanceLabel.family,
    detail: stanceLabel.detail,
    confidence: ioScore,
    // `ioScore=null` no se pinta como ★3 medido: se declara el hueco.
    confidenceLabel: formatConfidence(ioScore),
    starsLabel: formatDictamenStars(ioScore == null ? null : opinion.dictamenStars),
    dictamenStars:
      ioScore == null ? null : finite(opinion.dictamenStars) ? opinion.dictamenStars : null,
    strategyStars,
    faScore: finite(opinion.faScore) ? opinion.faScore : null,
    taScore: finite(opinion.taScore) ? opinion.taScore : null,
    gateStatus: opinion.gateStatus ?? null,
    distress: Boolean(opinion.distress),
    engineVersion: opinion.engineVersion ?? null,
    computedAt: opinion.computedAt ?? null,
    reasons: visible.visible,
    hiddenReasonCount: visible.hiddenCount,
    reasonsTooltip: tooltipParts.length > 0 ? tooltipParts.join(" · ") : null,
    asOfBarDate: opinion.asOfBarDate ?? null,
    source: opinion.source ?? null,
    // Un score no medido nunca se colapsa a 0 ni a ★3: se declara el hueco y
    // `uniqueGaps` lo deduplica con la causa `io_unmeasured` del estado.
    gaps: ioScore == null ? ["Calidad de señal sin medir"] : [],
  };
}

// ── Tendencia y fuerza (del parte diario, sin recalcular) ───────────────────

function buildTrend(
  study: DecisionJournalStudyViewV1 | null,
): AsesorCarteraTrendV1 {
  const trends = study?.trends ?? [];
  const line =
    trends.find((trend) => trend.key === "short_term") ??
    trends.find((trend) => trend.key === "background") ??
    null;
  const background =
    trends.find((trend) => trend.key === "background") ?? null;
  const vigencia = study?.vigencia ?? null;
  const vigenciaLabel = vigencia ? JOURNAL_STUDY_VIGENCIA_LABELS[vigencia] : null;
  const backgroundLabel = background
    ? marketTrendLabel({ value: background.value, display: background.display })
    : null;
  const confirmation = study?.indicators?.confirmation ?? null;
  const opinion = study?.opinion ?? null;

  if (!line) {
    return {
      measured: false,
      label: "Sin dato de tendencia",
      tone: "unknown",
      basis: null,
      vigencia,
      vigenciaLabel,
      shortTermLabel: null,
      backgroundLabel,
      confirmation,
      opinion,
      gaps: [study ? "Tendencia sin dato" : "Sin parte diario"],
    };
  }

  return {
    measured: true,
    label: marketTrendLabel({ value: line.value, display: line.display }),
    tone: marketTrendTone(line.value),
    basis: study?.indicators?.primary ?? null,
    vigencia,
    vigenciaLabel,
    shortTermLabel: marketTrendLabel({
      value: line.value,
      display: line.display,
    }),
    backgroundLabel,
    confirmation,
    opinion,
    gaps: vigencia === "expired" ? ["Parte diario caducado"] : [],
  };
}

function buildStrength(
  study: DecisionJournalStudyViewV1 | null,
): AsesorCarteraStrengthV1 {
  const value = finite(study?.strength) ? study!.strength! : null;
  if (value == null) {
    return {
      measured: false,
      value: null,
      bandLabel: null,
      label: "Sin dato de fuerza",
      gaps: ["Sin dato de fuerza"],
    };
  }
  const band = study?.strengthBand ?? null;
  const bandLabel = band ? JOURNAL_STUDY_STRENGTH_BAND_LABELS[band] : null;
  const rounded = String(Math.round(value * 10) / 10).replace(".", ",");
  return {
    measured: true,
    value,
    bandLabel,
    label: `Fuerza ${rounded} / 10${bandLabel ? ` · ${bandLabel}` : ""}`,
    gaps: [],
  };
}

// ── Soportes y resistencias (S2, solo `detectado`) ─────────────────────────

function nearestDrawable(
  levels: readonly MarketLevelV1[],
  close: number | null,
): MarketLevelV1 | null {
  const drawable = levels.filter(marketLevelIsDrawable);
  if (drawable.length === 0) return null;
  if (close == null) return drawable[0] ?? null;
  return drawable.reduce((best, level) =>
    Math.abs(level.price - close) < Math.abs(best.price - close) ? level : best,
  );
}

function levelLabel(kind: MarketLevelV1["kind"], level: MarketLevelV1 | null): string {
  if (!level) return "Sin nivel fiable";
  return `${marketLevelKindShortLabel(kind)} ${formatLevel(level.price)}`;
}

function levelDistanceLabel(level: MarketLevelV1 | null): string | null {
  if (!level || !finite(level.distancePct)) return null;
  return formatPctEs(level.distancePct);
}

function levelStateSummary(
  levels: readonly MarketLevelV1[],
): AsesorCarteraLevelsStateSummaryV1 {
  const summary: AsesorCarteraLevelsStateSummaryV1 = {
    detectado: 0,
    enPrecio: 0,
    roto: 0,
    noFiable: 0,
    noDisponible: 0,
  };
  for (const level of levels) {
    if (level.state === "detectado") summary.detectado += 1;
    else if (level.state === "en_precio") summary.enPrecio += 1;
    else if (level.state === "roto") summary.roto += 1;
    else if (level.state === "no_fiable") summary.noFiable += 1;
    else summary.noDisponible += 1;
  }
  return summary;
}

/** El nivel más cercano al cierre, sea cual sea su estado (para declarar el hueco). */
function nearestAnyLevel(
  levels: readonly MarketLevelV1[],
  close: number | null,
): MarketLevelV1 | null {
  if (levels.length === 0) return null;
  if (close == null) return levels[0] ?? null;
  return levels.reduce((best, level) =>
    Math.abs(level.price - close) < Math.abs(best.price - close) ? level : best,
  );
}

const EMPTY_LEVEL_SUMMARY: AsesorCarteraLevelsStateSummaryV1 = {
  detectado: 0,
  enPrecio: 0,
  roto: 0,
  noFiable: 0,
  noDisponible: 0,
};

function unmeasuredLevels(
  detail: string,
  gap: string,
  extra: Partial<AsesorCarteraLevelsV1> = {},
): AsesorCarteraLevelsV1 {
  return {
    measured: false,
    support: null,
    resistance: null,
    supportLabel: "Sin nivel fiable",
    resistanceLabel: "Sin nivel fiable",
    supportDistancePct: null,
    resistanceDistancePct: null,
    supportDistanceLabel: null,
    resistanceDistanceLabel: null,
    structureId: null,
    structureLabel: null,
    atrRef: null,
    close: null,
    stateSummary: { ...EMPTY_LEVEL_SUMMARY },
    nearestStateLabel: null,
    detail,
    gaps: [gap],
    ...extra,
  };
}

function buildLevels(
  structure: MarketStructureResultV1 | null,
): AsesorCarteraLevelsV1 {
  if (!structure) {
    return unmeasuredLevels("Sin medición de estructura", "Sin medición de estructura");
  }

  const structureId = structure.structure?.id ?? null;
  const structureLabel = marketStructureTrendLabel(structureId);
  const atrRef = finite(structure.atrRef) ? structure.atrRef : null;
  const close = finite(structure.close) ? structure.close : null;
  const stateSummary = levelStateSummary([
    ...structure.supports,
    ...structure.resistances,
  ]);

  if (structure.status === "insufficient_history") {
    const detail = `Histórico insuficiente (${structure.window.bars} velas, mínimo ${structure.params.minBars})`;
    return unmeasuredLevels(detail, "Histórico insuficiente", {
      structureId,
      structureLabel,
      atrRef,
      close,
      stateSummary,
    });
  }

  if (structure.status !== "ok") {
    return unmeasuredLevels("Sin niveles calculables", "Sin niveles calculables", {
      structureId,
      structureLabel,
      atrRef,
      close,
      stateSummary,
    });
  }

  const support = nearestDrawable(structure.supports, close);
  const resistance = nearestDrawable(structure.resistances, close);
  const measured = support != null || resistance != null;
  const nearest = nearestAnyLevel(
    [...structure.supports, ...structure.resistances],
    close,
  );
  const nearestStateLabel = measured
    ? null
    : (marketLevelStateLabel(nearest?.state ?? "") ?? null);

  return {
    measured,
    support: support?.price ?? null,
    resistance: resistance?.price ?? null,
    supportLabel: levelLabel("support", support),
    resistanceLabel: levelLabel("resistance", resistance),
    supportDistancePct: support && finite(support.distancePct) ? support.distancePct : null,
    resistanceDistancePct:
      resistance && finite(resistance.distancePct) ? resistance.distancePct : null,
    supportDistanceLabel: levelDistanceLabel(support),
    resistanceDistanceLabel: levelDistanceLabel(resistance),
    structureId,
    structureLabel,
    atrRef,
    close,
    stateSummary,
    nearestStateLabel,
    detail: measured
      ? "Nivel calculado: informa, no valida una compra"
      : nearestStateLabel
        ? `Sin nivel dibujable · el más cercano está ${nearestStateLabel.toLowerCase()}`
        : "Sin niveles fiables en la ventana",
    gaps: measured ? [] : ["Sin niveles fiables"],
  };
}

// ── Momento (fase operativa + termómetro) ──────────────────────────────────

function buildPositionMomentDetail(plan: OperationalPlanViewV1): string | null {
  const parts: string[] = [];
  if (finite(plan.stopVigente)) parts.push(`Stop ${formatLevel(plan.stopVigente)}`);
  if (finite(plan.target1)) parts.push(`T1 ${formatLevel(plan.target1)}`);
  if (finite(plan.target2)) parts.push(`T2 ${formatLevel(plan.target2)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

/** Geometría publicada, siempre como lectura: `E … · S … · T1 … · T2 …`. */
function buildGeometryLabel(plan: OperationalPlanViewV1): string | null {
  const parts: string[] = [];
  if (finite(plan.entry)) parts.push(`E ${formatLevel(plan.entry)}`);
  if (finite(plan.stopVigente)) parts.push(`S ${formatLevel(plan.stopVigente)}`);
  if (finite(plan.target1)) parts.push(`T1 ${formatLevel(plan.target1)}`);
  if (finite(plan.target2)) parts.push(`T2 ${formatLevel(plan.target2)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function buildMoment(input: {
  phase: MercadoCockpitPhase;
  plan: OperationalPlanViewV1;
  markPrice: number | null;
  hasOpenPosition: boolean;
}): AsesorCarteraMomentV1 {
  const phaseLabel = MERCADO_COCKPIT_PHASE_LABEL[input.phase] ?? "Sin fase";
  const geometry = {
    entry: finite(input.plan.entry) ? input.plan.entry : null,
    invalidation: finite(input.plan.stopVigente) ? input.plan.stopVigente : null,
    target1: finite(input.plan.target1) ? input.plan.target1 : null,
    target2: finite(input.plan.target2) ? input.plan.target2 : null,
    geometryLabel: buildGeometryLabel(input.plan),
  };

  if (input.hasOpenPosition) {
    const detail = buildPositionMomentDetail(input.plan);
    return {
      phase: input.phase,
      phaseLabel,
      kind: "posicion",
      thermometer: null,
      ...geometry,
      detail,
      gaps: detail ? [] : ["Sin geometría de salida publicada"],
    };
  }

  const thermometer = resolveThermometer({
    markPrice: input.markPrice,
    entry: input.plan.entry,
    invalidacion: input.plan.stopVigente,
    target1: input.plan.target1,
  });

  return {
    phase: input.phase,
    phaseLabel,
    kind: "entrada",
    thermometer,
    ...geometry,
    detail: thermometer.detail,
    gaps: thermometer.state === "sin_entrada" ? ["Sin entrada publicada"] : [],
  };
}

// ── Posición ───────────────────────────────────────────────────────────────

function buildPosition(input: {
  measured: boolean;
  position: PositionDto | null;
}): AsesorCarteraPositionV1 {
  const position = input.position;
  const hasOpenPosition = Boolean(
    position && Math.abs(Number(position.quantity ?? 0)) > 0,
  );

  if (!input.measured) {
    return {
      measured: false,
      hasOpenPosition: false,
      quantity: null,
      avgCost: null,
      unrealizedPnlPct: null,
      label: "Cartera sin medir",
      detail: "No se pudo confirmar si hay posición",
      gaps: ["Cartera sin medir"],
    };
  }

  if (!hasOpenPosition || !position) {
    return {
      measured: true,
      hasOpenPosition: false,
      quantity: null,
      avgCost: null,
      unrealizedPnlPct: null,
      label: "Sin posición",
      detail: null,
      gaps: [],
    };
  }

  const quantity = finite(position.quantity) ? position.quantity : null;
  const avgCost = finite(position.avgCost) ? position.avgCost : null;
  const pnl = finite(position.unrealizedPnlPct)
    ? position.unrealizedPnlPct
    : null;
  const detailParts: string[] = [];
  if (quantity != null) detailParts.push(`${quantity} uds`);
  if (avgCost != null) detailParts.push(`coste ${formatLevel(avgCost)}`);
  if (pnl != null) detailParts.push(`P&L ${formatPctEs(pnl)}`);

  return {
    measured: true,
    hasOpenPosition: true,
    quantity,
    avgCost,
    unrealizedPnlPct: pnl,
    label: "Posición abierta",
    detail: detailParts.length > 0 ? detailParts.join(" · ") : null,
    gaps: [],
  };
}

function buildStudyDetail(
  study: DecisionJournalStudyViewV1 | null,
): AsesorCarteraStudyDetailV1 | null {
  if (!study) return null;
  return {
    consensus: study.consensus ?? null,
    invalidation: study.invalidation ?? [],
    nextReviewAt: study.nextReviewAt ?? null,
    expectedRR: finite(study.expectedRR) ? study.expectedRR : null,
    riskAmount: finite(study.riskAmount) ? study.riskAmount : null,
    direction: study.direction ?? null,
    hasOperationalPlan: Boolean(study.hasOperationalPlan),
    decisionSummary: study.decisionSummary ?? null,
  };
}

function buildStructureProvenance(
  structure: MarketStructureResultV1 | null,
): AsesorCarteraStructureProvenanceV1 | null {
  if (!structure) return null;
  return {
    methodId: structure.methodId,
    methodVersion: structure.methodVersion,
    timeframe: structure.window.timeframe,
    bars: structure.window.bars,
    atrRef: finite(structure.atrRef) ? structure.atrRef : null,
    inputSignature: structure.inputSignature,
    status: structure.status,
    close: finite(structure.close) ? structure.close : null,
    supportPivots: structure.supports.reduce(
      (total, level) => total + level.pivots.length,
      0,
    ),
    resistancePivots: structure.resistances.reduce(
      (total, level) => total + level.pivots.length,
      0,
    ),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 4 · Constructor de la fila
// ─────────────────────────────────────────────────────────────────────────────

export type BuildAsesorCarteraRowInput = {
  instrumentId: string;
  symbol: string;
  name: string;
  quote: {
    price: number | null;
    changePct: number | null;
    /** Origen del precio; aditivo y opcional para no romper llamadas previas. */
    source?: AsesorCarteraQuoteSourceV1 | null;
    lastBarDate?: string | null;
    expectedLastBarDate?: string | null;
    freshness?: ListDataFreshnessStatus | null;
  };
  opinion: InstrumentDailyOpinionV1 | null;
  study: DecisionJournalStudyViewV1 | null;
  structure: MarketStructureResultV1 | null;
  phase: MercadoCockpitPhase;
  plan: OperationalPlanViewV1;
  /** `null` = la cartera se leyó y no hay posición (o no se leyó: ver `portfolioMeasured`). */
  position: PositionDto | null;
  portfolioMeasured: boolean;
  /** Precio de referencia para el termómetro (último cierre / mark). */
  markPrice: number | null;
};

/**
 * Construye una fila determinista y sin efectos. No accede a red ni a estado.
 *
 * La recomendación sale **solo** del dictamen. `position` y `portfolioMeasured`
 * deciden si se puede hablar de posición; ni la tendencia ni los niveles influyen
 * en la clasificación.
 */
export function buildAsesorCarteraRow(
  input: BuildAsesorCarteraRowInput,
): AsesorCarteraRowV1 {
  const position = buildPosition({
    measured: input.portfolioMeasured,
    position: input.position,
  });
  const state = classifyAsesorCarteraState({
    opinion: input.opinion,
    position: {
      measured: input.portfolioMeasured,
      hasOpenPosition: position.hasOpenPosition,
    },
  });
  const recommendation = buildRecommendation(input.opinion);
  const trend = buildTrend(input.study);
  const strength = buildStrength(input.study);
  const levels = buildLevels(input.structure);
  const moment = buildMoment({
    phase: input.phase,
    plan: input.plan,
    markPrice: finite(input.markPrice) ? input.markPrice : null,
    hasOpenPosition: position.hasOpenPosition,
  });

  const gaps = uniqueGaps([
    ...position.gaps,
    ...recommendation.gaps,
    ...trend.gaps,
    ...strength.gaps,
    ...levels.gaps,
    ...moment.gaps,
    ...state.gaps,
  ]);

  return {
    instrumentId: input.instrumentId,
    symbol: input.symbol,
    name: input.name,
    quote: buildQuote(input.quote),
    recommendation,
    trend,
    strength,
    levels,
    moment,
    position,
    state,
    structureProvenance: buildStructureProvenance(input.structure),
    studyDetail: buildStudyDetail(input.study),
    gaps,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 5 · Filtro, orden y resumen
// ─────────────────────────────────────────────────────────────────────────────

export type AsesorCarteraFilterV1 = {
  state: AsesorCarteraStateIdV1 | "todos";
  onlyWithPosition: boolean;
};

export const DEFAULT_ASESOR_CARTERA_FILTER: AsesorCarteraFilterV1 = {
  state: "todos",
  onlyWithPosition: false,
};

export function filterAsesorCarteraRows(
  rows: readonly AsesorCarteraRowV1[],
  filter: AsesorCarteraFilterV1,
): AsesorCarteraRowV1[] {
  return rows.filter((row) => {
    if (filter.onlyWithPosition && !row.position.hasOpenPosition) return false;
    if (filter.state !== "todos" && row.state.id !== filter.state) return false;
    return true;
  });
}

/**
 * Orden de lectura: por categoría (ver `ASESOR_CARTERA_STATES`) y, dentro de la
 * categoría, por confianza descendente y símbolo. **No** ordena por coincidencia
 * de indicadores: eso sería una recomendación encubierta.
 */
export function sortAsesorCarteraRows(
  rows: readonly AsesorCarteraRowV1[],
): AsesorCarteraRowV1[] {
  const rankOf = (row: AsesorCarteraRowV1) =>
    asesorCarteraStateDefinition(row.state.id).rank;
  return [...rows].sort((a, b) => {
    const byState = rankOf(a) - rankOf(b);
    if (byState !== 0) return byState;
    const aConf = a.recommendation.confidence ?? -1;
    const bConf = b.recommendation.confidence ?? -1;
    if (aConf !== bConf) return bConf - aConf;
    return a.symbol.localeCompare(b.symbol);
  });
}

export type AsesorCarteraSummaryV1 = {
  total: number;
  byState: Record<AsesorCarteraStateIdV1, number>;
  withPosition: number;
  unmeasured: number;
  /** Filas con al menos un hueco declarado. */
  withGaps: number;
};

export function summarizeAsesorCartera(
  rows: readonly AsesorCarteraRowV1[],
): AsesorCarteraSummaryV1 {
  const byState = Object.fromEntries(
    ASESOR_CARTERA_STATE_IDS.map((id) => [id, 0]),
  ) as Record<AsesorCarteraStateIdV1, number>;
  let withPosition = 0;
  let unmeasured = 0;
  let withGaps = 0;
  for (const row of rows) {
    byState[row.state.id] += 1;
    if (row.position.hasOpenPosition) withPosition += 1;
    if (!row.position.measured) unmeasured += 1;
    if (row.gaps.length > 0) withGaps += 1;
  }
  return { total: rows.length, byState, withPosition, unmeasured, withGaps };
}