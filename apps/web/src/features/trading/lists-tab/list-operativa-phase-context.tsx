/**
 * Batch fase operativa Mercado (G2) para filas de lista — evita N hooks por fila.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import type { DecisionJournalStudyViewV1, PositionDto } from "@bolsa/shared";
import {
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
  resolveInstrumentOperationalFacts,
  hasOpenPositionQuantity,
} from "@/features/trading/instrument-operational-facts";
import type { MercadoCockpitPhase } from "@/features/trading/operativa-cockpit-phase";
import type { ListOperativaBadge } from "@/features/trading/operativa-phase-toast";

export type ListOperativaRow = {
  phase: MercadoCockpitPhase;
  badge: ListOperativaBadge | null;
  target1Touched: boolean;
  target1Managed: boolean;
  decisionId: string | null;
  positionId: string | null;
};

type Ctx = {
  byInstrument: Map<string, ListOperativaRow>;
  loading: boolean;
};

const ListOperativaPhaseContext = createContext<Ctx>({
  byInstrument: new Map(),
  loading: false,
});

function hasQuantity(position: PositionDto | null): boolean {
  return hasOpenPositionQuantity(position);
}

export function resolveListOperativaRow(input: {
  instrumentId: string;
  inEstudio: boolean;
  position: PositionDto | null;
  study: DecisionJournalStudyViewV1 | null;
  originStudy: DecisionJournalStudyViewV1 | null;
  inConfirmQueue: boolean;
  orderPendingFill: boolean;
}): ListOperativaRow {
  const facts = resolveInstrumentOperationalFacts(input);
  return {
    phase: facts.phase,
    badge: facts.badge,
    target1Touched: facts.target1Touched,
    target1Managed: facts.target1Managed,
    decisionId: facts.decisionId,
    positionId: facts.positionId,
  };
}

export function ListOperativaPhaseProvider({
  instrumentIds,
  children,
}: {
  instrumentIds: ReadonlyArray<string>;
  children: ReactNode;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const accountScope = useActiveAccountQueryKey();
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const studyContains = useEstudioMembershipStore((s) => s.contains);
  const { pendingOrders } = usePendingOrders();

  const ids = useMemo(
    () => [...new Set(instrumentIds.filter(Boolean))],
    [instrumentIds],
  );

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
    enabled: ids.length > 0,
  });

  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () => api.getDecisionStudies(effectiveAccountId!, { limit: 200 }),
    enabled: Boolean(effectiveAccountId) && ids.length > 0,
    staleTime: 30_000,
  });

  const byInstrument = useMemo(() => {
    const map = new Map<string, ListOperativaRow>();
    if (ids.length === 0) return map;

    const positions = portfolioQuery.data?.data.positions ?? [];
    const positionByInstrument = new Map<string, PositionDto>();
    for (const pos of positions) {
      if (Math.abs(Number(pos.quantity ?? 0)) <= 0) continue;
      positionByInstrument.set(pos.instrumentId, pos);
    }

    const studies = studiesQuery.data?.data?.studies ?? [];
    const byInstrumentStudy = studiesByInstrumentMap(studies);
    const byDecision = studiesByDecisionIdMap(studies);

    const confirmInstrumentIds = new Set(
      queueItems.map((i) => i.payload.instrumentId).filter(Boolean),
    );
    const pendingFillIds = new Set(
      pendingOrders.map((o) => o.instrumentId).filter(Boolean),
    );

    for (const instrumentId of ids) {
      const position = positionByInstrument.get(instrumentId) ?? null;
      let study: DecisionJournalStudyViewV1 | null = null;
      let originStudy: DecisionJournalStudyViewV1 | null = null;

      if (hasQuantity(position)) {
        const pair = pickPositionStudies(
          position!,
          byDecision,
          byInstrumentStudy,
        );
        study = pair.evolutionStudy;
        originStudy = pair.originStudy;
      } else {
        study = byInstrumentStudy.get(instrumentId) ?? null;
        originStudy = study;
      }

      map.set(
        instrumentId,
        resolveListOperativaRow({
          instrumentId,
          inEstudio: studyContains(instrumentId),
          position,
          study,
          originStudy,
          inConfirmQueue: confirmInstrumentIds.has(instrumentId),
          orderPendingFill: pendingFillIds.has(instrumentId),
        }),
      );
    }

    return map;
  }, [
    ids,
    portfolioQuery.data,
    studiesQuery.data,
    queueItems,
    pendingOrders,
    studyContains,
  ]);

  return (
    <ListOperativaPhaseContext.Provider
      value={{
        byInstrument,
        loading: portfolioQuery.isLoading || studiesQuery.isLoading,
      }}
    >
      {children}
    </ListOperativaPhaseContext.Provider>
  );
}

export function useListOperativaRow(
  instrumentId: string,
): ListOperativaRow | null {
  const { byInstrument } = useContext(ListOperativaPhaseContext);
  return byInstrument.get(instrumentId) ?? null;
}
