/**
 * V1.63 — HUD flotante compacto de Decision Surface sobre el gráfico de Mercado.
 * Display-only — no firma · no BUY. ACCIÓN sigue en panel DECISIÓN.
 */

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { buildEntryOperatingTruth } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { DecisionSurfaceCompact } from "@/features/trading/decision-surface-compact";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";
import {
  useOpsSelfEval,
  portfolioReconStatusFromReport,
} from "@/features/operational-console/use-ops-self-eval";
import { usePositionOperationalView } from "@/features/trading/use-position-operational-view";

type ChartDecisionSurfaceHudProps = {
  instrumentId: string;
  symbol: string;
  className?: string;
};

export function ChartDecisionSurfaceHud({
  instrumentId,
  symbol,
  className,
}: ChartDecisionSurfaceHudProps) {
  const [collapsed, setCollapsed] = useState(false);
  const context = useInstrumentOperationalContext(instrumentId);
  const { entriesBlocked, paperDExecuteEnv } = useMesaEntriesBlocked();
  const bookPrefs = useDemoBookPrefs();
  const paperAuto = resolvePaperAutoPosture({
    bookMode: bookPrefs.mode,
    autoArmed: loadAutoArm().armed,
    paperDExecuteEnv,
  });
  const opsEval = useOpsSelfEval(context.accountId);
  const reconStatus = portfolioReconStatusFromReport(opsEval.data);
  const { phase, study, position } = context;

  const entryTruth =
    study && phase !== "posicion"
      ? buildEntryOperatingTruth({
          study,
          hasOpenPosition: Boolean(position),
          inConfirmQueue: context.inConfirmQueue,
          orderPendingFill: context.orderPendingFill,
          entriesBlocked,
          gateStatus: null,
          paperAuto,
        })
      : null;

  const positionPovResult = usePositionOperationalView(
    phase === "posicion" && position ? position : null,
    reconStatus,
  );

  if (context.loading) return null;

  const hasSurface =
    (phase === "posicion" && position != null) || entryTruth != null;
  if (!hasSurface) return null;

  return (
    <div
      className={cn(
        "pointer-events-auto absolute left-2 top-2 z-20 max-w-[min(280px,calc(100%-1rem))]",
        className,
      )}
      data-testid="chart-decision-surface-hud"
    >
      <div className="overflow-hidden rounded-md border border-border/70 bg-background/90 shadow-md backdrop-blur-sm">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 border-b border-border/50 px-2 py-1 text-left"
          onClick={() => setCollapsed((v) => !v)}
          aria-expanded={!collapsed}
          data-testid="chart-decision-surface-hud-toggle"
        >
          <span className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
            Estado operativo
          </span>
          {collapsed ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-3 w-3 shrink-0 text-muted-foreground" />
          )}
        </button>
        {!collapsed ? (
          <div className="p-1">
            {phase === "posicion" && position ? (
              <DecisionSurfaceCompact
                variant="position"
                density="hud"
                position={position}
                symbol={symbol}
                portfolioReconStatus={reconStatus}
                view={positionPovResult?.view}
                viewSource={positionPovResult?.source}
                className="border-0 bg-transparent shadow-none"
              />
            ) : entryTruth ? (
              <DecisionSurfaceCompact
                variant="entry"
                density="hud"
                truth={entryTruth}
                symbol={symbol}
                orderPendingFill={context.orderPendingFill}
                submitIntent={context.submitIntent}
                className="border-0 bg-transparent shadow-none"
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
