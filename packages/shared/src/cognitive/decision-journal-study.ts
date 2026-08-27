/**
 * ART-DECISION-JOURNAL-STUDY — vista de presentación (ADR-036).
 * Proyecta DecisionSession + DecisionPackage + TradePlan a lenguaje de usuario.
 * No es fuente de verdad: no duplica geometría ni persiste estados de UI.
 */

import type { DecisionAction } from "./decision-package.js";
import type { ExitReasonV1 } from "./exit-plan.js";
import type { PositionStatusV1 } from "./position-state.js";
import type { DirectionalBias } from "./technical-assessment.js";
import type {
  TradePlanStatusV1,
  TradePlanV1,
  TradePlanWhyNotV1,
  TradePlanDirectionV1,
} from "./trade-plan.js";

export const DECISION_JOURNAL_STUDY_ARTIFACT = "ART-DECISION-JOURNAL-STUDY";
export const DECISION_JOURNAL_STUDY_SCHEMA = "1.0.0";

export const NO_OPERATIONAL_PLAN_COPY =
  "No existe todavía un plan operativo." as const;

export type JournalStudyUserStatus =
  | "in_progress"
  | "target_active"
  | "target_reached"
  | "invalidated"
  | "neutral"
  | "no_target"
  | "cancelled"
  | "closed";

export type JournalStudyOpinion = "bullish" | "bearish" | "neutral";

export type JournalStudyPeriod = "daily" | "weekly" | "monthly";

export type JournalStudyStrengthBand =
  | "very_strong"
  | "strong"
  | "moderate"
  | "weak"
  | "very_weak";

export type JournalStudyVigencia = "current" | "expiring_soon" | "expired";

export const JOURNAL_STUDY_STATUS_LABELS: Record<
  JournalStudyUserStatus,
  string
> = {
  in_progress: "En desarrollo",
  target_active: "Objetivo activo",
  target_reached: "Objetivo alcanzado",
  invalidated: "Invalidado",
  neutral: "Neutral",
  no_target: "Sin objetivo",
  cancelled: "Cancelado",
  closed: "Cerrado",
};

export const JOURNAL_STUDY_OPINION_LABELS: Record<JournalStudyOpinion, string> =
  {
    bullish: "Alcista",
    bearish: "Bajista",
    neutral: "Neutra",
  };

export const JOURNAL_STUDY_PERIOD_LABELS: Record<JournalStudyPeriod, string> = {
  daily: "Diario",
  weekly: "Semanal",
  monthly: "Mensual",
};

export const JOURNAL_STUDY_STRENGTH_BAND_LABELS: Record<
  JournalStudyStrengthBand,
  string
> = {
  very_strong: "Muy fuerte",
  strong: "Fuerte",
  moderate: "Moderada",
  weak: "Débil",
  very_weak: "Muy débil",
};

export const JOURNAL_STUDY_VIGENCIA_LABELS: Record<
  JournalStudyVigencia,
  string
> = {
  current: "Vigente",
  expiring_soon: "Próximo a caducar",
  expired: "Caducado",
};

export type JournalStudyGeometryV1 = {
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
  expectedRR: number | null;
  riskAmount: number | null;
  quantity: number | null;
  initialRiskR: number | null;
  positionValue: number | null;
  direction: TradePlanDirectionV1 | null;
  hasOperationalPlan: boolean;
};

export type JournalStudyConsensusV1 = {
  bullish: number;
  bearish: number;
  neutral: number;
  total: number;
};

export type JournalStudyTrendV1 = {
  key: "short_term" | "background";
  label: string;
  value: string | null;
  display: string | null;
};

export type JournalStudyIndicatorsV1 = {
  primary: string | null;
  confirmation: string | null;
};

export type DecisionJournalStudyViewV1 = {
  artifactType: typeof DECISION_JOURNAL_STUDY_ARTIFACT;
  schemaVersion: typeof DECISION_JOURNAL_STUDY_SCHEMA;
  sessionId: string;
  decisionId: string | null;
  instrumentId: string;
  symbol: string | null;
  name: string | null;
  studiedAt: string;
  ageMs: number | null;
  period: JournalStudyPeriod | null;
  timeframe: string | null;
  opinion: JournalStudyOpinion | null;
  status: JournalStudyUserStatus;
  strength: number | null;
  strengthBand: JournalStudyStrengthBand | null;
  vigencia: JournalStudyVigencia | null;
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
  expectedRR: number | null;
  riskAmount: number | null;
  quantity: number | null;
  initialRiskR: number | null;
  positionValue: number | null;
  direction: TradePlanDirectionV1 | null;
  hasOperationalPlan: boolean;
  userThesis: null;
  decisionSummary: string | null;
  analysisNotes: string[];
  trends: JournalStudyTrendV1[];
  consensus: JournalStudyConsensusV1;
  indicators: JournalStudyIndicatorsV1;
  invalidation: string[];
  nextReviewAt: string | null;
  tradePlanStatus: TradePlanStatusV1 | null;
  action: DecisionAction | null;
};

export type MapJournalStudyStatusInput = {
  positionStatus?: PositionStatusV1 | null;
  proposalStatus?: string | null;
  recommendationStatus?: string | null;
  exitPrimaryReason?: ExitReasonV1 | null;
  tradePlanStatus?: TradePlanStatusV1 | null;
  tradePlanWhyNot?: TradePlanWhyNotV1[] | null;
  action?: DecisionAction | null;
  bias?: DirectionalBias | null;
  hasOpenPosition?: boolean | null;
  hasLivePlan?: boolean | null;
  hasOperationalPlan?: boolean | null;
};

export type JournalStudyFactInput = {
  key: string;
  value: string;
  claim?: string;
  refs?: Record<string, string> | null;
};

export type BuildJournalStudyViewInput = {
  sessionId: string;
  decisionId?: string | null;
  instrumentId: string;
  symbol?: string | null;
  name?: string | null;
  studiedAt: string;
  now?: Date | string;
  timeframe?: string | null;
  action?: DecisionAction | null;
  bias?: DirectionalBias | null;
  overallConfidence?: number | null;
  tradePlan?: TradePlanV1 | null;
  positionStatus?: PositionStatusV1 | null;
  proposalStatus?: string | null;
  recommendationStatus?: string | null;
  exitPrimaryReason?: ExitReasonV1 | null;
  hasOpenPosition?: boolean | null;
  notes?: string[] | null;
  narrativeFacts?: string[] | null;
  assessments?: unknown[] | null;
  facts?: JournalStudyFactInput[] | null;
  invalidators?: string[] | null;
  reevaluateWhen?: string[] | null;
  thesisHealthWhy?: string[] | null;
  expiresAt?: string | null;
};

const EMPTY_GEOMETRY: JournalStudyGeometryV1 = {
  entry: null,
  stop: null,
  target1: null,
  target2: null,
  expectedRR: null,
  riskAmount: null,
  quantity: null,
  initialRiskR: null,
  positionValue: null,
  direction: null,
  hasOperationalPlan: false,
};

const EMPTY_CONSENSUS: JournalStudyConsensusV1 = {
  bullish: 0,
  bearish: 0,
  neutral: 0,
  total: 0,
};

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function journalStudyHasValidStop(
  plan: TradePlanV1 | null | undefined,
): boolean {
  if (!plan) return false;
  if ((plan.whyNot ?? []).includes("no_stop")) return false;
  const entry = finiteNumber(plan.entry);
  const stop = finiteNumber(plan.structuralStop);
  if (entry == null || entry <= 0 || stop == null) return false;
  if (plan.direction === "long") return stop < entry;
  if (plan.direction === "short") return stop > entry;
  return false;
}

/**
 * Honestidad: WATCH / BLOCKED / EXPIRED / sin stop válido → sin SL/TP.
 * Solo ARMED o TRIGGERED con stop válido exponen geometría operativa.
 */
export function journalStudyGeometry(
  plan: TradePlanV1 | null | undefined,
): JournalStudyGeometryV1 {
  if (!plan) return EMPTY_GEOMETRY;
  if (plan.status !== "ARMED" && plan.status !== "TRIGGERED") {
    return EMPTY_GEOMETRY;
  }
  if (!journalStudyHasValidStop(plan)) return EMPTY_GEOMETRY;
  const qty = finiteNumber(plan.quantity);
  return {
    entry: finiteNumber(plan.entry),
    stop: finiteNumber(plan.structuralStop),
    target1: finiteNumber(plan.target1),
    target2: finiteNumber(plan.target2),
    expectedRR: finiteNumber(plan.expectedRR),
    riskAmount: finiteNumber(plan.riskAmount),
    quantity: qty != null && qty > 0 ? qty : null,
    initialRiskR: finiteNumber(plan.initialRiskR),
    positionValue: finiteNumber(plan.positionValue),
    direction:
      plan.direction === "long" || plan.direction === "short"
        ? plan.direction
        : null,
    hasOperationalPlan: true,
  };
}

export function mapJournalStudyOpinion(input: {
  bias?: DirectionalBias | null;
  action?: DecisionAction | null;
}): JournalStudyOpinion | null {
  if (
    input.bias === "bullish" ||
    input.bias === "bearish" ||
    input.bias === "neutral"
  ) {
    return input.bias;
  }
  if (input.action === "recommend_long") return "bullish";
  if (input.action === "recommend_short") return "bearish";
  if (
    input.action === "wait" ||
    input.action === "reduce" ||
    input.action === "exit_hint"
  ) {
    return "neutral";
  }
  return null;
}

export function mapJournalStudyPeriod(
  timeframe?: string | null,
): JournalStudyPeriod | null {
  if (!timeframe) return null;
  const tf = timeframe.trim();
  const lower = tf.toLowerCase();
  if (
    lower === "1d" ||
    lower === "d" ||
    lower === "daily" ||
    lower === "1day"
  ) {
    return "daily";
  }
  if (
    lower === "1w" ||
    lower === "1wk" ||
    lower === "w" ||
    lower === "weekly" ||
    lower === "1week"
  ) {
    return "weekly";
  }
  if (
    tf === "1M" ||
    lower === "1mo" ||
    lower === "monthly" ||
    lower === "1month" ||
    lower === "1mon"
  ) {
    return "monthly";
  }
  return null;
}

export function mapJournalStudyStrength(
  overallConfidence?: number | null,
): number | null {
  if (
    typeof overallConfidence !== "number" ||
    !Number.isFinite(overallConfidence)
  ) {
    return null;
  }
  const clamped = Math.min(1, Math.max(0, overallConfidence));
  return Math.round(clamped * 100) / 10;
}

export function mapJournalStudyStrengthBand(
  strength: number | null | undefined,
): JournalStudyStrengthBand | null {
  if (typeof strength !== "number" || !Number.isFinite(strength)) return null;
  if (strength >= 8) return "very_strong";
  if (strength >= 6) return "strong";
  if (strength >= 4) return "moderate";
  if (strength >= 2) return "weak";
  if (strength >= 0) return "very_weak";
  return null;
}

export function mapJournalStudyVigencia(input: {
  now: Date;
  expiresAt?: string | null;
}): JournalStudyVigencia | null {
  const raw = input.expiresAt?.trim();
  if (!raw) return null;
  const expires = new Date(raw);
  if (Number.isNaN(expires.getTime())) return null;
  if (input.now.getTime() > expires.getTime()) return "expired";
  const remainingMs = expires.getTime() - input.now.getTime();
  if (remainingMs <= 24 * 60 * 60 * 1000) return "expiring_soon";
  return "current";
}

export function mapJournalStudyAgeMs(
  studiedAt: string,
  now: Date,
): number | null {
  const at = new Date(studiedAt);
  if (Number.isNaN(at.getTime())) return null;
  const age = now.getTime() - at.getTime();
  return age >= 0 ? age : 0;
}

export function formatJournalStudyAge(
  ageMs: number | null | undefined,
): string | null {
  if (typeof ageMs !== "number" || !Number.isFinite(ageMs) || ageMs < 0) {
    return null;
  }
  const minutes = Math.round(ageMs / 60_000);
  if (minutes < 60) return `${Math.max(1, minutes)}m`;
  const hours = Math.round(ageMs / 3_600_000);
  if (hours < 48) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days} ${days === 1 ? "día" : "días"}`;
}

function phaseStatus(value?: string | null): string {
  return (value ?? "").trim().toLowerCase();
}

export function mapJournalStudyStatus(
  input: MapJournalStudyStatusInput,
): JournalStudyUserStatus {
  const positionStatus = input.positionStatus ?? null;
  const proposal = phaseStatus(
    input.proposalStatus ?? input.recommendationStatus,
  );
  const exitReason = input.exitPrimaryReason ?? null;
  const tpStatus = input.tradePlanStatus ?? null;
  const whyNot = input.tradePlanWhyNot ?? [];
  const action = input.action ?? null;
  const bias = input.bias ?? null;
  const hasOpenPosition =
    input.hasOpenPosition ??
    (positionStatus === "OPEN" ||
      positionStatus === "PARTIAL" ||
      positionStatus === "PROTECTED");
  const hasLivePlan =
    input.hasLivePlan ?? (tpStatus != null && tpStatus !== "EXPIRED");
  const hasOperationalPlan = Boolean(input.hasOperationalPlan);

  if (positionStatus === "CLOSED") return "closed";
  if (proposal === "rejected" || proposal === "superseded") return "cancelled";
  if (exitReason === "THESIS_INVALIDATION") return "invalidated";
  if (exitReason === "TARGET_1" || exitReason === "TARGET_2") {
    return "target_reached";
  }
  if (tpStatus === "TRIGGERED" && (hasOpenPosition || hasLivePlan)) {
    return "target_active";
  }

  const waitOrNeutral = action === "wait" || bias === "neutral";
  if (waitOrNeutral && !hasOperationalPlan) return "neutral";

  const noPlan = tpStatus == null;
  const noStop = whyNot.includes("no_stop");
  if (noPlan || noStop) return "no_target";

  const directional =
    bias === "bullish" ||
    bias === "bearish" ||
    action === "recommend_long" ||
    action === "recommend_short";
  if ((tpStatus === "ARMED" || tpStatus === "WATCH") && directional) {
    return "in_progress";
  }

  return "closed";
}

function readBias(value: unknown): JournalStudyOpinion | null {
  if (!value || typeof value !== "object") return null;
  const rec = value as Record<string, unknown>;
  const direct = rec.bias;
  if (direct === "bullish" || direct === "bearish" || direct === "neutral") {
    return direct;
  }
  const meta = rec.metadata;
  if (meta && typeof meta === "object") {
    const nested = (meta as Record<string, unknown>).bias;
    if (nested === "bullish" || nested === "bearish" || nested === "neutral") {
      return nested;
    }
  }
  return null;
}

export function mapJournalStudyConsensus(
  assessments: unknown[] | null | undefined,
): JournalStudyConsensusV1 {
  if (!Array.isArray(assessments) || assessments.length === 0) {
    return EMPTY_CONSENSUS;
  }
  let bullish = 0;
  let bearish = 0;
  let neutral = 0;
  for (const item of assessments) {
    const bias = readBias(item);
    if (bias === "bullish") bullish += 1;
    else if (bias === "bearish") bearish += 1;
    else if (bias === "neutral") neutral += 1;
  }
  return {
    bullish,
    bearish,
    neutral,
    total: bullish + bearish + neutral,
  };
}

export function journalStudyConsensusPercents(
  consensus: JournalStudyConsensusV1,
): { bullish: number; bearish: number; neutral: number } {
  if (consensus.total <= 0) {
    return { bullish: 0, bearish: 0, neutral: 0 };
  }
  const pct = (n: number) => Math.round((100 * n) / consensus.total);
  return {
    bullish: pct(consensus.bullish),
    bearish: pct(consensus.bearish),
    neutral: pct(consensus.neutral),
  };
}

const TREND_PRIMARY_LABELS: Record<string, string> = {
  strong_bullish: "Fuertemente alcista",
  bullish: "Alcista",
  weak: "Neutra / rango",
  bearish: "Bajista",
  strong_bearish: "Fuertemente bajista",
};

const STRUCTURE_SMA_LABELS: Record<string, string> = {
  bullish_stack: "Alcista",
  bearish_stack: "Bajista",
  mixed: "Mixta",
};

export function mapJournalStudyTrends(
  facts: JournalStudyFactInput[] | null | undefined,
  fallbackOpinion?: JournalStudyOpinion | null,
): JournalStudyTrendV1[] {
  const list = facts ?? [];
  const primary = list.find((f) => f.key === "trend.primary");
  const structure = list.find((f) => f.key === "structure.sma");
  const trends: JournalStudyTrendV1[] = [];

  const shortDisplay = primary
    ? (TREND_PRIMARY_LABELS[primary.value] ?? primary.claim ?? primary.value)
    : fallbackOpinion
      ? JOURNAL_STUDY_OPINION_LABELS[fallbackOpinion]
      : null;
  if (shortDisplay) {
    trends.push({
      key: "short_term",
      label: "Corto plazo",
      value: primary?.value ?? fallbackOpinion ?? null,
      display: shortDisplay,
    });
  }

  if (structure) {
    trends.push({
      key: "background",
      label: "De fondo",
      value: structure.value,
      display:
        STRUCTURE_SMA_LABELS[structure.value] ??
        structure.claim ??
        structure.value,
    });
  }

  return trends;
}

export function mapJournalStudyIndicators(
  facts: JournalStudyFactInput[] | null | undefined,
): JournalStudyIndicatorsV1 {
  const refs = new Set<string>();
  for (const fact of facts ?? []) {
    for (const key of Object.keys(fact.refs ?? {})) {
      refs.add(key.toLowerCase());
    }
  }
  const primaryParts: string[] = [];
  if (refs.has("adx") || refs.has("plus_di") || refs.has("minus_di")) {
    primaryParts.push("ADX + DI");
  }
  if (refs.has("atr") || refs.has("atr_percentile")) {
    primaryParts.push("ATR");
  }
  const confirmParts: string[] = [];
  if (refs.has("rsi")) confirmParts.push("RSI");
  if (
    refs.has("sma_20") ||
    refs.has("sma_50") ||
    refs.has("sma20") ||
    refs.has("sma50")
  ) {
    confirmParts.push("SMA");
  }
  return {
    primary: primaryParts.length > 0 ? primaryParts.join(" + ") : null,
    confirmation: confirmParts.length > 0 ? confirmParts.join(" + ") : null,
  };
}

const INVALIDATOR_LABELS: Record<string, string> = {
  exhaustion: "Agotamiento del movimiento",
  distress: "Distress fundamental",
  crisis: "Régimen de crisis",
  luck: "Señal poco robusta (suerte)",
};

const THESIS_HEALTH_WHY_LABELS: Record<string, string> = {
  confidence_degraded: "Confianza degradada",
  stop_intact: "Stop estructural aún intacto",
  hard_exit: "Salida dura señalada",
  expired: "Plan caducado",
};

export function mapJournalStudyInvalidation(input: {
  direction?: TradePlanDirectionV1 | null;
  structuralStop?: number | null;
  hasOperationalPlan?: boolean;
  invalidators?: string[] | null;
  reevaluateWhen?: string[] | null;
  thesisHealthWhy?: string[] | null;
}): string[] {
  const items: string[] = [];
  const seen = new Set<string>();
  const push = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || seen.has(trimmed)) return;
    seen.add(trimmed);
    items.push(trimmed);
  };

  if (
    input.hasOperationalPlan &&
    typeof input.structuralStop === "number" &&
    Number.isFinite(input.structuralStop)
  ) {
    const price = input.structuralStop.toFixed(2);
    if (input.direction === "short") {
      push(`Cierre > ${price}`);
    } else if (input.direction === "long") {
      push(`Cierre < ${price}`);
    }
  }

  for (const raw of input.invalidators ?? []) {
    push(INVALIDATOR_LABELS[raw] ?? raw);
  }
  for (const raw of input.reevaluateWhen ?? []) {
    push(raw);
  }
  for (const raw of input.thesisHealthWhy ?? []) {
    push(THESIS_HEALTH_WHY_LABELS[raw] ?? raw);
  }
  return items;
}

function parseNow(now?: Date | string): Date {
  if (now instanceof Date) return now;
  if (typeof now === "string") {
    const d = new Date(now);
    if (!Number.isNaN(d.getTime())) return d;
  }
  return new Date();
}

export function buildJournalStudyView(
  input: BuildJournalStudyViewInput,
): DecisionJournalStudyViewV1 {
  const now = parseNow(input.now);
  const geometry = journalStudyGeometry(input.tradePlan ?? null);
  const opinion = mapJournalStudyOpinion({
    bias: input.bias,
    action: input.action,
  });
  const strength = mapJournalStudyStrength(input.overallConfidence);
  const notes = (input.notes ?? []).filter(
    (n) => typeof n === "string" && n.trim().length > 0,
  );
  const narrative = (input.narrativeFacts ?? []).filter(
    (n) => typeof n === "string" && n.trim().length > 0,
  );
  const analysisNotes = [...notes, ...narrative];
  const status = mapJournalStudyStatus({
    positionStatus: input.positionStatus,
    proposalStatus: input.proposalStatus,
    recommendationStatus: input.recommendationStatus,
    exitPrimaryReason: input.exitPrimaryReason,
    tradePlanStatus: input.tradePlan?.status,
    tradePlanWhyNot: input.tradePlan?.whyNot,
    action: input.action,
    bias: input.bias,
    hasOpenPosition: input.hasOpenPosition,
    hasLivePlan:
      input.tradePlan != null && input.tradePlan.status !== "EXPIRED",
    hasOperationalPlan: geometry.hasOperationalPlan,
  });

  return {
    artifactType: DECISION_JOURNAL_STUDY_ARTIFACT,
    schemaVersion: DECISION_JOURNAL_STUDY_SCHEMA,
    sessionId: input.sessionId,
    decisionId: input.decisionId ?? null,
    instrumentId: input.instrumentId,
    symbol: input.symbol ?? null,
    name: input.name ?? null,
    studiedAt: input.studiedAt,
    ageMs: mapJournalStudyAgeMs(input.studiedAt, now),
    period: mapJournalStudyPeriod(input.timeframe),
    timeframe: input.timeframe ?? null,
    opinion,
    status,
    strength,
    strengthBand: mapJournalStudyStrengthBand(strength),
    vigencia: mapJournalStudyVigencia({
      now,
      expiresAt: input.expiresAt ?? input.tradePlan?.expiresAt,
    }),
    entry: geometry.entry,
    stop: geometry.stop,
    target1: geometry.target1,
    target2: geometry.target2,
    expectedRR: geometry.expectedRR,
    riskAmount: geometry.riskAmount,
    quantity: geometry.quantity,
    initialRiskR: geometry.initialRiskR,
    positionValue: geometry.positionValue,
    direction: geometry.direction,
    hasOperationalPlan: geometry.hasOperationalPlan,
    userThesis: null,
    decisionSummary: analysisNotes[0] ?? null,
    analysisNotes,
    trends: mapJournalStudyTrends(input.facts, opinion),
    consensus: mapJournalStudyConsensus(input.assessments),
    indicators: mapJournalStudyIndicators(input.facts),
    invalidation: mapJournalStudyInvalidation({
      direction: input.tradePlan?.direction,
      structuralStop: geometry.stop,
      hasOperationalPlan: geometry.hasOperationalPlan,
      invalidators: input.invalidators,
      reevaluateWhen: input.reevaluateWhen,
      thesisHealthWhy: input.thesisHealthWhy,
    }),
    nextReviewAt: input.expiresAt ?? input.tradePlan?.expiresAt ?? null,
    tradePlanStatus: input.tradePlan?.status ?? null,
    action: input.action ?? null,
  };
}

export type DecisionJournalStudyListV1 = {
  accountId: string;
  studies: DecisionJournalStudyViewV1[];
  total: number;
  limit: number;
  offset: number;
};

export type DecisionJournalStudyListResponseV1 = {
  data: DecisionJournalStudyListV1;
};
