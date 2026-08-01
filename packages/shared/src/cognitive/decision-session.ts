/**
 * ART-DECISION-SESSION + WeightContext (auditabilidad RFC-008).
 * Session ≠ Memory: Session = fotografía del razonamiento; Memory = outcome del Gate.
 */

export interface WeightContextV1 {
  horizon: string;
  regime: string;
  volatilityRegime?: string | null;
  policyId?: string | null;
  ruleVersion: string;
  weights: {
    ta: number;
    fund: number;
    macro: number;
    news: number;
  };
  rationale: string;
  sizeHint?: number;
  vetoNewLong?: boolean;
  missingAssessments?: string[];
}

export type DecisionSessionKind = 'propose' | 'confirm' | 'paper_auto' | 'live_dry_run';
export type DecisionSessionStatus = 'open' | 'closed';

export interface DecisionSessionV1 {
  artifactType?: 'ART-DECISION-SESSION';
  schemaVersion: string;
  sessionId: string;
  kind: DecisionSessionKind;
  status: DecisionSessionStatus;
  instrumentId: string;
  symbol?: string | null;
  accountId?: string | null;
  createdAt: string;
  timeframe?: string | null;
  horizon?: string | null;
  marketRegime?: string | null;
  profileSnapshotRef?: string | null;
  policySnapshot?: Record<string, unknown> | null;
  weightContext?: WeightContextV1 | null;
  assessments?: Record<string, unknown>[];
  predictions?: Record<string, unknown>[];
  evidence?: Record<string, unknown> | null;
  runtime?: Record<string, unknown> | null;
  recommendation?: Record<string, unknown> | null;
  policyGate?: Record<string, unknown> | null;
  execution?: Record<string, unknown> | null;
  outcome?: SessionOutcomeV1 | Record<string, unknown> | null;
  lineage?: Record<string, unknown>;
  decisionId?: string | null;
  recommendationId?: string | null;
}

export interface DecisionSessionSummaryV1 {
  sessionId: string;
  kind: string;
  status: string;
  instrumentId: string;
  symbol?: string | null;
  accountId?: string | null;
  recommendationId?: string | null;
  decisionId?: string | null;
  createdAt: string;
}

export interface DecisionReplayStepV1 {
  stepId: string;
  title: string;
  detail: string;
  payload?: Record<string, unknown> | null;
}

export interface DecisionReplayV1 {
  sessionId: string;
  instrumentId: string;
  symbol?: string | null;
  createdAt?: string | null;
  kind?: string | null;
  steps: DecisionReplayStepV1[];
}

/** Outcome Session (Learning) — distinto de Memory Gate outcome. */
export type SessionOutcomeVerdict = 'hit' | 'miss' | 'neutral' | 'invalid' | 'skipped';
export type SessionOutcomeSource = 'auto_mark' | 'manual';

export interface SessionOutcomeV1 {
  criteriaVersion: string;
  source: SessionOutcomeSource;
  evaluatedAt: string;
  horizon: string;
  evalBars: number;
  recommendedAction: string;
  priceAtDecision?: number | null;
  priceAtEval?: number | null;
  returnPct?: number | null;
  directionHit?: boolean | null;
  verdict: SessionOutcomeVerdict;
  notes?: string | null;
  mature?: boolean;
  barsElapsed?: number | null;
}

export interface SessionLearningSummaryV1 {
  criteriaVersion: string;
  sampleClosed: number;
  scored: number;
  hits: number;
  misses: number;
  neutrals: number;
  skipped: number;
  invalid: number;
  hitRate?: number | null;
  matureScored?: number;
  matureHits?: number;
  matureMisses?: number;
  matureHitRate?: number | null;
  prematureScored?: number;
  byHorizon: Record<string, Record<string, number>>;
  note?: string;
}
