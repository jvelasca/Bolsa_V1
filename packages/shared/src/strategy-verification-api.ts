/**
 * DTOs de la **verificación periódica de estrategia** (ADR-050).
 *
 * El veredicto es **advisory**: `activationAllowed` es siempre `false`. Puede pedir re-LAB o
 * proponer una mutación, nunca escribir la estrategia activa ni el mandato.
 *
 * Dos relojes que no se mezclan:
 * - **Épocas** no solapadas (`kind="epoch"`): son las que deciden.
 * - **Ventana móvil** (`kind="rolling"`, `overlapping=true`): historial visual, nunca certifica.
 *
 * El ledger separa `outcome` (qué pasó) de `decisionQuality` (si la acción fue coherente).
 */

import type {
  DiaDAsRunCandidateForwardV1,
  DiaDAsRunOperationRowV1,
} from "./dia-d-as-run.js";

export type StrategyVerificationCadenceDto = {
  mode: "epochs";
  everyDays: number;
  anchorDay: string | null;
  rollingEnabled: boolean;
  rollingLookbackDays: number;
};

export type StrategyVerificationSamplesDto = {
  minCohortSamples: number;
  minClosedCycles: number;
  minPerInstrumentCycles: number;
  epochsInVerdict: number;
};

export type StrategyVerificationCandidatePolicyDto = {
  requirePointInTime: true;
  measureForward: boolean;
  maxCandidates: number;
};

export type StrategyVerificationThresholdsDto = {
  minExcessMeanR: number;
  minShareEpochsNotWorse: number;
  maxDrawdownPct: number;
  minHitRate: number | null;
  maxEvidenceAgeDays: number | null;
};

export type StrategyVerificationDecisionPolicyDto = {
  version: string;
  watchOnInconclusive: boolean;
  relabOnArmDominance: boolean;
  allowAutoActivation: false;
};

/** Perfil pre-registrado: se hashea ANTES de medir y no autoriza operar. */
export type StrategyVerificationProfileDto = {
  version: string;
  profileId: string;
  accountScope: string;
  universeInstruments: string[];
  cadence: StrategyVerificationCadenceDto;
  samples: StrategyVerificationSamplesDto;
  arms: string[];
  candidate: StrategyVerificationCandidatePolicyDto;
  thresholds: StrategyVerificationThresholdsDto;
  decision: StrategyVerificationDecisionPolicyDto;
  execution: Record<string, unknown>;
};

export type StrategyVerificationProfileResponseDto = {
  available: boolean;
  activationAllowed: false;
  profile?: StrategyVerificationProfileDto;
  profileHash?: string;
  notes: string[];
};

export type StrategyVerificationGateStatus = "pass" | "fail" | "not_evaluated";

/** Un gate del veredicto. `not_evaluated` NUNCA equivale a `pass`. */
export type StrategyVerificationGateDto = {
  gate: string;
  status: StrategyVerificationGateStatus;
  reason: string | null;
  [detail: string]: unknown;
};

export type StrategyVerificationEpochDto = {
  epochId: string;
  day: string;
  toDay: string;
  artifactHash: string;
  measured: boolean;
  certified: boolean;
  armsR: Record<string, number | null>;
  armsReturnPct: Record<string, number | null>;
  closedCycles: number;
  operations: number;
  consistentDecisions: number;
  inconsistentDecisions: number;
  unrealizedR: number | null;
  strategyVersion: string | null;
  mandateVersion: string | null;
  candidateMeasured: boolean;
  candidateReturnPct: number | null;
  candidateGap: string | null;
  certificationChecks: Record<string, string>;
};

export type StrategyVerificationVerdictKind =
  | "continue"
  | "watch"
  | "relab"
  | "promote_requires_human"
  | "insufficient_sample"
  | "inconclusive_version_change";

/** Veredicto completo con sus gates y sus números. */
export type StrategyVerificationVerdictDto = {
  verdict: StrategyVerificationVerdictKind;
  activationAllowed: false;
  profileId: string;
  profileHash: string;
  gates: StrategyVerificationGateDto[];
  samples: number;
  requiredSamples: number;
  asRunMeanR: number | null;
  bestArm: string | null;
  bestArmMeanR: number | null;
  meanExcessR: number | null;
  shareEpochsNotWorse: number | null;
  bootstrapLow: number | null;
  candidateMeanReturnPct: number | null;
  asRunMeanReturnPct: number | null;
  epochs: StrategyVerificationEpochDto[];
  reasons: string[];
  limits: string[];
  /** Solo presente en la respuesta del POST (no es parte del veredicto puro). */
  measurementHash?: string;
  profile?: StrategyVerificationProfileDto;
};

export type StrategyVerificationKind = "epoch" | "rolling";

/** Run sellado en el índice durable. La misma clave con otra medición es un conflicto. */
export type StrategyVerificationRunDto = {
  id: string;
  accountId: string;
  profileId: string;
  profileHash: string;
  kind: StrategyVerificationKind;
  day: string;
  toDay: string;
  measurementHash: string;
  verdict: StrategyVerificationVerdictKind;
  strategyVersion: string | null;
  payload: Record<string, unknown>;
  createdAt: string;
};

export type StrategyVerificationOverviewDto = {
  available: boolean;
  activationAllowed: false;
  latest: StrategyVerificationRunDto | null;
  runs: StrategyVerificationRunDto[];
  notes: string[];
};

export type StrategyVerificationHistoryDto = {
  available: boolean;
  activationAllowed: false;
  kind: StrategyVerificationKind;
  runs: StrategyVerificationRunDto[];
  notes: string[];
};

export type StrategyVerificationRecomputeRequestDto = {
  everyDays?: number;
  anchorDay?: string;
  healthState?: string;
  limitDays?: number;
};

export type StrategyVerificationRecomputeResponseDto = {
  available: boolean;
  activationAllowed: false;
  run: StrategyVerificationRunDto;
  verdict: StrategyVerificationVerdictDto;
};

/** Ledger por operación de un día as-run, filtrable por brazo/instrumento/desenlace/calidad. */
export type StrategyVerificationLedgerRowDto = DiaDAsRunOperationRowV1 & {
  day: string;
};

export type StrategyVerificationLedgerDto = {
  available: boolean;
  activationAllowed: false;
  day: string;
  rows: StrategyVerificationLedgerRowDto[];
  notes: string[];
};

export type StrategyVerificationMeasurementHashDto = {
  available: boolean;
  day?: string;
  measurementHash?: string;
  artifactHash?: string | null;
  notes?: string[];
};

export type StrategyVerificationCandidateForwardDto =
  DiaDAsRunCandidateForwardV1;
