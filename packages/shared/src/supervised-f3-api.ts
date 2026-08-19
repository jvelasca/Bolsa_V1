/**
 * DTOs SEMI Confirm F3 queue multi-dispositivo — espejo API camelCase.
 *
 * P2.8: el wire (blob opaco del BE) no cambia; declaramos la *forma concreta*
 * de cada item para que `supervised-f3-sync.ts` serialice sin `as unknown as`.
 * P2.6 (R-2): hogar canónico de los tipos de la cola Supervised-F3. La forma
 * concreta de `payload` deriva de `RecommendationV1` + grafos web-only; al
 * tiparlo aquí, `supervised-f3-sync.ts` comparte el mismo tipo y elimina el cast
 * de frontera TS↔wire. El wire sigue siendo un blob JSON opaco round-trip del
 * BE, por lo que tipar `payload`/`origin` es SOLO compile-time: no cambia el valor.
 */

import type {
  AssessmentV1,
  EvidenceAssessmentV1,
  FundamentalAssessmentV1,
  MacroAssessmentV1,
  NewsAssessmentV1,
  RecommendationV1,
  TechnicalAssessmentV1,
  DecisionSessionV1,
  WeightContextV1,
} from "./cognitive/index.js";

/** Origen de la cola Supervised-F3 (badges en el panel). Espejo literal de la
 * union del web (`SupervisedQueueOrigin`). */
export type SupervisedQueueOriginDto =
  | "scan"
  | "finalists"
  | "chart"
  | "manual"
  | "alarm"
  | "operativa"
  | "asesor";

/** Payload de un ítem de la cola Supervised-F3: `RecommendationV1` + grafos
 * web-only opcionales. `decisionPackage` es un blob genuinamente abierto. */
export type SupervisedProposePayloadDto = RecommendationV1 & {
  technicalAssessment?: TechnicalAssessmentV1;
  fundamentalAssessment?: FundamentalAssessmentV1;
  macroAssessment?: MacroAssessmentV1;
  evidenceAssessment?: EvidenceAssessmentV1;
  newsAssessment?: NewsAssessmentV1;
  assessments?: AssessmentV1[];
  decisionPackage?: Record<string, unknown>;
  policyGate?: { status?: string; mode?: string; message?: string } | null;
  lastClose?: number | null;
  source?: string;
  /** Estrategia / señal de origen (Finalistas / Radar) para tenure Mandato. */
  strategyOrSignalRef?: string | null;
  strategyLabel?: string | null;
  decisionSession?: DecisionSessionV1;
  weightContext?: WeightContextV1;
  combinedScore?: number;
};

/** Meta de enqueue del web (`SupervisedEnqueueMeta`). */
export type SupervisedEnqueueMetaDto = {
  scanId?: string;
  symbol?: string;
  origin?: SupervisedQueueOriginDto;
};

export type SupervisedF3QueueItemDto = {
  id: string;
  enqueuedAt: string;
  scanId?: string;
  symbol?: string;
  origin?: SupervisedQueueOriginDto;
  payload: SupervisedProposePayloadDto;
};

export type SupervisedF3BundleDto = {
  accountId: string;
  items: Array<SupervisedF3QueueItemDto>;
  activeId?: string | null;
  updatedAt?: string | null;
};
