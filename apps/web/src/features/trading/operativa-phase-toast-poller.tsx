/**
 * Poller V1.28 G2 — toasts DISPARADA / T1 para universo Estudio.
 * Primera pasada silenciosa (no spam al abrir). T1 = informativo (H2).
 */

import { useEffect, useMemo, useRef } from "react";
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
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useAlertsStore } from "@/stores/alerts-store";
import { useNotificationPrefsStore } from "@/stores/notification-prefs-store";
import {
  collectOperativaToastEvents,
  formatOperativaToastMessage,
  loadOperativaToastSeen,
  partitionFreshOperativaEvents,
  saveOperativaToastSeen,
} from "@/features/trading/operativa-phase-toast";
import { resolveListOperativaRow } from "@/features/trading/lists-tab/list-operativa-phase-context";

const POLL_MS = 60_000;

function hasQuantity(position: PositionDto | null): boolean {
  return Boolean(position && Math.abs(Number(position.quantity ?? 0)) > 0);
}

export function OperativaPhaseToastPoller() {
  const entries = useEstudioMembershipStore((s) => s.members);
  const studyIds = useMemo(() => entries.map((e) => e.instrumentId), [entries]);
  const symbolById = useMemo(
    () => new Map(entries.map((e) => [e.instrumentId, e.symbol])),
    [entries],
  );

  const operativaToastEnabled = useNotificationPrefsStore(
    (s) => s.operativaToastEnabled,
  );
  const pushToast = useAlertsStore((s) => s.pushToast);
  const { effectiveAccountId } = useActiveAccount();
  const accountScope = useActiveAccountQueryKey();
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const studyContains = useEstudioMembershipStore((s) => s.contains);
  const { pendingOrders } = usePendingOrders();

  const seenRef = useRef<Set<string> | null>(null);
  const primedRef = useRef(false);

  const enabled = operativaToastEnabled && studyIds.length > 0;

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
    enabled,
    refetchInterval: enabled ? POLL_MS : false,
  });

  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () => api.getDecisionStudies(effectiveAccountId!, { limit: 200 }),
    enabled: Boolean(effectiveAccountId) && enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? POLL_MS : false,
  });

  useEffect(() => {
    if (!enabled) return;
    if (seenRef.current == null) seenRef.current = loadOperativaToastSeen();
    if (!portfolioQuery.data && !studiesQuery.data) return;

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

    const rows = studyIds.map((instrumentId) => {
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

      const resolved = resolveListOperativaRow({
        instrumentId,
        inEstudio: studyContains(instrumentId),
        position,
        study,
        originStudy,
        inConfirmQueue: confirmInstrumentIds.has(instrumentId),
        orderPendingFill: pendingFillIds.has(instrumentId),
      });

      return {
        instrumentId,
        symbol: symbolById.get(instrumentId) ?? instrumentId.slice(0, 8),
        phase: resolved.phase,
        target1Touched: resolved.target1Touched,
        target1Managed: resolved.target1Managed,
        decisionId: resolved.decisionId,
        positionId: resolved.positionId,
      };
    });

    const events = collectOperativaToastEvents(rows);
    const seen = seenRef.current;
    const { fresh, nextSeen } = partitionFreshOperativaEvents(events, seen);

    if (!primedRef.current) {
      saveOperativaToastSeen(nextSeen);
      seenRef.current = nextSeen;
      primedRef.current = true;
      return;
    }

    if (fresh.length === 0) return;

    saveOperativaToastSeen(nextSeen);
    seenRef.current = nextSeen;

    for (const event of fresh.slice(0, 3)) {
      pushToast(formatOperativaToastMessage(event), {
        action:
          event.kind === "disparada"
            ? {
                type: "open_trading_instrument",
                instrumentId: event.instrumentId,
                symbol: event.symbol,
                label: "Ver en Mercado",
              }
            : null,
      });
    }

    if (fresh.length > 3) {
      pushToast(
        `Mercado · +${fresh.length - 3} evento${fresh.length - 3 === 1 ? "" : "s"} operativos más`,
      );
    }
  }, [
    enabled,
    studyIds,
    symbolById,
    portfolioQuery.data,
    studiesQuery.data,
    queueItems,
    pendingOrders,
    studyContains,
    pushToast,
  ]);

  return null;
}
