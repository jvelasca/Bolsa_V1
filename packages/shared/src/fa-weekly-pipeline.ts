/**
 * FIE — Pipeline semanal: Screener FA → whitelist → Paper D propose/execute.
 *
 * Orquesta F4 + Paper D. Execute sigue gated por PAPER_D_EXECUTE.
 * Cron worker: FA_WEEKLY_CRON_ENABLED (off-by-default).
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

import type { FundamentalGateV1 } from './fundamentals-gate.js';
import type { FundamentalScreenerRunResultV1 } from './fundamental-screener.js';
import type { PaperDProposeResultV1, PaperDProposeUniverseV1 } from './paper-d.js';

export const FA_WEEKLY_PIPELINE_VERSION = 'fa_weekly_pipeline_v1' as const;

export interface FaWeeklyPipelinePersistV1 {
  listId?: string;
  name?: string;
}

export interface FaWeeklyPipelineRequestV1 {
  universe: PaperDProposeUniverseV1;
  fundamentalGate: FundamentalGateV1;
  refreshStale?: boolean;
  maxResults?: number;
  /** Default: crear/actualizar whitelist snapshot. */
  persist?: FaWeeklyPipelinePersistV1 | null;
  horizon?: 'intraday' | 'swing' | 'position' | 'long_term';
  regime?: 'risk_on' | 'neutral' | 'risk_off' | 'crisis' | 'uncertain';
  minScoreDisplay100?: number;
  respectVetoNewLong?: boolean;
  maxCandidates?: number;
  execute?: boolean;
  executionPolicyId?: string | null;
}

export type FaWeeklyPipelineStatusV1 =
  | 'completed'
  | 'completed_no_hits'
  | 'propose_skipped_no_whitelist';

export interface FaWeeklyPipelineResultV1 {
  pipelineVersion: typeof FA_WEEKLY_PIPELINE_VERSION | string;
  weekKey: string;
  status: FaWeeklyPipelineStatusV1;
  whitelistListId: string | null;
  screener: FundamentalScreenerRunResultV1;
  propose: PaperDProposeResultV1 | null;
  notes: string[];
  generatedAt?: string;
}

export interface FaWeeklyPipelineResponseV1 {
  data: FaWeeklyPipelineResultV1;
}
