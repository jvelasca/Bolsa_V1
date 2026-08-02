/**
 * DTOs mandato operativo (ADR-020 M1b) — espejo API camelCase.
 */

export type MandateActorDto = 'user' | 'coach' | 'core_r' | 'system';
export type MandateReasonDto =
  | 'adopt'
  | 'switch'
  | 'propose_accepted'
  | 'obsolete'
  | 'manual';

export type MandateTenureDto = {
  id: string;
  accountId: string;
  instrumentId: string;
  timeframe?: string | null;
  strategyDefinitionId?: string | null;
  strategyLabelSnapshot?: string | null;
  effectiveFrom: string;
  effectiveTo?: string | null;
  actor: MandateActorDto | string;
  reason: MandateReasonDto | string;
  sourceTopId?: string | null;
  sourceTopVersion?: number | null;
  evidenceLevel?: 'in_sample_only' | 'lab_validated' | string | null;
};

export type MandateTradeLinkDto = {
  transactionId: string;
  mandateTenureId: string;
  instrumentId: string;
  accountId: string;
  linkedAt: string;
  engine?: string;
};

export type MandateBundleDto = {
  tenures: MandateTenureDto[];
  links: MandateTradeLinkDto[];
};
