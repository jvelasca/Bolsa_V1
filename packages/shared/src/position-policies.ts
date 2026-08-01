/** DTOs API — políticas por posición (ADR-010 P6). */

import type { PositionExecutionMode, PositionPolicyV1 } from './platform-kernel.js';

export interface PositionPolicySummaryDto {
  id: string;
  accountId: string;
  instrumentId: string;
  mode: PositionExecutionMode;
  exitStrategyDefinitionId?: string | null;
  executionPolicyId?: string | null;
  updatedAt: string;
  createdAt: string;
}

export interface PositionPolicyDetailDto extends PositionPolicySummaryDto {
  definition: PositionPolicyV1;
}

export interface CreatePositionPolicyDto {
  accountId: string;
  instrumentId: string;
  mode?: PositionExecutionMode;
  exitStrategyDefinitionId?: string | null;
  executionPolicyId?: string | null;
}

export interface UpdatePositionPolicyDto {
  mode?: PositionExecutionMode;
  exitStrategyDefinitionId?: string | null;
  executionPolicyId?: string | null;
}

export interface PositionPolicyResponseDto {
  data: PositionPolicyDetailDto;
}

export interface PositionPoliciesListResponseDto {
  data: PositionPolicySummaryDto[];
}

export type PositionExitEvalStatus =
  | 'no_policy'
  | 'manual'
  | 'no_exit_strategy'
  | 'no_bars'
  | 'no_signal'
  | 'exit_signal'
  | 'executed'
  | 'skipped'
  | 'error';

export interface PositionExitEvalResultDto {
  accountId: string;
  instrumentId: string;
  symbol: string;
  quantity: number;
  policyId?: string | null;
  mode?: string | null;
  status: PositionExitEvalStatus;
  signal?: Record<string, unknown> | null;
  action?: Record<string, unknown> | null;
  reason?: string | null;
}

export interface EvaluatePositionExitsResponseDto {
  data: {
    accountId: string;
    evaluatedCount: number;
    results: PositionExitEvalResultDto[];
  };
}
