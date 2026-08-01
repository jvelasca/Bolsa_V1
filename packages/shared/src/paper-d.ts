/**
 * Paper D — auto-paper completo (FIE post-F3/F4).
 *
 * Propose: Composite × universo (dry-run).
 * Execute: `PAPER_D_EXECUTE=1` + execute=true + policy paper_auto → ExecutionRouter.
 * Distinto de: A lab checklist · B radar paper_auto · C Supervisado Proponer.
 *
 * @see docs/engineering/research-lifecycle.md
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 * @see docs/engineering/fa-status-and-test-plan-2026-07-31.md
 */

export const PAPER_D_PROPOSE_VERSION = 'paper_d_propose_v2' as const;

export type PaperDCandidateStatusV1 =
  | 'eligible'
  | 'below_threshold'
  | 'vetoed_regime'
  | 'missing_composite'
  | 'skipped';

export interface PaperDProposeUniverseV1 {
  listId?: string;
  instrumentIds?: string[];
}

export interface PaperDProposeRequestV1 {
  universe: PaperDProposeUniverseV1;
  horizon?: 'intraday' | 'swing' | 'position' | 'long_term';
  regime?: 'risk_on' | 'neutral' | 'risk_off' | 'crisis' | 'uncertain';
  /** Mínimo scoreDisplay100 del Composite (default 55). */
  minScoreDisplay100?: number;
  /** Respetar WeightRules.vetoNewLong (default true). */
  respectVetoNewLong?: boolean;
  maxCandidates?: number;
  /**
   * Ejecutar paper trades vía ExecutionRouter.
   * Requiere env PAPER_D_EXECUTE=1 + executionPolicyId (mode=paper_auto).
   */
  execute?: boolean;
  executionPolicyId?: string | null;
}

export interface PaperDCandidateV1 {
  instrumentId: string;
  ticker: string;
  status: PaperDCandidateStatusV1;
  combinedScore: number | null;
  scoreDisplay100: number | null;
  confidence: string | null;
  regime: string | null;
  vetoNewLong: boolean;
  reason?: string | null;
}

export interface PaperDExecutionActionV1 {
  instrumentId: string;
  signalKind: string;
  status: string;
  reason?: string | null;
  transactionId?: string | null;
}

export interface PaperDExecutionResultV1 {
  policyId?: string | null;
  mode?: string | null;
  hitCount?: number;
  actions: PaperDExecutionActionV1[];
  priceSkips?: Array<{ instrumentId: string; ticker?: string | null; reason: string }>;
}

export interface PaperDProposeResultV1 {
  proposeVersion: typeof PAPER_D_PROPOSE_VERSION | string;
  planId: string;
  weekKey: string;
  scannedCount: number;
  eligibleCount: number;
  candidates: PaperDCandidateV1[];
  rankingReady: boolean;
  executeAllowedByEnv: boolean;
  executeRequested: boolean;
  executeStatus: 'dry_run' | 'blocked_env' | 'executed';
  execution?: PaperDExecutionResultV1 | null;
  notes: string[];
  generatedAt?: string;
}

export interface PaperDProposeResponseV1 {
  data: PaperDProposeResultV1;
}
