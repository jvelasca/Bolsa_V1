/** DTOs API — políticas de ejecución (ADR-010 P5). */

import type {
  ExecutionMode,
  ExecutionPolicyV1,
  KernelEntityOrigin,
} from './platform-kernel.js';
import type { SignalKind } from './signal-events.js';
import type { AlertChannelType } from './signal-alerts-api.js';
import type { ScanHitDto } from './scan-api.js';

export interface ExecutionPolicySummaryDto {
  id: string;
  name: string;
  mode: ExecutionMode;
  accountId?: string | null;
  strategyDefinitionId?: string | null;
  signalKinds: SignalKind[];
  requireValidatedBacktest: boolean;
  enabled: boolean;
  updatedAt: string;
  createdAt: string;
}

export interface ExecutionPolicyDetailDto extends ExecutionPolicySummaryDto {
  definition: ExecutionPolicyV1;
}

export interface CreateExecutionPolicyDto {
  name: string;
  mode: ExecutionMode;
  accountId?: string | null;
  strategyDefinitionId?: string | null;
  signalKinds?: SignalKind[];
  channels?: AlertChannelType[];
  webhookUrl?: string | null;
  emailTo?: string | null;
  requireValidatedBacktest?: boolean;
  origin?: KernelEntityOrigin;
  enabled?: boolean;
}

export interface UpdateExecutionPolicyDto {
  name?: string;
  mode?: ExecutionMode;
  accountId?: string | null;
  strategyDefinitionId?: string | null;
  signalKinds?: SignalKind[];
  channels?: AlertChannelType[];
  webhookUrl?: string | null;
  emailTo?: string | null;
  requireValidatedBacktest?: boolean;
  enabled?: boolean;
}

export interface ExecutionPolicyResponseDto {
  data: ExecutionPolicyDetailDto;
}

export interface ExecutionPoliciesListResponseDto {
  data: ExecutionPolicySummaryDto[];
}

export type ExecutionActionStatus =
  | 'inform_only'
  | 'alert_dispatched'
  | 'trade_executed'
  | 'skipped'
  | 'live_dry_run_pass'
  | 'live_dry_run_veto';

export interface ExecutionActionResultDto {
  instrumentId: string;
  signalKind: SignalKind;
  status: ExecutionActionStatus;
  reason?: string | null;
  transactionId?: string | null;
  dispatches?: { channel: string; ok: boolean; error?: string | null }[];
}

export interface RouteSignalsRequestDto {
  hits: ScanHitDto[];
}

export interface RouteSignalsResponseDto {
  data: {
    policyId: string;
    mode: ExecutionMode;
    actions: ExecutionActionResultDto[];
  };
}

export interface ExecuteScanJobRequestDto {
  policyId: string;
}
