/**
 * Finalistas → Camino C (Propose supervisado).
 *
 * Llama `POST /api/ai/recommendations/propose` con FA + macro + evidence + news
 * y `strategyOrSignalRef` = estrategia del slot. Marca `source: 'finalists'`
 * para el badge de origen en la cola F3.
 *
 * Requisitos UI: cuenta activa (perfil → WeightContext) + TOP `lab_validated`.
 * Tras éxito: encolar en `useSupervisedF3QueueStore` con `origin: 'finalists'`
 * y `openHelpAiPlatform({ panel: 'supervised-f3' })` para foco Confirm.
 *
 * **No es** Desplegar en demo (Camino A) ni Plan D auto.
 *
 * @see PAPER_PATH_SUPERVISED in `paper-paths-copy.ts`
 * @see docs/engineering/backtesting-funnel-handoff-2026-07-29.md
 */

import { api } from '@/lib/api';
import type { SupervisedProposePayload } from '@/stores/supervised-f3-queue-store';

/** Valor de `payload.source` / origen de cola para Finalistas. */
export const FINALIST_SUPERVISED_SOURCE = 'finalists' as const;

/**
 * Propose de un Finalista hacia Supervisado F3.
 * @throws errores de red/API; la página muestra toast + status.
 */
export async function proposeFinalistSupervised(opts: {
  instrumentId: string;
  symbol: string;
  accountId: string;
  strategyDefinitionId: string;
}): Promise<SupervisedProposePayload> {
  const res = await api.proposeRecommendation({
    instrumentId: opts.instrumentId,
    symbol: opts.symbol,
    accountId: opts.accountId,
    suggestedQuantity: 1,
    includeFundamentals: true,
    includeMacro: true,
    includeEvidence: true,
    includeNews: true,
    strategyOrSignalRef: opts.strategyDefinitionId,
  });
  return {
    ...(res.data as SupervisedProposePayload),
    source: FINALIST_SUPERVISED_SOURCE,
  };
}
