/**
 * ART: DiaDExperimentTop — TOP experimento as-of D (F-D) del LAB.
 *
 * Es el TOP que se guarda al verificar una fecha pasada `D`: **no** sustituye al
 * TOP operativo (F-hoy). Durable en servidor como Evidence append-only
 * (`source='dia_d_experiment_top'`), con la procedencia derivada de los runs.
 */

import type { InstrumentStrategyTopSlotV1 } from "./instrument-strategy-top.js";

export type DiaDExperimentTop1RefV1 = {
  strategyDefinitionId?: string | null;
  label?: string | null;
  strategyType?: string | null;
};

export type DiaDExperimentTopProvenanceSlotV1 = {
  rank: number;
  runId?: string | null;
  p1Status: string;
  reason?: string | null;
};

export type DiaDExperimentTopProvenanceV1 = {
  evidenceLevel: "in_sample_only" | "lab_validated";
  slots: DiaDExperimentTopProvenanceSlotV1[];
};

export type DiaDExperimentTopV1 = {
  artifactType?: "ART-DIA-D-EXPERIMENT-TOP";
  schemaVersion?: "1.0.0";
  id: string;
  instrumentId: string;
  timeframe: string;
  /** Fecha D del experimento (ISO `YYYY-MM-DD`). */
  asOfDiaD: string;
  /** Sello del servidor al insertar la evidencia. */
  savedAt: string;
  level: string;
  slots: InstrumentStrategyTopSlotV1[];
  symbol?: string | null;
  coachHeadline?: string | null;
  productionTop1AtSave?: DiaDExperimentTop1RefV1 | null;
  provenance?: DiaDExperimentTopProvenanceV1 | null;
};

export type PersistDiaDExperimentTopRequestV1 = {
  instrumentId: string;
  timeframe: string;
  asOfDiaD: string;
  slots: InstrumentStrategyTopSlotV1[];
  symbol?: string | null;
  coachHeadline?: string | null;
  productionTop1AtSave?: DiaDExperimentTop1RefV1 | null;
};
