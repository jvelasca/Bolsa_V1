/** Research Observatory DTOs — Fase 1.5 (read-only ledger K). */

export interface ResearchTrialDto {
  id: string;
  instrumentId: string;
  params: Record<string, unknown>;
  isMetrics: Record<string, number | string | null>;
  proposedBy: string;
  kContribution: number;
  createdAt: string;
  hypothesisId?: string | null;
  researchQuestionId?: string | null;
  backtestRunId?: string | null;
  optimizationRunId?: string | null;
  strategyDefinitionId?: string | null;
  presetKey?: string | null;
  strategyName?: string | null;
  blocks?: Record<string, unknown> | null;
  isScore?: number | null;
  parentTrialId?: string | null;
  failCode?: string | null;
  manifestRef?: Record<string, unknown> | null;
}

export interface ResearchTrialsListResponseDto {
  data: ResearchTrialDto[];
  total: number;
  limit: number;
  offset: number;
}

export interface ResearchTrialDetailResponseDto {
  data: ResearchTrialDto;
}

export interface InstrumentResearchSummaryDto {
  instrumentId: string;
  symbol: string;
  name: string;
  trials: number;
  kConsumed: number;
  avgSharpe?: number | null;
  avgSortino?: number | null;
  avgMaxDD?: number | null;
  bestSharpe?: number | null;
  lastTrialAt?: string | null;
  proposedBy: Record<string, number>;
}

export interface LaboratoryResearchSummaryDto {
  totalTrials: number;
  totalK: number;
  activeInstruments: number;
  avgSharpe?: number | null;
  avgProfitFactor?: number | null;
  avgMaxDD?: number | null;
  lastTrialAt?: string | null;
  byInstrument: Array<{
    instrumentId: string;
    symbol: string;
    trials: number;
    kConsumed: number;
    avgSharpe?: number | null;
  }>;
  byPreset: Array<{
    presetKey: string;
    trials: number;
    kConsumed: number;
  }>;
  byOrigin: Array<{
    proposedBy: string;
    trials: number;
    kConsumed: number;
  }>;
}

export type ResearchTrialSort =
  | 'created_at'
  | 'sharpe'
  | 'pnl'
  | 'commission'
  | 'k_contribution';

export interface ResearchTrialsQuery {
  instrumentId?: string;
  proposedBy?: string;
  presetKey?: string;
  strategy?: string;
  strategyDefinitionId?: string;
  optimizationRunId?: string;
  backtestRunId?: string;
  failCode?: string;
  dateFrom?: string;
  dateTo?: string;
  sort?: ResearchTrialSort;
  sortDir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}
