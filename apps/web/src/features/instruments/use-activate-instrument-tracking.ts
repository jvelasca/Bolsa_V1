/**
 * Activar seguimiento desde hub: Finalistas #1 → crear Tracker → Radar.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import {
  buildTrackerFromFinalistSlot,
  screenersHrefAfterTrackerCreate,
} from "@/features/backtests/promote-finalist-to-tracker";
import { PAPER_PATH_RADAR } from "@/features/settings/paper-paths-copy";
import { useAlertsStore } from "@/stores/alerts-store";
import { instrumentTopBacktestsHref } from "@/features/backtests/instrument-strategy-top-panel";

export function useActivateInstrumentTracking() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pushToast = useAlertsStore((s) => s.pushToast);

  return useMutation({
    mutationFn: async (input: {
      instrumentId: string;
      symbol: string;
      timeframe?: string;
    }) => {
      const timeframe = input.timeframe ?? "1d";
      const topRes = await api.getInstrumentStrategyTop(
        input.instrumentId,
        timeframe,
      );
      const top = topRes.data;
      const slot =
        top?.slots.find((s) => s.rank === 1 && s.strategyDefinitionId) ??
        top?.slots.find((s) => Boolean(s.strategyDefinitionId));
      if (!slot?.strategyDefinitionId) {
        throw new Error("NO_FINALISTS");
      }
      const policiesRes = await api.getExecutionPolicies(true);
      const built = buildTrackerFromFinalistSlot({
        instrumentId: input.instrumentId,
        symbol: input.symbol,
        timeframe: top?.timeframe ?? timeframe,
        slot,
        topVersion: top?.version,
        scheduleKind: "manual",
        alarmPolicies: (policiesRes.data ?? []).map((p) => ({
          id: p.id,
          mode: p.mode,
          enabled: p.enabled,
        })),
      });
      if (!built.ok) throw new Error(built.error);
      const res = await api.createTracker(built.dto);
      return res.data;
    },
    onSuccess: (detail) => {
      void queryClient.invalidateQueries({ queryKey: ["trackers"] });
      void queryClient.invalidateQueries({ queryKey: ["tracker"] });
      pushToast(
        `${PAPER_PATH_RADAR.cta} creado: ${detail.name}. Abre Screeners para escanear / programar.`,
      );
      navigate(screenersHrefAfterTrackerCreate(detail.id));
    },
    onError: (err: Error, vars) => {
      if (err.message === "NO_FINALISTS") {
        pushToast(
          `Sin Finalistas con estrategia. Abre Backtesting para generar TOP de ${vars.symbol}.`,
        );
        navigate(
          instrumentTopBacktestsHref(vars.instrumentId, vars.timeframe ?? "1d"),
        );
        return;
      }
      pushToast(`Seguimiento: ${err.message}`);
    },
  });
}
