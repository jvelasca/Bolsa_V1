/**
 * Propose desde gráfico / Operativa → cola F3 (Camino C), con gates SEMI/Estudio.
 * Misma disciplina que Finalistas y Alarm inbox. No Camino D.
 */

import { api } from "@/lib/api";
import {
  demoBookAllowsEnqueueConfirm,
  demoBookRequiresEstudioMembership,
  ESTUDIO_MEMBERSHIP_REQUIRED_MSG,
  loadDemoBookPrefs,
} from "@/features/trading/demo-book-prefs";
import { finalizeSupervisedProposePayload } from "@/features/trading/supervised-opening-sizing";
import type { SupervisedProposePayload } from "@/stores/supervised-f3-queue-store";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";

export async function proposeInstrumentSupervised(opts: {
  instrumentId: string;
  symbol: string;
  accountId: string;
  /** Origen cola / payload.source */
  source?: string;
  strategyDefinitionId?: string | null;
  strategyLabel?: string | null;
  priceHint?: number | null;
}): Promise<SupervisedProposePayload> {
  const book = loadDemoBookPrefs();
  if (!demoBookAllowsEnqueueConfirm(book.mode)) {
    throw new Error(
      "Libro en MANUAL: solo aviso. Cambia a SEMI en Operativa → Configuración para Proponer F3.",
    );
  }
  if (demoBookRequiresEstudioMembership(book.mode)) {
    if (!useEstudioMembershipStore.getState().contains(opts.instrumentId)) {
      throw new Error(ESTUDIO_MEMBERSHIP_REQUIRED_MSG);
    }
  }
  const summary = (await api.getAccountSummary(opts.accountId)).data;
  if (summary.positionsCount >= book.maxOpenPositions) {
    throw new Error(
      `Tope de posiciones (${book.maxOpenPositions}). Cierra alguna o sube el máximo en Libro DEMO.`,
    );
  }
  const priceHint =
    opts.priceHint != null && opts.priceHint > 0 ? opts.priceHint : null;
  const strategyRef = opts.strategyDefinitionId?.trim() || undefined;

  const res = await api.proposeRecommendation({
    instrumentId: opts.instrumentId,
    symbol: opts.symbol,
    accountId: opts.accountId,
    suggestedQuantity: 1,
    ...(priceHint != null ? { suggestedPrice: priceHint } : {}),
    includeFundamentals: true,
    includeMacro: true,
    includeEvidence: true,
    includeNews: true,
    ...(strategyRef ? { strategyOrSignalRef: strategyRef } : {}),
  });

  let payload: SupervisedProposePayload = finalizeSupervisedProposePayload({
    ...(res.data as SupervisedProposePayload),
    source: opts.source ?? "operativa",
    strategyOrSignalRef: strategyRef ?? null,
    strategyLabel: opts.strategyLabel ?? opts.symbol,
  });

  const close =
    payload.lastClose ?? payload.suggestedPrice ?? priceHint ?? null;
  if (close != null && payload.suggestedPrice == null) {
    payload = { ...payload, suggestedPrice: close };
  }
  return payload;
}
