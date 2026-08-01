/** DTOs API — rastreadores persistidos (ADR-010 P3). */

import type {
  KernelEntityOrigin,
  KernelEvaluationMode,
  KernelTimeframe,
  TrackerDefinitionV1,
  TrackerScheduleV1,
  TrackerUniverseV1,
} from './platform-kernel.js';
import type { IndicatorSpec } from './research-platform.js';

export interface TrackerDefinitionSummaryDto {
  id: string;
  name: string;
  strategyDefinitionId: string;
  strategyVersion?: number | null;
  timeframe: KernelTimeframe;
  evaluationMode: KernelEvaluationMode;
  origin: KernelEntityOrigin;
  enabled: boolean;
  updatedAt: string;
  createdAt: string;
}

export interface TrackerDefinitionDetailDto extends TrackerDefinitionSummaryDto {
  definition: TrackerDefinitionV1;
}

export interface CreateTrackerDefinitionDto {
  name: string;
  strategyDefinitionId: string;
  universe: TrackerUniverseV1;
  strategyVersion?: number | null;
  timeframe?: KernelTimeframe;
  barLimit?: number;
  maxResults?: number;
  evaluationMode?: KernelEvaluationMode;
  rankBy?: {
    indicatorSpec: IndicatorSpec;
    direction: 'asc' | 'desc';
  };
  defaultExecutionPolicyId?: string | null;
  schedule?: TrackerScheduleV1 | null;
  origin?: KernelEntityOrigin;
  sourcePrompt?: string | null;
  enabled?: boolean;
}

export interface UpdateTrackerDefinitionDto {
  name?: string;
  strategyDefinitionId?: string;
  universe?: TrackerUniverseV1;
  strategyVersion?: number | null;
  timeframe?: KernelTimeframe;
  barLimit?: number;
  maxResults?: number;
  evaluationMode?: KernelEvaluationMode;
  rankBy?: {
    indicatorSpec: IndicatorSpec;
    direction: 'asc' | 'desc';
  } | null;
  defaultExecutionPolicyId?: string | null;
  schedule?: TrackerScheduleV1 | null;
  origin?: KernelEntityOrigin;
  sourcePrompt?: string | null;
  enabled?: boolean;
}

export interface TrackerDefinitionResponseDto {
  data: TrackerDefinitionDetailDto;
}

export interface TrackerDefinitionsListResponseDto {
  data: TrackerDefinitionSummaryDto[];
}

export type TrackerScheduleRunStatus =
  | 'enqueued'
  | 'skipped'
  | 'no_bars'
  | 'not_due'
  | 'error';

export interface TrackerScheduleRunResultDto {
  trackerId: string;
  trackerName: string;
  status: TrackerScheduleRunStatus;
  scanJobId?: string | null;
  latestBarTimestamp?: string | null;
  reason?: string | null;
}

export interface EvaluateTrackerSchedulesResponseDto {
  data: {
    checkedCount: number;
    enqueuedCount: number;
    runs: TrackerScheduleRunResultDto[];
  };
}
