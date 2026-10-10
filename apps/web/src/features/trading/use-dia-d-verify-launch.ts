/**
 * Hook compartido de lanzamiento «Verificar D→hoy» (LAB · Cartera LAB).
 *
 * Encapsula el flujo DUPLICADO en la operación AUTO y en Finalistas para que exista una sola
 * forma de arrancar la verificación DÍA-D desde cualquier punto de entrada:
 *
 *   enterSession({mode:'auto', …}) → setAdoption(candidata) → navigate(deep-link) → pushToast.
 *
 * Read-only respecto al motor: no recalcula nada; solo prepara la sesión LAB y navega al deep-link
 * canónico. Fail-closed: sin `instrumentId`/`strategyDefinitionId` no navega ni escribe sesión.
 *
 * @see apps/web/src/features/platform/product-universe.ts (diaDVerifyHref)
 * @see apps/web/src/stores/dia-d-trading-session-store.ts (enterSession)
 */

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAlertsStore } from "@/stores/alerts-store";
import { useDiaDTradingSessionStore } from "@/stores/dia-d-trading-session-store";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import {
  effectiveDiaD,
  todayIsoDate,
} from "@/features/backtests/backtest-period";
import { loadBacktestRunContext } from "@/features/backtests/backtest-run-context";
import { diaDVerifyHref } from "@/features/platform/product-universe";
import { setAdoption } from "@/features/platform/strategy-adoption";

export type DiaDVerifyLaunchArgs = {
  instrumentId: string;
  symbol: string;
  strategyDefinitionId: string;
  strategyLabel: string;
  rank: number;
  /** Timeframe de adopción; por defecto `1d`. */
  timeframe?: string;
  /** D efectiva (ISO). Por defecto, la del contexto de Backtests (o hoy). */
  diaD?: string | null;
  /** Toast explícito; por defecto, la forma canónica de la verificación desde AUTO. */
  toast?: string;
};

/**
 * Devuelve el lanzador de verificación DÍA-D. Reutiliza EXACTAMENTE la forma de sesión existente
 * (modo `auto`, instrumento/símbolo/estrategia/rank/diaD/fin) y el destino canónico del helper.
 */
export function useDiaDVerifyLaunch(): (args: DiaDVerifyLaunchArgs) => void {
  const navigate = useNavigate();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enterDiaDSession = useDiaDTradingSessionStore((s) => s.enterSession);
  const { effectiveAccountId } = useActiveAccount();

  return useCallback(
    (args: DiaDVerifyLaunchArgs) => {
      const instrumentId = args.instrumentId?.trim();
      const strategyDefinitionId = args.strategyDefinitionId?.trim();
      // Fail-closed: el destino canónico exige instrumento y estrategia #1.
      if (!instrumentId || !strategyDefinitionId) return;

      const runCtx = loadBacktestRunContext();
      const diaD =
        args.diaD === undefined
          ? effectiveDiaD(runCtx.diaD)
          : effectiveDiaD(args.diaD);
      const timeframe = args.timeframe ?? "1d";

      enterDiaDSession({
        instrumentId,
        symbol: args.symbol,
        strategyDefinitionId,
        strategyLabel: args.strategyLabel,
        rank: args.rank,
        diaD,
        endDate: todayIsoDate(),
        mode: "auto",
      });

      // La adopción solo se escribe con cuenta activa (como en los dos llamantes originales).
      if (effectiveAccountId) {
        setAdoption({
          instrumentId,
          accountId: effectiveAccountId,
          state: "candidata",
          strategyDefinitionId,
          strategyLabel: args.strategyLabel,
          timeframe,
        });
      }

      navigate(diaDVerifyHref(instrumentId));
      pushToast(
        args.toast ?? `LAB · Verificar ${diaD} → hoy · ${args.strategyLabel}`,
      );
    },
    [navigate, pushToast, enterDiaDSession, effectiveAccountId],
  );
}
