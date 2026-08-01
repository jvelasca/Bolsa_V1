/**
 * Evidence Engine types + ART-EDGE-REPORT (RFC-008 D3 skeleton).
 * Responde: ¿cuánto puedo creerme esta señal? (Credibility), no solo “¿funciona?”.
 */

export type EvidenceDirection = 'supports' | 'contradicts' | 'neutral';

export type EvidenceKind =
  | 'data_quality'
  | 'market_regime'
  | 'technical'
  | 'fundamental'
  | 'opportunity'
  | 'news_event'
  | 'macro'
  | 'risk'
  | 'policy'
  | 'statistical';

export interface EvidenceV1 {
  evidenceId: string;
  evidenceKind: EvidenceKind;
  claim: string;
  direction: EvidenceDirection;
  weight: number;
  confidence: number;
  validFrom?: string;
  validTo?: string;
  /** Half-life in hours */
  decayHalfLifeHours?: number;
  refs?: Record<string, string>;
}

export interface EvidenceBundleV1 {
  artifactType: 'ART-EVIDENCE-BUNDLE';
  schemaVersion: '1.0.0';
  bundleId: string;
  instrumentId: string;
  timestamp: string;
  evidences: EvidenceV1[];
}

export type EdgeBand = 'skill' | 'uncertain' | 'luck';

export type WfeSource = 'lab_score' | 'sharpe';

export interface StatisticalSuiteResult {
  /** Walk-Forward Efficiency — Sharpe ratio or lab score ratio (see wfeSource). */
  walkForwardEfficiency?: number | null;
  /** Provenance of walkForwardEfficiency. */
  wfeSource?: WfeSource | null;
  monteCarloPValue?: number | null;
  /** Probabilistic Sharpe Ratio */
  psr?: number | null;
  /** Deflated Sharpe Ratio — inválido sin trialsN */
  dsr?: number | null;
  bootstrapAlphaCiLower?: number | null;
  bootstrapAlphaCiUpper?: number | null;
  stressSurvivalRate?: number | null;
  historicalWinRate?: number | null;
  sampleTradesCount?: number | null;
  /** Nº de trials / hipótesis exploradas (obligatorio para DSR) */
  trialsN: number;
}

export interface EdgeReportV1 {
  artifactType: 'ART-EDGE-REPORT';
  schemaVersion: '1.0.0';
  edgeReportId: string;
  version: string;
  strategyOrSignalRef: string;
  instrumentUniverseRef?: string;
  createdAt: string;
  suite: StatisticalSuiteResult;
  /** Credibility agregada 0–100 */
  credibility: number;
  edgeScore: number;
  band: EdgeBand;
  notes?: string[];
}

export interface CredibilityWeights {
  wMonteCarlo: number;
  wWfe: number;
  wDsr: number;
  wBootstrap: number;
  wStress: number;
}

export const DEFAULT_CREDIBILITY_WEIGHTS: CredibilityWeights = {
  wMonteCarlo: 0.25,
  wWfe: 0.25,
  wDsr: 0.2,
  wBootstrap: 0.15,
  wStress: 0.15,
};

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

/**
 * Credibility 0–100 a partir de la suite.
 * DSR se ignora (contribuye 0) si trialsN < 1 — el caller debe registrar trials.
 */
export function computeCredibility(
  suite: StatisticalSuiteResult,
  weights: CredibilityWeights = DEFAULT_CREDIBILITY_WEIGHTS,
): { credibility: number; edgeScore: number; band: EdgeBand } {
  const mc =
    suite.monteCarloPValue == null
      ? 0
      : clamp01(1 - suite.monteCarloPValue / 0.05) * (suite.monteCarloPValue <= 0.05 ? 1 : 0.3);

  const wfe =
    suite.walkForwardEfficiency == null
      ? 0
      : clamp01(suite.walkForwardEfficiency);

  const dsr =
    suite.trialsN < 1 || suite.dsr == null ? 0 : clamp01(suite.dsr);

  let bootstrap = 0;
  if (
    suite.bootstrapAlphaCiLower != null &&
    suite.bootstrapAlphaCiUpper != null
  ) {
    bootstrap = suite.bootstrapAlphaCiLower > 0 ? 1 : 0.35;
  }

  const stress =
    suite.stressSurvivalRate == null ? 0 : clamp01(suite.stressSurvivalRate);

  const sumW =
    weights.wMonteCarlo +
    weights.wWfe +
    weights.wDsr +
    weights.wBootstrap +
    weights.wStress;

  const score01 =
    (weights.wMonteCarlo * mc +
      weights.wWfe * wfe +
      weights.wDsr * dsr +
      weights.wBootstrap * bootstrap +
      weights.wStress * stress) /
    sumW;

  const credibility = Math.round(score01 * 1000) / 10;
  const edgeScore = credibility;
  const band: EdgeBand =
    credibility >= 85 ? 'skill' : credibility >= 65 ? 'uncertain' : 'luck';

  return { credibility, edgeScore, band };
}

export interface TrialRecordV1 {
  trialId: string;
  hypothesisRef: string;
  paramsHash: string;
  sharpeIs?: number | null;
  createdAt: string;
  notes?: string | null;
}

/** Log de hipótesis — N = trials.length; obligatorio para DSR. */
export interface TrialsLogV1 {
  logId: string;
  strategyFamilyRef: string;
  trialsN: number;
  trials: TrialRecordV1[];
}

export interface AutoLiveCheckV1 {
  allowed: boolean;
  reasons: string[];
  policyId: string;
  edgeReportId?: string | null;
  credibility?: number | null;
}

/** Suite D3 — implementación numérica en Python (`bolsa_analytics.cognitive`). */
export interface EvidenceEngineSuiteApi {
  monteCarloPermutationPValue(tradeReturns: number[], permutations?: number): number;
  walkForwardEfficiency(inSampleSharpe: number, outOfSampleSharpe: number): number;
  /** Requiere trialsN > 0 para DSR válido */
  buildEdgeReport(input: {
    strategyOrSignalRef: string;
    suite: StatisticalSuiteResult;
  }): EdgeReportV1;
}
