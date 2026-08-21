/**
 * Zona derecha fija de la barra Trading: hilos/colas + chip F3.
 *
 * Anchos reservados para que la barra no «salte» al cambiar conteos.
 * CORE-R v1.5: chip siempre visible → Ayuda · Monitor.
 * F3: cola Confirm SEMI → `/confirm` (R-12 C1).
 *
 * @see trading-status-bar.tsx
 */

import { BrainCircuit, FlaskConical, RefreshCw } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  formatCoreROpenSymbolsKey,
  formatCoreRStatusTitle,
  openHelpBacktesting,
} from "@/features/backtests/core-r-status";
import { TradingBackgroundStatus } from "@/features/trading/trading-background-status";
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";
import { useCoreRReviewQueueStore } from "@/stores/core-r-review-queue-store";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";
import { cn } from "@/lib/utils";

/** Slot Velas (sync OHLCV). */
const SLOT_SYNC = "w-[7.25rem]";
/** Slot CORE-R. */
const SLOT_CORE_R = "w-[4.75rem]";
/** Slot F3 Confirm. */
const SLOT_F3 = "w-[3.75rem]";
/** Slot Lista AUTO (solo si activo; el grupo ya tiene min-width). */
const SLOT_LIST_AUTO = "w-[7.5rem]";

export function TradingAppThreads() {
  const listAutoSummary = useListAutoActivityStore((s) => s.summary);
  const listAutoActive = useListAutoActivityStore((s) => s.active);
  const listAutoPaused = useListAutoActivityStore((s) => s.paused);
  const listAutoDetail = useListAutoActivityStore((s) => s.detail);
  const coreROpenCount = useCoreRReviewQueueStore((s) => s.openCount());
  const coreRSymbolsKey = useCoreRReviewQueueStore((s) =>
    formatCoreROpenSymbolsKey(s.items),
  );
  /** Primitivo estable — no devolver .length vía array filtrado en selector. */
  const f3Count = useSupervisedF3QueueStore((s) => s.items.length);

  const coreRTitle = useMemo(
    () =>
      formatCoreRStatusTitle(
        coreROpenCount,
        coreRSymbolsKey ? coreRSymbolsKey.split("\u0001") : [],
      ),
    [coreROpenCount, coreRSymbolsKey],
  );

  const coreRLabel =
    coreROpenCount > 0
      ? coreROpenCount > 99
        ? "CORE-R 99+"
        : `CORE-R ${coreROpenCount}`
      : "CORE-R —";

  const f3Label = f3Count > 99 ? "F3 99+" : `F3 ${f3Count}`;

  return (
    <div
      className="flex h-6 min-w-[16.5rem] shrink-0 items-center gap-0.5 rounded border border-border/60 bg-muted/15 px-0.5"
      data-testid="trading-status-threads"
      title="Procesos / colas en curso"
    >
      <span className="hidden shrink-0 px-0.5 text-[8px] uppercase tracking-wide text-muted-foreground/55 sm:inline">
        Colas
      </span>

      <div className={cn("shrink-0", SLOT_SYNC)}>
        <TradingBackgroundStatus className="w-full" />
      </div>

      <button
        type="button"
        onClick={() => openHelpBacktesting({ panel: "monitor" })}
        className={cn(
          "flex h-5 shrink-0 items-center justify-center gap-0.5 rounded px-0.5 text-[10px] tabular-nums hover:bg-accent",
          SLOT_CORE_R,
          coreROpenCount > 0
            ? "font-medium text-amber-900 dark:text-amber-200"
            : "text-muted-foreground/70",
        )}
        title={coreRTitle}
      >
        <RefreshCw className="h-3 w-3 shrink-0 opacity-70" aria-hidden />
        <span
          className={cn(
            "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
            coreROpenCount > 0 ? "bg-amber-500" : "bg-muted-foreground/35",
          )}
          aria-hidden
        />
        <span className="min-w-0 truncate">{coreRLabel}</span>
      </button>

      <button
        type="button"
        onClick={() => openHelpAiPlatform({ panel: "supervised-f3" })}
        className={cn(
          "flex h-5 shrink-0 items-center justify-center gap-0.5 rounded px-0.5 text-[10px] tabular-nums hover:bg-accent",
          SLOT_F3,
          f3Count > 0
            ? "font-medium text-sky-900 dark:text-sky-200"
            : "text-muted-foreground/70",
        )}
        title={
          f3Count > 0
            ? `Cola Confirm F3 · ${f3Count} pendiente(s)\nClic → Confirmar`
            : "Cola Confirm F3 vacía\nClic → Confirmar"
        }
      >
        <BrainCircuit className="h-3 w-3 shrink-0 opacity-70" aria-hidden />
        <span className="min-w-0 truncate">{f3Label}</span>
      </button>

      {listAutoActive && listAutoSummary ? (
        <Link
          to="/backtests?tab=run&focus=list_auto"
          className={cn(
            "flex h-5 min-w-0 shrink-0 items-center gap-0.5 truncate rounded px-0.5 text-[10px] font-medium hover:bg-accent",
            SLOT_LIST_AUTO,
            listAutoPaused
              ? "text-amber-800 dark:text-amber-200"
              : "text-violet-800 dark:text-violet-200",
          )}
          title={
            listAutoDetail
              ? `${listAutoSummary}\n${listAutoDetail}\nClic → tablero Lista AUTO`
              : `${listAutoSummary}\nClic → tablero Lista AUTO`
          }
        >
          <FlaskConical className="h-3 w-3 shrink-0 opacity-80" aria-hidden />
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
              listAutoPaused ? "bg-amber-500" : "animate-pulse bg-violet-500",
            )}
            aria-hidden
          />
          <span className="min-w-0 truncate tabular-nums">
            {listAutoSummary}
          </span>
        </Link>
      ) : (
        <span
          className={cn("hidden h-5 shrink-0 sm:block", SLOT_LIST_AUTO)}
          aria-hidden
        />
      )}
    </div>
  );
}
