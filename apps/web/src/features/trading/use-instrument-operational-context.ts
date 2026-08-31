/**
 * InstrumentOperationalContext — CONTEXTO → ESTADO → ACCIÓN para un valor.
 *
 * Fuente única de fase + `OperationalPlanView` en Mercado: la usan la tarjeta
 * cockpit (Operativa) y la capa de niveles del gráfico, así que los números
 * coinciden con Hoy / Journal / ficha de posición.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type {
  DecisionJournalStudyViewV1,
  OperationalPlanViewV1,
  PositionDto,
  SubmitIntentListItemV1,
} from "@bolsa/shared";
import {
  buildInvestmentPositionAggregate,
  buildOperationalPlanFromPosition,
  buildOperationalPlanFromStudy,
  pickPositionStudies,
  studiesByDecisionIdMap,
  studiesByInstrumentMap,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import {
  pickSubmitIntentForInstrument,
  useInFlightSubmitIntents,
} from "@/features/operations/use-in-flight-submit-intents";
import {
  mercadoCockpitShowsPlanLevels,
  resolveMercadoCockpitPhase,
  resolveMercadoTrailingCopy,
  type MercadoCockpitPhase,
  type MercadoTrailingCopyV1,
} from "@/features/trading/operativa-cockpit-phase";

export type InstrumentOperationalContextV1 = {
  instrumentId: string | null;
  accountId: string | null;
  phase: MercadoCockpitPhase;
  plan: OperationalPlanViewV1;
  /** Anti-ruido: false en vigilar / descubierto / sin_contexto. */
  showsPlanLevels: boolean;
  trailing: MercadoTrailingCopyV1;
  study: DecisionJournalStudyViewV1 | null;
  originStudy: DecisionJournalStudyViewV1 | null;
  position: PositionDto | null;
  inEstudio: boolean;
  inConfirmQueue: boolean;
  confirmQueueCount: number;
  /** Firma hecha, fill pendiente (orden en vuelo). */
  orderPendingFill: boolean;
  /** F2b — in-flight SubmitIntent for this instrument (list facts). */
  submitIntent: SubmitIntentListItemV1 | null;
  loading: boolean;
};

function hasQuantity(position: PositionDto | null): boolean {
  return Boolean(position && Math.abs(Number(position.quantity ?? 0)) > 0);
}

export function useInstrumentOperationalContext(
  instrumentId: string | null,
): InstrumentOperationalContextV1 {
  const { effectiveAccountId } = useActiveAccount();
  const accountScope = useActiveAccountQueryKey();
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const studyContains = useEstudioMembershipStore((s) => s.contains);
  const { pendingOrders } = usePendingOrders();
  const submitIntentsQuery = useInFlightSubmitIntents(effectiveAccountId);

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
  });

  // Misma fuente que Mesa Hoy / Libro — proyección; sin endpoint de histórico.
  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () => api.getDecisionStudies(effectiveAccountId!, { limit: 200 }),
    enabled: Boolean(effectiveAccountId),
    staleTime: 30_000,
  });

  const position = useMemo(() => {
    if (!instrumentId) return null;
    const positions = portfolioQuery.data?.data.positions ?? [];
    return (
      positions.find(
        (p) =>
          p.instrumentId === instrumentId &&
          Math.abs(Number(p.quantity ?? 0)) > 0,
      ) ?? null
    );
  }, [instrumentId, portfolioQuery.data]);

  const studies = useMemo(
    () => studiesQuery.data?.data?.studies ?? [],
    [studiesQuery.data],
  );
  const byInstrument = useMemo(
    () => studiesByInstrumentMap(studies),
    [studies],
  );
  const byDecision = useMemo(() => studiesByDecisionIdMap(studies), [studies]);

  const { study, originStudy } = useMemo(() => {
    if (!instrumentId) {
      return {
        study: null as DecisionJournalStudyViewV1 | null,
        originStudy: null as DecisionJournalStudyViewV1 | null,
      };
    }
    if (hasQuantity(position)) {
      const pair = pickPositionStudies(position!, byDecision, byInstrument);
      return { study: pair.evolutionStudy, originStudy: pair.originStudy };
    }
    const soft = byInstrument.get(instrumentId) ?? null;
    return { study: soft, originStudy: soft };
  }, [instrumentId, position, byInstrument, byDecision]);

  const plan = useMemo(() => {
    if (hasQuantity(position)) {
      const aggregate = buildInvestmentPositionAggregate({
        position: position!,
        study,
        originStudy: originStudy ?? study,
      });
      return buildOperationalPlanFromPosition({
        aggregate,
        markPrice: position!.lastPrice ?? null,
      });
    }
    return buildOperationalPlanFromStudy(study);
  }, [position, study, originStudy]);

  const inConfirmQueue = useMemo(() => {
    if (!instrumentId) return false;
    return queueItems.some((i) => i.payload.instrumentId === instrumentId);
  }, [instrumentId, queueItems]);

  const orderPendingFill = useMemo(() => {
    if (!instrumentId) return false;
    return pendingOrders.some((order) => order.instrumentId === instrumentId);
  }, [instrumentId, pendingOrders]);

  const submitIntent = useMemo(
    () =>
      pickSubmitIntentForInstrument(
        submitIntentsQuery.data?.data?.intents,
        instrumentId,
      ),
    [submitIntentsQuery.data, instrumentId],
  );

  const inEstudio = instrumentId ? studyContains(instrumentId) : false;

  const phase = resolveMercadoCockpitPhase({
    instrumentId,
    inEstudio,
    hasOpenPosition: hasQuantity(position),
    inConfirmQueue,
    orderPendingFill,
    tradePlanStatus: study?.tradePlanStatus ?? null,
    hasOperationalPlan: study?.hasOperationalPlan === true || plan.hasPlan,
  });

  const trailing = resolveMercadoTrailingCopy({
    phase,
    entry: plan.entry,
    stopVigente: plan.stopVigente,
    trailingActive: plan.trailingActive,
    trailingStopHint: plan.trailingStopHint,
    direction: plan.direction === "short" ? "short" : "long",
  });

  return {
    instrumentId,
    accountId: effectiveAccountId,
    phase,
    plan,
    showsPlanLevels: mercadoCockpitShowsPlanLevels(phase) && plan.hasPlan,
    trailing,
    study,
    originStudy,
    position,
    inEstudio,
    inConfirmQueue,
    confirmQueueCount: queueItems.length,
    orderPendingFill,
    submitIntent,
    loading: studiesQuery.isLoading || portfolioQuery.isLoading,
  };
}
