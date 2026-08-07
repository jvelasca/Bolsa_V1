/**
 * Tras Confirm+ejecutar SEMI (Camino C): abre tenure Mandato + enlaza trade.
 * Fase 5a — sin Belief auto (5c freeze).
 *
 * @see docs/engineering/demo-operating-modes-brief-2026-08-03.md §5
 */

import { setAdoption } from '@/features/platform/strategy-adoption';
import { linkTradeToMandate } from '@/features/platform/operating-mandate';
import type { SupervisedProposePayload } from '@/stores/supervised-f3-queue-store';

export type SemiConfirmTradeResult = {
  status: string;
  reason?: string;
  transactionId?: string | null;
} | null;

function strategyRefFromPayload(payload: SupervisedProposePayload): {
  strategyDefinitionId: string | null;
  strategyLabel: string | null;
} {
  const direct =
    typeof payload.strategyOrSignalRef === 'string' && payload.strategyOrSignalRef
      ? payload.strategyOrSignalRef
      : null;
  const pkg = payload.decisionPackage as Record<string, unknown> | undefined;
  const fromPkg =
    (typeof pkg?.strategyOrSignalRef === 'string' && pkg.strategyOrSignalRef) ||
    (typeof pkg?.strategyDefinitionId === 'string' && pkg.strategyDefinitionId) ||
    null;
  const fromEdge =
    typeof payload.edgeReportRef === 'string' && payload.edgeReportRef
      ? payload.edgeReportRef
      : null;
  const id = direct || fromPkg || fromEdge || null;
  const label =
    (typeof payload.strategyLabel === 'string' && payload.strategyLabel) ||
    (typeof pkg?.strategyLabel === 'string' && pkg.strategyLabel) ||
    payload.symbol ||
    id?.slice(0, 12) ||
    null;
  return { strategyDefinitionId: id, strategyLabel: label };
}

/**
 * Si el intent se ejecutó/autorizó en DEMO, materializa mandato (propose_accepted)
 * y enlaza la transacción al tenure abierto.
 */
export function recordSemiConfirmMandate(opts: {
  accountId: string;
  payload: SupervisedProposePayload;
  intentStatus: string;
  trade: SemiConfirmTradeResult;
}): { mandateTenureId: string | null; linked: boolean } {
  if (opts.intentStatus !== 'executed' && opts.intentStatus !== 'authorized') {
    return { mandateTenureId: null, linked: false };
  }
  const { strategyDefinitionId, strategyLabel } = strategyRefFromPayload(opts.payload);
  const rec = setAdoption({
    instrumentId: opts.payload.instrumentId,
    accountId: opts.accountId,
    state: 'propuesta',
    reason: 'propose_accepted',
    strategyDefinitionId,
    strategyLabel,
    timeframe: '1d',
    actor: 'user',
    evidenceLevel: strategyDefinitionId ? 'lab_validated' : null,
  });
  let linked = false;
  const txId = opts.trade?.transactionId;
  const mandateTenureId = rec.mandateTenureId ?? null;
  if (txId) {
    const link = linkTradeToMandate({
      transactionId: txId,
      instrumentId: opts.payload.instrumentId,
      accountId: opts.accountId,
      mandateTenureId,
    });
    linked = Boolean(link);
  }
  return { mandateTenureId, linked };
}
