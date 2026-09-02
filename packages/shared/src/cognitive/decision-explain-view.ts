/**
 * DecisionExplainView — proyección canónica «Por qué» (V1.66).
 * Composición determinista sobre DecisionJournalStudyViewV1 + policy opts.
 * Mercado / Hoy / Journal / Operaciones leen el mismo explain view.
 * No LLM · no muta decisión.
 *
 * @see docs/engineering/spec-v166-decision-explainability-2026-09-02.md
 */

import {
  DECISION_JOURNAL_STUDY_ARTIFACT,
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_STRENGTH_BAND_LABELS,
  journalStudyConsensusPercents,
  type DecisionJournalStudyViewV1,
  type JournalStudyOpinion,
  type JournalStudyStrengthBand,
} from "./decision-journal-study.js";
import {
  MERCADO_COCKPIT_PHASE_LABEL,
  resolveMercadoCockpitPhase,
  type MercadoCockpitPhase,
} from "./mercado-cockpit-phase.js";
import type { PositionSecondaryConditionV1 } from "./position-operating-truth.js";
import type { EntryConditionV1, TradePlanWhyNotV1 } from "./trade-plan.js";

export const DECISION_EXPLAIN_VIEW_ARTIFACT = "ART-DECISION-EXPLAIN-VIEW";
export const DECISION_EXPLAIN_VIEW_SCHEMA = "1.0.0";

export const TRADE_PLAN_WHY_NOT_LABELS: Record<TradePlanWhyNotV1, string> = {
  fit: "No encaja en la cartera",
  entry: "Entrada aún no lista",
  freshness: "Datos no frescos",
  mandate: "Sin mandato abierto",
  expired: "La decisión caducó",
  no_stop: "Falta stop estructural",
  regime: "Régimen no admite longs",
  orphan: "Sin paquete de decisión",
  rr: "Riesgo/beneficio insuficiente",
  legacy_projection: "Sin plan vivo (proyección; motivo desconocido)",
};

const ENTRY_CONDITION_LABELS: Record<EntryConditionV1, string> = {
  ready: "Entrada lista",
  wait: "Esperar confirmación",
  none: "Sin condición de entrada",
};

export type DecisionExplainWhyNotV1 = {
  code: string;
  label: string;
};

export type DecisionExplainViewV1 = {
  artifactType: typeof DECISION_EXPLAIN_VIEW_ARTIFACT;
  schemaVersion: typeof DECISION_EXPLAIN_VIEW_SCHEMA;
  thesis: {
    opinion: string | null;
    strength: string | null;
    summary: string | null;
  };
  signals: {
    consensus: string[];
    indicators: string[];
    trends: string[];
  };
  conditions: {
    phase: string | null;
    entryCondition: string | null;
    whyNot: DecisionExplainWhyNotV1[];
  };
  invalidators: string[];
  policy: {
    entriesBlocked: boolean;
    gateStatus: string | null;
    fitLabel: string | null;
    mandateLabel: string | null;
  };
  traceability: {
    asOf: string | null;
    source: string;
    decisionId: string | null;
  };
};

export type BuildDecisionExplainViewInputV1 = {
  study: DecisionJournalStudyViewV1;
  entriesBlocked?: boolean;
  gateStatus?: string | null;
  phase?: MercadoCockpitPhase | string | null;
  secondaryConditions?: PositionSecondaryConditionV1[];
  /** TradePlan whyNot when caller has the live plan (study view omits it). */
  whyNot?: TradePlanWhyNotV1[];
  entryCondition?: EntryConditionV1 | null;
  asOf?: string | null;
  source?: string | null;
};

export function formatTradePlanWhyNot(code: TradePlanWhyNotV1): string {
  return TRADE_PLAN_WHY_NOT_LABELS[code] ?? code;
}

function formatStrength(study: DecisionJournalStudyViewV1): string | null {
  const band = study.strengthBand as JournalStudyStrengthBand | null;
  if (band && band in JOURNAL_STUDY_STRENGTH_BAND_LABELS) {
    return JOURNAL_STUDY_STRENGTH_BAND_LABELS[band];
  }
  if (typeof study.strength === "number" && Number.isFinite(study.strength)) {
    return study.strength.toFixed(1);
  }
  return null;
}

function formatConsensusLines(study: DecisionJournalStudyViewV1): string[] {
  const consensus = study.consensus;
  if (!consensus || consensus.total <= 0) return [];
  const pct = journalStudyConsensusPercents(consensus);
  return [
    `Alcista ${pct.bullish}% (${consensus.bullish})`,
    `Neutral ${pct.neutral}% (${consensus.neutral})`,
    `Bajista ${pct.bearish}% (${consensus.bearish})`,
  ];
}

function formatIndicatorLines(study: DecisionJournalStudyViewV1): string[] {
  const lines: string[] = [];
  const indicators = study.indicators;
  if (!indicators) return lines;
  if (indicators.primary?.trim()) {
    lines.push(indicators.primary.trim());
  }
  if (indicators.confirmation?.trim()) {
    lines.push(indicators.confirmation.trim());
  }
  return lines;
}

function formatTrendLines(study: DecisionJournalStudyViewV1): string[] {
  return (study.trends ?? [])
    .map((t) => t.display?.trim() || t.label?.trim() || t.value?.trim() || "")
    .filter((line) => line.length > 0);
}

function inferEntryCondition(
  study: DecisionJournalStudyViewV1,
  explicit?: EntryConditionV1 | null,
): EntryConditionV1 {
  if (explicit) return explicit;
  const status = study.tradePlanStatus;
  if (status === "TRIGGERED") return "ready";
  if (status === "ARMED" || status === "WATCH") return "wait";
  return "none";
}

function inferWhyNotCodes(
  study: DecisionJournalStudyViewV1,
  explicit?: TradePlanWhyNotV1[],
): TradePlanWhyNotV1[] {
  if (explicit && explicit.length > 0) return explicit;
  if (study.tradePlanStatus === "EXPIRED") return ["expired"];
  return [];
}

function resolvePhaseLabel(
  study: DecisionJournalStudyViewV1,
  phase: MercadoCockpitPhase | string | null | undefined,
): string | null {
  if (typeof phase === "string" && phase.trim()) {
    const key = phase.trim() as MercadoCockpitPhase;
    if (key in MERCADO_COCKPIT_PHASE_LABEL) {
      return MERCADO_COCKPIT_PHASE_LABEL[key];
    }
    return phase.trim();
  }
  const resolved = resolveMercadoCockpitPhase({
    instrumentId: study.instrumentId,
    inEstudio: true,
    hasOpenPosition: false,
    inConfirmQueue: false,
    tradePlanStatus: study.tradePlanStatus,
    hasOperationalPlan: study.hasOperationalPlan,
  });
  return MERCADO_COCKPIT_PHASE_LABEL[resolved];
}

function buildWhyNotList(
  codes: TradePlanWhyNotV1[],
  secondaryConditions: PositionSecondaryConditionV1[] = [],
): DecisionExplainWhyNotV1[] {
  const items: DecisionExplainWhyNotV1[] = codes.map((code) => ({
    code,
    label: formatTradePlanWhyNot(code),
  }));
  for (const condition of secondaryConditions) {
    items.push({
      code: condition.kind,
      label: condition.label,
    });
  }
  return items;
}

export function buildDecisionExplainView(
  input: BuildDecisionExplainViewInputV1,
): DecisionExplainViewV1 {
  const { study } = input;
  const entriesBlocked = input.entriesBlocked === true;
  const gateStatus = input.gateStatus ?? null;
  const whyNotCodes = inferWhyNotCodes(study, input.whyNot);
  const entryCondition = inferEntryCondition(study, input.entryCondition);
  const whyNot = buildWhyNotList(whyNotCodes, input.secondaryConditions ?? []);

  const opinion =
    study.opinion != null
      ? JOURNAL_STUDY_OPINION_LABELS[study.opinion as JournalStudyOpinion]
      : null;

  const asOf =
    typeof input.asOf === "string" && input.asOf.trim()
      ? input.asOf.trim()
      : study.studiedAt?.trim() || null;

  return {
    artifactType: DECISION_EXPLAIN_VIEW_ARTIFACT,
    schemaVersion: DECISION_EXPLAIN_VIEW_SCHEMA,
    thesis: {
      opinion,
      strength: formatStrength(study),
      summary: study.decisionSummary?.trim() || null,
    },
    signals: {
      consensus: formatConsensusLines(study),
      indicators: formatIndicatorLines(study),
      trends: formatTrendLines(study),
    },
    conditions: {
      phase: resolvePhaseLabel(study, input.phase),
      entryCondition: ENTRY_CONDITION_LABELS[entryCondition],
      whyNot,
    },
    invalidators: [...(study.invalidation ?? [])],
    policy: {
      entriesBlocked,
      gateStatus,
      fitLabel: whyNotCodes.includes("fit")
        ? formatTradePlanWhyNot("fit")
        : null,
      mandateLabel: whyNotCodes.includes("mandate")
        ? formatTradePlanWhyNot("mandate")
        : null,
    },
    traceability: {
      asOf,
      source: input.source?.trim() || DECISION_JOURNAL_STUDY_ARTIFACT,
      decisionId: study.decisionId,
    },
  };
}

export type DecisionExplainSurfaceSnapshotV1 = Omit<
  DecisionExplainViewV1,
  "artifactType" | "schemaVersion"
>;

/** Snapshot estable para tests cross-surface (sin metadatos de artefacto). */
export function decisionExplainSurfaceSnapshot(
  view: DecisionExplainViewV1,
): DecisionExplainSurfaceSnapshotV1 {
  const { artifactType: _a, schemaVersion: _s, ...rest } = view;
  return rest;
}
