/**
 * DecisionExplainView — proyección canónica «Por qué» (V1.66 + V1.72 WHY rico).
 * Composición determinista sobre DecisionJournalStudyViewV1 + policy opts.
 * Mercado / Hoy / Journal / Operaciones leen el mismo explain view.
 * No LLM · no muta decisión · Ranking ≠ BUY (LONG ≠ COMPRAR).
 *
 * @see docs/engineering/spec-v172-decision-explainability-top-2026-09-02.md
 */

import type { DecisionAction } from "./decision-package.js";
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
import { entryMarkDistance } from "./operational-plan-view.js";
import type { PositionSecondaryConditionV1 } from "./position-operating-truth.js";
import type { EntryConditionV1, TradePlanWhyNotV1 } from "./trade-plan.js";

export const DECISION_EXPLAIN_VIEW_ARTIFACT = "ART-DECISION-EXPLAIN-VIEW";
export const DECISION_EXPLAIN_VIEW_SCHEMA = "1.1.0";

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

export const THESIS_DIRECTION_LABELS: Record<DecisionAction, string> = {
  recommend_long: "LONG",
  recommend_short: "SHORT",
  wait: "ESPERAR",
  reduce: "REDUCIR",
  exit_hint: "SALIDA",
};

export const DECISION_EXPLAIN_FACTOR_IDS = [
  "tendencia",
  "momentum",
  "volumen",
  "regimen",
  "rr",
  "riesgo",
  "perfil",
] as const;

export type DecisionExplainFactorIdV1 =
  (typeof DECISION_EXPLAIN_FACTOR_IDS)[number];

export type DecisionExplainFactorStateV1 = "pass" | "fail" | "unknown";

export type DecisionExplainWhyNotV1 = {
  code: string;
  label: string;
};

export type DecisionExplainScoreV1 = {
  value: number | null;
  label: string | null;
};

export type DecisionExplainThesisDirectionV1 = {
  action: DecisionAction | null;
  label: string | null;
};

export type DecisionExplainFactorV1 = {
  id: DecisionExplainFactorIdV1;
  label: string;
  state: DecisionExplainFactorStateV1;
  detail: string;
};

export type DecisionExplainLevelsV1 = {
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
};

export type DecisionExplainEntryGeometryV1 = {
  entry: number | null;
  currentPrice: number | null;
  distanceAbs: number | null;
  distancePct: number | null;
};

export type DecisionExplainAuthorizationV1 = {
  entriesBlocked: boolean;
  gateStatus: string | null;
  executionAllowed: boolean | null;
  copy: string;
};

export type DecisionExplainViewV1 = {
  artifactType: typeof DECISION_EXPLAIN_VIEW_ARTIFACT;
  schemaVersion: typeof DECISION_EXPLAIN_VIEW_SCHEMA;
  symbol: string | null;
  score: DecisionExplainScoreV1;
  thesisDirection: DecisionExplainThesisDirectionV1;
  factors: DecisionExplainFactorV1[];
  levels: DecisionExplainLevelsV1;
  entryGeometry: DecisionExplainEntryGeometryV1;
  authorization: DecisionExplainAuthorizationV1;
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

export type DecisionExplainTaComponentsV1 = {
  trend?: number;
  momentum?: number;
  volume?: number;
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
  /** Optional live mark / last close. Omit → distances null. */
  markPrice?: number | null;
  /** TA components; missing keys → factor unknown (no invented pass). */
  taComponents?: DecisionExplainTaComponentsV1 | null;
  regimeHint?: string | null;
  executionAllowed?: boolean | null;
  /** Override study.action when the live package is available. */
  action?: DecisionAction | null;
};

const AUTHORIZATION_COPY =
  "La tesis no es autorización ni orden. Ranking ≠ BUY.";

const FACTOR_LABELS: Record<DecisionExplainFactorIdV1, string> = {
  tendencia: "Tendencia",
  momentum: "Momentum",
  volumen: "Volumen",
  regimen: "Régimen",
  rr: "R/R",
  riesgo: "Riesgo",
  perfil: "Perfil",
};

export function formatTradePlanWhyNot(code: TradePlanWhyNotV1): string {
  return TRADE_PLAN_WHY_NOT_LABELS[code] ?? code;
}

export function formatExplainScoreLabel(value: number): string {
  return `${value.toFixed(1).replace(".", ",")}/10`;
}

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function formatStrength(study: DecisionJournalStudyViewV1): string | null {
  const band = study.strengthBand as JournalStudyStrengthBand | null;
  if (band && band in JOURNAL_STUDY_STRENGTH_BAND_LABELS) {
    return JOURNAL_STUDY_STRENGTH_BAND_LABELS[band];
  }
  if (finite(study.strength)) {
    return study.strength.toFixed(1);
  }
  return null;
}

function formatScore(
  study: DecisionJournalStudyViewV1,
): DecisionExplainScoreV1 {
  if (!finite(study.strength)) {
    return { value: null, label: null };
  }
  return {
    value: study.strength,
    label: formatExplainScoreLabel(study.strength),
  };
}

function resolveThesisDirection(
  study: DecisionJournalStudyViewV1,
  explicit?: DecisionAction | null,
): DecisionExplainThesisDirectionV1 {
  const action = explicit ?? study.action ?? null;
  if (!action) {
    return { action: null, label: null };
  }
  return {
    action,
    label: THESIS_DIRECTION_LABELS[action],
  };
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

function factor(
  id: DecisionExplainFactorIdV1,
  state: DecisionExplainFactorStateV1,
  detail: string,
): DecisionExplainFactorV1 {
  return { id, label: FACTOR_LABELS[id], state, detail };
}

function signedComponentState(value: number | undefined): {
  state: DecisionExplainFactorStateV1;
  detail: string;
} {
  if (!finite(value)) {
    return { state: "unknown", detail: "sin dato" };
  }
  if (value > 0) {
    return { state: "pass", detail: value.toFixed(2) };
  }
  if (value < 0) {
    return { state: "fail", detail: value.toFixed(2) };
  }
  return { state: "unknown", detail: "neutro" };
}

function tendenciaFactor(
  study: DecisionJournalStudyViewV1,
): DecisionExplainFactorV1 {
  const blob = [
    study.opinion ?? "",
    ...formatTrendLines(study),
    ...(study.trends ?? []).map((t) => t.value ?? ""),
  ]
    .join(" ")
    .toLowerCase();
  const bullish =
    study.opinion === "bullish" || /alcista|bull|up|strong_bull/.test(blob);
  const bearish = study.opinion === "bearish" || /bajista|bear|down/.test(blob);
  if (bullish && !bearish) {
    return factor(
      "tendencia",
      "pass",
      study.opinion
        ? JOURNAL_STUDY_OPINION_LABELS[study.opinion as JournalStudyOpinion]
        : (formatTrendLines(study)[0] ?? "alcista"),
    );
  }
  if (bearish && !bullish) {
    return factor(
      "tendencia",
      "fail",
      study.opinion
        ? JOURNAL_STUDY_OPINION_LABELS[study.opinion as JournalStudyOpinion]
        : (formatTrendLines(study)[0] ?? "bajista"),
    );
  }
  if (!study.opinion && formatTrendLines(study).length === 0) {
    return factor("tendencia", "unknown", "sin dato");
  }
  return factor("tendencia", "unknown", "señales mixtas");
}

function buildFactors(
  study: DecisionJournalStudyViewV1,
  whyNotCodes: TradePlanWhyNotV1[],
  entriesBlocked: boolean,
  taComponents: DecisionExplainTaComponentsV1 | null | undefined,
  regimeHint: string | null | undefined,
): DecisionExplainFactorV1[] {
  const momentum = signedComponentState(taComponents?.momentum);
  const volumen = signedComponentState(taComponents?.volume);

  let regimen: DecisionExplainFactorV1;
  if (whyNotCodes.includes("regime")) {
    regimen = factor("regimen", "fail", formatTradePlanWhyNot("regime"));
  } else if (typeof regimeHint === "string" && regimeHint.trim()) {
    const hint = regimeHint.trim().toLowerCase();
    if (/bajista|bear|no admite/.test(hint)) {
      regimen = factor("regimen", "fail", regimeHint.trim());
    } else if (/alcista|bull/.test(hint)) {
      regimen = factor("regimen", "pass", regimeHint.trim());
    } else {
      regimen = factor("regimen", "unknown", regimeHint.trim());
    }
  } else {
    regimen = factor("regimen", "unknown", "sin dato");
  }

  let rr: DecisionExplainFactorV1;
  if (whyNotCodes.includes("rr")) {
    rr = factor("rr", "fail", formatTradePlanWhyNot("rr"));
  } else if (finite(study.expectedRR) && study.expectedRR > 0) {
    rr = factor("rr", "pass", `${study.expectedRR.toFixed(1)}:1`);
  } else {
    rr = factor("rr", "unknown", "sin dato");
  }

  let riesgo: DecisionExplainFactorV1;
  if (entriesBlocked) {
    riesgo = factor("riesgo", "fail", "Entradas bloqueadas");
  } else if (finite(study.riskAmount) && study.riskAmount > 0) {
    riesgo = factor(
      "riesgo",
      "pass",
      `planificado ${study.riskAmount.toFixed(0)}`,
    );
  } else {
    riesgo = factor("riesgo", "unknown", "sin dato");
  }

  let perfil: DecisionExplainFactorV1;
  if (whyNotCodes.includes("fit")) {
    perfil = factor("perfil", "fail", formatTradePlanWhyNot("fit"));
  } else if (whyNotCodes.includes("mandate")) {
    perfil = factor("perfil", "fail", formatTradePlanWhyNot("mandate"));
  } else {
    perfil = factor("perfil", "unknown", "sin dato");
  }

  return [
    tendenciaFactor(study),
    factor("momentum", momentum.state, momentum.detail),
    factor("volumen", volumen.state, volumen.detail),
    regimen,
    rr,
    riesgo,
    perfil,
  ];
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

  const mark = finite(input.markPrice) ? input.markPrice : null;
  const entry = finite(study.entry) ? study.entry : null;
  const distance = entryMarkDistance(entry, mark);

  return {
    artifactType: DECISION_EXPLAIN_VIEW_ARTIFACT,
    schemaVersion: DECISION_EXPLAIN_VIEW_SCHEMA,
    symbol: study.symbol?.trim() || null,
    score: formatScore(study),
    thesisDirection: resolveThesisDirection(study, input.action),
    factors: buildFactors(
      study,
      whyNotCodes,
      entriesBlocked,
      input.taComponents,
      input.regimeHint,
    ),
    levels: {
      entry,
      stop: finite(study.stop) ? study.stop : null,
      target1: finite(study.target1) ? study.target1 : null,
      target2: finite(study.target2) ? study.target2 : null,
    },
    entryGeometry: {
      entry,
      currentPrice: mark,
      distanceAbs: distance.distanceAbs,
      distancePct: distance.distancePct,
    },
    authorization: {
      entriesBlocked,
      gateStatus,
      executionAllowed:
        typeof input.executionAllowed === "boolean"
          ? input.executionAllowed
          : null,
      copy: AUTHORIZATION_COPY,
    },
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
