import type { TechnicalRatingBreakdownV1, DataQualityBreakdownV1 } from './hybrid-strategy.js';
import type { ChartTimeframe } from './chart-timeframes.js';
import type { IndicatorSpec, StrategyDefinitionV1 } from './research-platform.js';
import type { SignalEventV1 } from './signal-events.js';
import type { BacktestStrategyType } from './types.js';

/** Spec de job de scan — alineado SCREENERS_SIGNALS_ALIGNMENT.md */
export interface ScanJobSpecV1 {
  id: string;
  strategyDefinitionId: string;
  universe: { listId?: string; instrumentIds?: string[] };
  timeframe: ChartTimeframe;
  mode: 'bar_close' | 'realtime';
  rankBy?: { indicatorSpec: IndicatorSpec; direction: 'asc' | 'desc' };
  maxResults?: number;
}

export interface ScanUniverseDto {
  listId?: string;
  instrumentIds?: string[];
}

export interface ScanRunRequestDto {
  strategyDefinitionId?: string;
  trackerDefinitionId?: string;
  definition?: StrategyDefinitionV1 | Record<string, unknown>;
  presetKey?: BacktestStrategyType;
  universe: ScanUniverseDto;
  timeframe?: ChartTimeframe;
  barLimit?: number;
  maxResults?: number;
}

export interface ScanSkippedInstrumentDto {
  instrumentId: string;
  reason: string;
}

export interface ScanHitDto {
  instrumentId: string;
  symbol: string;
  name: string;
  signal: SignalEventV1;
  aiScore?: number;
  ratingBreakdown?: TechnicalRatingBreakdownV1;
  dataQualityScore?: number;
  dataQualityBreakdown?: DataQualityBreakdownV1;
  globalScore?: number;
}

export interface ScanRunResultDto {
  scanId: string;
  scannedCount: number;
  hitCount: number;
  hits: ScanHitDto[];
  skipped: ScanSkippedInstrumentDto[];
  strategyDefinitionId?: string;
  listId?: string;
  timeframe: ChartTimeframe;
  scanMode?: 'classic' | 'hybrid';
  scorerVersion?: string;
  /** Instrumentos con fundamentales refrescados desde Yahoo pre-scan (P14). */
  fundamentalsRefreshedCount?: number;
  /** Auto-ruta B1 (inform_only / alert) tras scan de rastreador. */
  alarmRoute?: {
    policyId: string;
    mode: string;
    actions: Array<{
      instrumentId: string;
      signalKind: string;
      status: string;
      reason?: string | null;
      transactionId?: string | null;
    }>;
  } | null;
}

export interface ScanRunResponseDto {
  data: ScanRunResultDto;
}

export type ScanJobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface ScanJobDto {
  id: string;
  status: ScanJobStatus;
  payload: ScanRunRequestDto;
  result?: ScanRunResultDto | null;
  error?: string | null;
  cacheHits?: number | null;
  cacheMisses?: number | null;
  trackerDefinitionId?: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt?: string | null;
}

export interface ScanJobResponseDto {
  data: ScanJobDto;
}

export interface ScanJobsListResponseDto {
  data: ScanJobDto[];
}

export const SIGNAL_KIND_LABELS: Record<SignalEventV1['kind'], string> = {
  entry_long: 'Entrada long',
  entry_short: 'Entrada short',
  exit: 'Salida',
  watch: 'Vigilar',
};
