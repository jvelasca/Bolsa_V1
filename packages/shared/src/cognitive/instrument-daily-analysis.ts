/**
 * Análisis diario del valor — proyección única de lectura para DECISIÓN · MERCADO.
 *
 * NO calcula tendencia, régimen ni indicadores: solo proyecta artefactos ya
 * producidos (parte diario `study.trends` / `study.indicators`, `OperationalPlanViewV1`,
 * `MercadoTrailingCopyV1` y los `indicatorSpecs` de la estrategia del Lab).
 *
 * Regla dura: lo que no existe se declara en `gaps`; nunca se rellena a cero ni a verde.
 *
 * Consumidores: banda de análisis diario del panel OPERATIVA (hoy) y, en la fase
 * siguiente, las superficies HOY y Screeners (mismo modelo, sin duplicar copy).
 *
 * @see docs/PROJECT_PREMISES.md §6.4
 * @see docs/engineering/analisis-diario-operativa-mercado-2026-11-10.md
 */

import type { InstrumentStrategyTopSlotV1 } from "../instrument-strategy-top.js";
import type { StrategyDefinitionV1 } from "../research-platform.js";
import {
  strategySlotToIndicatorDetails,
  type StrategySlotIndicatorDetailV1,
} from "../strategy-top1-chart-indicators.js";
import type {
  DecisionJournalStudyViewV1,
  JournalStudyVigencia,
} from "./decision-journal-study.js";
import {
  MERCADO_COCKPIT_PHASE_LABEL,
  mercadoCockpitNoLevelsCopy,
  mercadoCockpitShowsPlanLevels,
  type MercadoCockpitPhase,
  type MercadoTrailingCopyV1,
} from "./mercado-cockpit-phase.js";
import {
  entryMarkDistance,
  targetProgressHint,
  type OperationalPlanViewV1,
} from "./operational-plan-view.js";

/** Tono de presentación derivado del `value` canónico (nunca al revés). */
export type DailyTrendToneV1 =
  | "bullish"
  | "bearish"
  | "range"
  | "mixed"
  | "unknown";

/** Una línea de tendencia del parte diario (`study.trends`). */
export type InstrumentDailyTrendLineV1 = {
  key: "short_term" | "background";
  /** «Corto plazo» / «De fondo». */
  label: string;
  /** Etiqueta canónica del estudio (p. ej. «Alcista»). */
  display: string;
  /** Solo presentación; `unknown` cuando el estudio no trae valor. */
  tone: DailyTrendToneV1;
  /** Indicador que sustenta la línea (ADX + DI / SMA), si el estudio lo declara. */
  basis: string | null;
};

/** Metadatos de frescura del parte diario. */
export type InstrumentDailyStudyMetaV1 = {
  studiedAt: string;
  ageMs: number | null;
  vigencia: JournalStudyVigencia | null;
  indicators: { primary: string | null; confirmation: string | null };
};

/** Seguimiento Lab: estrategia #1 e indicadores optimizados que la sustentan. */
export type InstrumentDailyTrackingV1 = {
  strategyRank: 1 | 2 | 3 | null;
  strategyLabel: string | null;
  indicators: StrategySlotIndicatorDetailV1[];
  /** Primera razón del coach; el resto se consulta en ¿Por qué?. */
  reason: string | null;
  evidenceLevel: "in_sample_only" | "lab_validated" | null;
  stabilityLabel: string | null;
  /** Hueco declarado del bloque (fuera de Estudio, sin Finalista, sin specs…). */
  gap: string | null;
};

/** Momento de entrada (fase sin posición abierta). */
export type InstrumentDailyEntryV1 = {
  state: MercadoCockpitPhase;
  stateLabel: string;
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
  expectedRR: number | null;
  /** (mark − entrada) / entrada × 100; null si falta alguno. */
  distancePct: number | null;
  /** Qué falta para operar (disparador pendiente, sin niveles, fill…). */
  missing: string | null;
};

/** Momento de salida (posición abierta). */
export type InstrumentDailyExitV1 = {
  stop: number | null;
  target1Hint: string;
  target2Hint: string;
  /** Copy de trailing; nunca se promueve a stop vigente. */
  trailingLabel: string | null;
  unrealizedR: number | null;
  invalidation: string | null;
};

/** Proyección completa del análisis diario de un valor. */
export type InstrumentDailyAnalysisV1 = {
  instrumentId: string;
  inEstudio: boolean;
  /** Hay parte diario con tendencia utilizable. */
  measured: boolean;
  studyMeta: InstrumentDailyStudyMetaV1 | null;
  trends: InstrumentDailyTrendLineV1[];
  tracking: InstrumentDailyTrackingV1;
  /** null cuando la posición está abierta (manda la salida). */
  entry: InstrumentDailyEntryV1 | null;
  /** null cuando no hay posición abierta. */
  exit: InstrumentDailyExitV1 | null;
  /** Huecos declarados, sin duplicados. */
  gaps: string[];
};

export type BuildInstrumentDailyAnalysisInput = {
  instrumentId: string;
  inEstudio: boolean;
  study: DecisionJournalStudyViewV1 | null;
  phase: MercadoCockpitPhase;
  /** `useInstrumentOperationalContext().showsPlanLevels`. */
  showsPlanLevels: boolean;
  plan: OperationalPlanViewV1;
  trailing: MercadoTrailingCopyV1;
  markPrice: number | null;
  slot: InstrumentStrategyTopSlotV1 | null;
  definition: Pick<StrategyDefinitionV1, "indicatorSpecs" | "presetKey"> | null;
  reasons: string[];
  evidenceLevel: "in_sample_only" | "lab_validated" | null;
  stabilityLabel: string | null;
};

const TREND_TONE_BY_VALUE: Record<string, DailyTrendToneV1> = {
  strong_bullish: "bullish",
  bullish: "bullish",
  bullish_stack: "bullish",
  weak: "range",
  bearish: "bearish",
  strong_bearish: "bearish",
  bearish_stack: "bearish",
  mixed: "mixed",
};

/** Traduce el `value` canónico del estudio a tono de presentación. */
export function dailyTrendTone(
  value: string | null | undefined,
): DailyTrendToneV1 {
  if (!value) return "unknown";
  return TREND_TONE_BY_VALUE[value] ?? "unknown";
}

function buildTrendLines(
  study: DecisionJournalStudyViewV1 | null,
): InstrumentDailyTrendLineV1[] {
  const trends = study?.trends ?? [];
  return trends.map((trend) => ({
    key: trend.key,
    label: trend.label,
    display: trend.display ?? trend.value ?? "",
    tone: dailyTrendTone(trend.value),
    basis:
      trend.key === "short_term"
        ? (study?.indicators?.primary ?? null)
        : (study?.indicators?.confirmation ?? null),
  }));
}

function buildTracking(
  input: BuildInstrumentDailyAnalysisInput,
): InstrumentDailyTrackingV1 {
  const details = strategySlotToIndicatorDetails({
    slot: input.slot,
    definition: input.definition,
  });
  const gap = !input.inEstudio
    ? "Fuera de Estudio"
    : !input.slot
      ? "Sin Finalista #1 todavía"
      : details.items.length === 0
        ? "Estrategia sin indicadores declarados"
        : null;
  return {
    strategyRank: input.slot?.rank ?? null,
    strategyLabel: input.slot?.label ?? null,
    indicators: details.items,
    reason: input.reasons[0] ?? null,
    evidenceLevel: input.evidenceLevel,
    stabilityLabel: input.stabilityLabel,
    gap,
  };
}

function missingLevelsCopy(plan: OperationalPlanViewV1): string {
  const missing: string[] = [];
  if (plan.entry == null) missing.push("entrada");
  if (plan.stopVigente == null) missing.push("stop");
  if (plan.target1 == null) missing.push("T1");
  if (plan.target2 == null) missing.push("T2");
  if (missing.length === 0) return "Sin niveles operables";
  return `Sin ${missing.join(" / ")} todavía`;
}

/**
 * Copy de fase cuando el plan existe pero no publicó geometría. Evita el
 * «Plan sin niveles» genérico, que no distingue una propuesta en cola de un
 * plan armado: el estado ya es información, no se inventa el nivel.
 */
const PHASE_NO_GEOMETRY_COPY: Partial<Record<MercadoCockpitPhase, string>> = {
  preparada: "Preparada sin geometría publicada",
  disparada: "Disparador activo sin geometría publicada",
  propuesta: "Propuesta en cola · sin geometría publicada",
  confirmada: "Firma hecha · sin geometría publicada",
};

function buildEntry(
  input: BuildInstrumentDailyAnalysisInput,
): InstrumentDailyEntryV1 | null {
  if (input.phase === "posicion") return null;
  const state = input.phase;
  const stateLabel = MERCADO_COCKPIT_PHASE_LABEL[state];
  const noLevelsCopy = mercadoCockpitNoLevelsCopy(state);

  if (!input.showsPlanLevels || !input.plan.hasPlan) {
    return {
      state,
      stateLabel,
      entry: null,
      stop: null,
      target1: null,
      target2: null,
      expectedRR: null,
      distancePct: null,
      missing:
        noLevelsCopy ??
        PHASE_NO_GEOMETRY_COPY[state] ??
        missingLevelsCopy(input.plan),
    };
  }

  const distance = entryMarkDistance(input.plan.entry, input.markPrice);
  let missing: string | null = null;
  if (state === "preparada") missing = "Disparador pendiente";
  else if (state === "confirmada") missing = "Fill pendiente";
  else if (input.plan.entry == null || input.plan.stopVigente == null) {
    missing = missingLevelsCopy(input.plan);
  }

  return {
    state,
    stateLabel,
    entry: input.plan.entry,
    stop: input.plan.stopVigente,
    target1: input.plan.target1,
    target2: input.plan.target2,
    expectedRR: input.plan.expectedRR,
    distancePct: distance.distancePct,
    missing,
  };
}

function buildExit(
  input: BuildInstrumentDailyAnalysisInput,
): InstrumentDailyExitV1 | null {
  if (input.phase !== "posicion") return null;
  const { plan, trailing } = input;
  let trailingLabel: string | null = null;
  if (trailing.show) {
    trailingLabel = trailing.statusLabel ?? "Recogido en el stop vigente";
  }
  return {
    stop: plan.stopVigente,
    target1Hint: targetProgressHint(plan.target1Touched, plan.target1Managed),
    target2Hint: targetProgressHint(plan.target2Touched, plan.target2Managed),
    trailingLabel,
    unrealizedR: plan.unrealizedR,
    invalidation: input.study?.invalidation?.[0] ?? null,
  };
}

function collectGaps(
  input: BuildInstrumentDailyAnalysisInput,
  analysis: Pick<InstrumentDailyAnalysisV1, "measured" | "trends" | "tracking">,
): string[] {
  const gaps = new Set<string>();
  if (!input.inEstudio) gaps.add("Fuera de Estudio");
  if (!analysis.measured) gaps.add("Sin análisis diario todavía");
  const vigencia = input.study?.vigencia ?? null;
  if (vigencia === "expired") gaps.add("Parte diario caducado");
  if (analysis.trends.some((trend) => trend.tone === "unknown")) {
    gaps.add("Tendencia sin dato");
  }
  if (analysis.tracking.gap) gaps.add(analysis.tracking.gap);
  if (
    mercadoCockpitShowsPlanLevels(input.phase) &&
    input.phase !== "posicion" &&
    !input.plan.hasPlan
  ) {
    gaps.add("Plan sin niveles");
  }
  return Array.from(gaps);
}

/**
 * Construye la proyección de análisis diario de un valor.
 *
 * Determinista y sin efectos: mismas entradas ⇒ misma salida. No accede a red ni
 * a estado global; el caller decide de dónde vienen los artefactos.
 */
export function buildInstrumentDailyAnalysis(
  input: BuildInstrumentDailyAnalysisInput,
): InstrumentDailyAnalysisV1 {
  const trends = buildTrendLines(input.study);
  const tracking = buildTracking(input);
  const measured = Boolean(input.study && trends.length > 0);
  const studyMeta: InstrumentDailyStudyMetaV1 | null = input.study
    ? {
        studiedAt: input.study.studiedAt,
        ageMs: input.study.ageMs ?? null,
        vigencia: input.study.vigencia ?? null,
        indicators: {
          primary: input.study.indicators?.primary ?? null,
          confirmation: input.study.indicators?.confirmation ?? null,
        },
      }
    : null;

  const analysis = {
    instrumentId: input.instrumentId,
    inEstudio: input.inEstudio,
    measured,
    studyMeta,
    trends,
    tracking,
    entry: buildEntry(input),
    exit: buildExit(input),
    gaps: [] as string[],
  };
  analysis.gaps = collectGaps(input, analysis);
  return analysis;
}
