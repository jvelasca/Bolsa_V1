/**
 * P4 — payload del enlace durable «verificación DÍA-D ↔ ciclo AUTO» (puro, testeable).
 *
 * El enlace NUNCA se fabrica: sin `cycleId` (la verificación no se lanzó desde un ciclo) la
 * función devuelve `null`. Se comparte entre la persistencia AUTOMÁTICA del flujo de
 * verificación (`trading-dia-d-replay-panel.tsx`) y el guardado manual, para que ambas rutas
 * envíen exactamente lo mismo y la tabla de ciclos refleje la realidad.
 *
 * @see apps/web/src/features/auto-monitor/dia-d-cycle-verification-status.ts
 * @see packages/shared/src/dia-d-verification-api.ts
 */

import type { DiaDCycleVerificationPersistDto } from "@bolsa/shared";
import type { DiaDSessionEvidenceV1 } from "@/features/trading/dia-d-session-evidence";

export type DiaDCycleVerificationLinkInput = {
  /** Ciclo AUTO desde el que se lanzó; `null`/vacío ⇒ no hay enlace que persistir. */
  cycleId?: string | null;
  instrumentId: string;
  symbol: string;
  diaD: string;
  endDate: string;
  mode: string;
  strategyDefinitionId: string;
  strategyPresetKey?: string | null;
  strategyVersion?: string | null;
  /** Evidencia ya calculada: banda, confianza y métricas (sin recálculo). */
  evidence: Pick<DiaDSessionEvidenceV1, "band" | "confidence" | "metrics">;
  /** Evidencia de Fase 2 asociada (si ya se guardó); `null` si todavía no. */
  researchEvidenceId?: string | null;
};

export function buildDiaDCycleVerificationPayload(
  input: DiaDCycleVerificationLinkInput,
): DiaDCycleVerificationPersistDto | null {
  const cycleId = input.cycleId?.trim();
  if (!cycleId) return null;
  return {
    cycleId,
    instrumentId: input.instrumentId,
    symbol: input.symbol,
    diaD: input.diaD,
    endDate: input.endDate,
    mode: input.mode,
    strategyPresetKey: input.strategyPresetKey ?? null,
    strategyVersion: input.strategyVersion ?? null,
    strategyDefinitionId: input.strategyDefinitionId,
    band: input.evidence.band,
    result: {
      band: input.evidence.band,
      confidence: input.evidence.confidence,
      metrics: input.evidence.metrics,
    },
    researchEvidenceId: input.researchEvidenceId ?? null,
  };
}
