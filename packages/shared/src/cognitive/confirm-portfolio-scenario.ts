/**
 * V1.25 — what-if Confirm reutiliza buildPortfolioScenario (misma fn que Mesa).
 */

import {
  DECISION_JOURNAL_STUDY_ARTIFACT,
  DECISION_JOURNAL_STUDY_SCHEMA,
  type DecisionJournalStudyViewV1,
} from "./decision-journal-study.js";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import {
  buildPortfolioScenario,
  type BuildPortfolioScenarioInput,
  type PortfolioScenarioV1,
} from "./portfolio-scenario.js";
import type { TradePlanV1 } from "./trade-plan.js";

export type BuildConfirmPortfolioScenarioInput = {
  symbol: string;
  instrumentId: string;
  signedQty: number;
  signedPrice: number;
  signedStop: number | null;
  tradePlan?: TradePlanV1 | null;
  positions: BuildPortfolioScenarioInput["positions"];
  equity?: number | null;
  cash?: number | null;
  candidateSector?: string | null;
  riskTolerance?: string | null;
  maxAcceptableLossPct?: number | null;
  maxSectorExposurePct?: number;
  portfolioRiskLimitR?: number | null;
};

/** Candidato mínimo para scenario desde inputs firmados del ticket. */
export function buildConfirmScenarioCandidate(input: {
  symbol: string;
  instrumentId: string;
  signedQty: number;
  signedPrice: number;
  signedStop: number | null;
  tradePlan?: TradePlanV1 | null;
}): MesaCandidateRowV1 {
  const plan = input.tradePlan;
  const entry = input.signedPrice;
  const stop = input.signedStop ?? plan?.structuralStop ?? null;
  const quantity = input.signedQty;
  const riskAmount = plan?.riskAmount ?? null;
  const initialRiskR = plan?.initialRiskR ?? null;
  const positionValue =
    Number.isFinite(entry) && Number.isFinite(quantity) && quantity > 0
      ? entry * quantity
      : (plan?.positionValue ?? null);

  const study: DecisionJournalStudyViewV1 = {
    artifactType: DECISION_JOURNAL_STUDY_ARTIFACT,
    schemaVersion: DECISION_JOURNAL_STUDY_SCHEMA,
    sessionId: plan?.decisionId ?? "confirm-scenario",
    decisionId: plan?.decisionId ?? null,
    instrumentId: input.instrumentId,
    symbol: input.symbol,
    name: null,
    studiedAt: new Date(0).toISOString(),
    ageMs: null,
    period: null,
    timeframe: null,
    opinion: null,
    status: "in_progress",
    strength: null,
    strengthBand: null,
    vigencia: null,
    entry,
    stop,
    target1: plan?.target1 ?? null,
    target2: plan?.target2 ?? null,
    expectedRR: plan?.expectedRR ?? null,
    riskAmount,
    quantity,
    initialRiskR,
    positionValue,
    direction: plan?.direction ?? "long",
    hasOperationalPlan: plan?.status === "TRIGGERED",
    userThesis: null,
    decisionSummary: null,
    analysisNotes: [],
    trends: [],
    consensus: { bullish: 0, bearish: 0, neutral: 0, total: 0 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: plan?.status ?? null,
    action: null,
  };

  return {
    symbol: input.symbol,
    status: plan?.status ?? "WATCH",
    statusLabel: plan?.status ?? "WATCH",
    gate: "PASS",
    instrumentId: input.instrumentId,
    study,
  };
}

export function buildConfirmPortfolioScenario(
  input: BuildConfirmPortfolioScenarioInput,
): PortfolioScenarioV1 {
  const candidate = buildConfirmScenarioCandidate({
    symbol: input.symbol,
    instrumentId: input.instrumentId,
    signedQty: input.signedQty,
    signedPrice: input.signedPrice,
    signedStop: input.signedStop,
    tradePlan: input.tradePlan,
  });

  return buildPortfolioScenario({
    candidate,
    positions: input.positions,
    equity: input.equity,
    cash: input.cash,
    candidateSector: input.candidateSector,
    riskTolerance: input.riskTolerance,
    maxAcceptableLossPct: input.maxAcceptableLossPct,
    maxSectorExposurePct: input.maxSectorExposurePct,
    portfolioRiskLimitR: input.portfolioRiskLimitR,
  });
}
