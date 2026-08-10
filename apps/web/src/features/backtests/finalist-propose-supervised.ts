/**
 * Finalistas → Camino C (Propose supervisado).
 *
 * Llama `POST /api/ai/recommendations/propose` con FA + macro + evidence + news
 * y `strategyOrSignalRef` = estrategia del slot. Marca `source: 'finalists'`
 * para el badge de origen en la cola F3.
 *
 * Requisitos UI: cuenta activa (perfil → WeightContext) + TOP `lab_validated`.
 * Libro DEMO en SEMI (MANUAL solo aviso). Qty ≈ % cash; respeta maxOpenPositions.
 * Tras éxito: encolar en `useSupervisedF3QueueStore` con `origin: 'finalists'`
 * y `openHelpAiPlatform({ panel: 'supervised-f3' })` para foco Confirm.
 *
 * **No es** Desplegar en demo (Camino A) ni Plan D auto.
 *
 * @see PAPER_PATH_SUPERVISED in `paper-paths-copy.ts`
 * @see docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md
 */

import { api } from "@/lib/api";
import {
  demoBookAllowsEnqueueConfirm,
  demoBookRequiresEstudioMembership,
  ESTUDIO_MEMBERSHIP_REQUIRED_MSG,
  loadDemoBookPrefs,
  suggestQuantityFromCash,
} from "@/features/trading/demo-book-prefs";
import type { SupervisedProposePayload } from "@/stores/supervised-f3-queue-store";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";

/** Valor de `payload.source` / origen de cola para Finalistas. */
export const FINALIST_SUPERVISED_SOURCE = "finalists" as const;

/**
 * Propose de un Finalista hacia Supervisado F3.
 * @throws errores de red/API / libro MANUAL / tope posiciones; la página muestra toast + status.
 */
export async function proposeFinalistSupervised(opts: {
  instrumentId: string;
  symbol: string;
  accountId: string;
  strategyDefinitionId: string;
  strategyLabel?: string | null;
  /** Precio hint opcional (p. ej. last close del run) para sizing. */
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
  let suggestedQuantity = 1;
  if (priceHint != null && summary.cash > 0) {
    const q = suggestQuantityFromCash({
      cash: summary.cash,
      price: priceHint,
      sizePctOfCash: book.defaultSizePctOfCash,
    });
    if (q > 0) suggestedQuantity = q;
  }

  const res = await api.proposeRecommendation({
    instrumentId: opts.instrumentId,
    symbol: opts.symbol,
    accountId: opts.accountId,
    suggestedQuantity,
    includeFundamentals: true,
    includeMacro: true,
    includeEvidence: true,
    includeNews: true,
    strategyOrSignalRef: opts.strategyDefinitionId,
  });
  const payload = {
    ...(res.data as SupervisedProposePayload),
    source: FINALIST_SUPERVISED_SOURCE,
    strategyOrSignalRef: opts.strategyDefinitionId,
    strategyLabel: opts.strategyLabel ?? opts.symbol,
  } satisfies SupervisedProposePayload;

  // Si no había priceHint, recalcular qty con lastClose del propose.
  const close = payload.lastClose ?? payload.suggestedPrice ?? null;
  if (
    (opts.priceHint == null || !(opts.priceHint > 0)) &&
    close != null &&
    close > 0 &&
    summary.cash > 0
  ) {
    const q = suggestQuantityFromCash({
      cash: summary.cash,
      price: close,
      sizePctOfCash: book.defaultSizePctOfCash,
    });
    if (q > 0) {
      return { ...payload, suggestedQuantity: q, suggestedPrice: close };
    }
  }
  return payload;
}
