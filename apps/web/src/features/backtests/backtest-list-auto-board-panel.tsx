/**
 * Panel visual del progreso Lista AUTO.
 *
 * Tabla de todos los instrumentos + barra + Δ Finalistas + CORE-R + Pausa/Stop.
 * Read-only respecto a la campaña; el hub orquesta queue/settle/pause.
 *
 * @see backtest-list-auto-board.ts
 */

import { Link } from "react-router-dom";
import {
  Check,
  Equal,
  Loader2,
  Pause,
  Play,
  SkipForward,
  Sparkles,
  Square,
  ZapOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { formatFreshnessAge } from "@/features/backtests/backtest-finalists-freshness";
import {
  listAutoBoardProgress,
  listAutoChangeLabel,
  listAutoPhaseLabel,
  type ListAutoBoardRow,
  type ListAutoBoardState,
  type ListAutoChangeKind,
  type ListAutoRowPhase,
} from "@/features/backtests/backtest-list-auto-board";
import {
  coreRNeedsAction,
  coreRVerdictLabel,
  type CoreRJudgment,
  type CoreRVerdict,
} from "@/features/backtests/core-r-judgment";

type Props = {
  board: ListAutoBoardState;
  className?: string;
  compact?: boolean;
  onSelectInstrument?: (instrumentId: string) => void;
  /** Resalta la fila del valor abierto en Valor / Detalle. */
  selectedInstrumentId?: string | null;
  /** Controles de campaña (solo si hay campaña viva o pausada). */
  campaignControls?: {
    canPause: boolean;
    canResume: boolean;
    canStop: boolean;
    onPause: () => void;
    onResume: () => void;
    onStop: () => void;
    onForceRescanRemaining?: () => void;
  };
};

function PhaseIcon({ phase }: { phase: ListAutoRowPhase }) {
  if (phase === "running") {
    return (
      <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-500" aria-hidden />
    );
  }
  if (phase === "saved") {
    return (
      <Check
        className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400"
        aria-hidden
      />
    );
  }
  if (phase === "omitted") {
    return (
      <ZapOff
        className="h-3.5 w-3.5 text-violet-600 dark:text-violet-300"
        aria-hidden
      />
    );
  }
  if (phase === "same") {
    return <Equal className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />;
  }
  if (phase === "skipped") {
    return (
      <SkipForward
        className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400"
        aria-hidden
      />
    );
  }
  if (phase === "aborted") {
    return <Square className="h-3.5 w-3.5 text-destructive" aria-hidden />;
  }
  return (
    <span
      className="inline-block h-2 w-2 rounded-full bg-muted-foreground/40"
      aria-hidden
    />
  );
}

function ChangeBadge({ change }: { change: ListAutoChangeKind }) {
  const label = listAutoChangeLabel(change);
  if (change === "unknown") {
    return <span className="text-muted-foreground/70">—</span>;
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium",
        change === "changed" || change === "new"
          ? "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200"
          : "bg-muted text-muted-foreground",
      )}
    >
      {(change === "changed" || change === "new") && (
        <Sparkles className="h-2.5 w-2.5" aria-hidden />
      )}
      {label}
    </span>
  );
}

const REEVAL_CLASS: Record<CoreRVerdict, string> = {
  keep: "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
  fresh_ok: "bg-violet-500/10 text-violet-800 dark:text-violet-200",
  review_lab: "bg-amber-500/15 text-amber-900 dark:text-amber-100",
  consider_replace: "bg-rose-500/15 text-rose-900 dark:text-rose-100",
  profile_mismatch: "bg-amber-500/20 text-amber-950 dark:text-amber-50",
  skipped_weak: "bg-amber-500/10 text-amber-800 dark:text-amber-200",
};

function ReevalBadge({ reeval }: { reeval?: CoreRJudgment | null }) {
  if (!reeval) {
    return <span className="text-muted-foreground/70">—</span>;
  }
  return (
    <span
      className={cn(
        "inline-flex max-w-[9rem] truncate rounded px-1.5 py-0.5 text-[10px] font-medium",
        REEVAL_CLASS[reeval.verdict],
      )}
      title={reeval.reason}
    >
      {coreRVerdictLabel(reeval.verdict)}
    </span>
  );
}

function RowStatus({ row }: { row: ListAutoBoardRow }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <PhaseIcon phase={row.phase} />
      <span
        className={cn(
          row.phase === "running" &&
            "font-medium text-sky-700 dark:text-sky-300",
          row.phase === "saved" && "text-emerald-800 dark:text-emerald-200",
          row.phase === "omitted" && "text-violet-800 dark:text-violet-200",
          row.phase === "skipped" && "text-amber-800 dark:text-amber-200",
        )}
      >
        {listAutoPhaseLabel(row.phase)}
      </span>
    </span>
  );
}

export function BacktestListAutoBoardPanel({
  board,
  className,
  compact = false,
  onSelectInstrument,
  selectedInstrumentId,
  campaignControls,
}: Props) {
  const progress = listAutoBoardProgress(board);
  const reevalAttention = board.rows.filter((r) =>
    coreRNeedsAction(r.reeval?.verdict),
  ).length;
  const title = board.aborted
    ? "Lista AUTO detenida (Stop)"
    : board.paused
      ? "Lista AUTO en pausa"
      : board.done
        ? "Lista AUTO completada"
        : "Lista AUTO en curso";

  return (
    <div
      className={cn(
        "flex min-h-0 flex-col gap-2 rounded-lg border border-border/70 bg-gradient-to-b from-background to-muted/25",
        compact ? "p-2" : "p-3",
        className,
      )}
      role="region"
      aria-label={title}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          <p
            className={cn(
              "font-medium text-foreground",
              compact ? "text-xs" : "text-sm",
            )}
          >
            {title}
          </p>
          <p className="text-[10px] leading-snug text-muted-foreground">
            {progress.doneCount}/{progress.total} · {progress.changedCount}{" "}
            cambiaron · {progress.omittedCount} omitidos (frescos) ·{" "}
            {progress.skippedCount} skip Lab
            {reevalAttention > 0
              ? ` · ${reevalAttention} a revisar (CORE-R)`
              : ""}
          </p>
        </div>
        <p
          className={cn(
            "tabular-nums font-semibold text-foreground",
            compact ? "text-xs" : "text-sm",
          )}
          aria-live="polite"
        >
          {progress.pct}%
        </p>
      </div>

      {campaignControls && !board.done && (
        <div className="flex flex-wrap items-center gap-1.5">
          {campaignControls.canPause ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 gap-1 text-[11px]"
              onClick={campaignControls.onPause}
              title="Termina el valor actual y no arranca el siguiente"
            >
              <Pause className="h-3 w-3" aria-hidden />
              Pausa
            </Button>
          ) : null}
          {campaignControls.canResume ? (
            <Button
              type="button"
              size="sm"
              variant="default"
              className="h-7 gap-1 text-[11px]"
              onClick={campaignControls.onResume}
              title="Continúa en el siguiente valor"
            >
              <Play className="h-3 w-3" aria-hidden />
              Reanudar
            </Button>
          ) : null}
          {campaignControls.canStop ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 gap-1 text-[11px]"
              onClick={campaignControls.onStop}
              title="Corta ya · el próximo Play continúa aquí"
            >
              <Square className="h-3 w-3" aria-hidden />
              Stop
            </Button>
          ) : null}
          {campaignControls.onForceRescanRemaining ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 gap-1 text-[11px]"
              onClick={campaignControls.onForceRescanRemaining}
              title="LAB: ignora frescura (Omitido) en el resto. No cambia el mandato de Trading hasta aceptar CORE-R en Monitor."
            >
              Reevaluar resto
            </Button>
          ) : null}
        </div>
      )}

      <div
        className={cn(
          "min-h-0 overflow-auto rounded-md border border-border/50",
          compact ? "max-h-48" : "max-h-[min(28rem,50vh)]",
        )}
      >
        <table className="w-full border-collapse text-left text-[11px]">
          <thead className="sticky top-0 z-[1] bg-muted/95 backdrop-blur-sm">
            <tr className="border-b border-border/60 text-[10px] uppercase tracking-wide text-muted-foreground">
              <th className="px-2 py-1.5 font-medium">#</th>
              <th className="px-2 py-1.5 font-medium">Valor</th>
              <th className="px-2 py-1.5 font-medium">Estado</th>
              <th className="px-2 py-1.5 font-medium">Δ</th>
              <th className="px-2 py-1.5 font-medium">Reeval</th>
              {!compact && (
                <th className="px-2 py-1.5 font-medium">Últ. búsqueda</th>
              )}
              {!compact && <th className="px-2 py-1.5 font-medium">Acción</th>}
              {!compact && <th className="px-2 py-1.5 font-medium">Detalle</th>}
            </tr>
          </thead>
          <tbody>
            {board.rows.map((row) => {
              const interactive = Boolean(onSelectInstrument);
              const selected = Boolean(
                selectedInstrumentId &&
                row.instrumentId === selectedInstrumentId,
              );
              const actions =
                row.reeval?.actions.filter((a) => a.id !== "none" && a.href) ??
                [];
              return (
                <tr
                  key={row.instrumentId}
                  className={cn(
                    "border-b border-border/40 last:border-0",
                    row.phase === "running" && "bg-sky-500/10",
                    row.phase === "saved" && "bg-emerald-500/5",
                    row.phase === "omitted" && "bg-violet-500/5",
                    interactive && "cursor-pointer hover:bg-muted/40",
                    selected &&
                      "bg-amber-500/10 ring-1 ring-inset ring-amber-400/40",
                  )}
                  title={interactive ? "Abrir en pestaña Valor" : undefined}
                  onClick={
                    interactive
                      ? () => onSelectInstrument?.(row.instrumentId)
                      : undefined
                  }
                >
                  <td className="px-2 py-1.5 tabular-nums text-muted-foreground">
                    {row.index + 1}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="font-semibold tracking-wide text-foreground">
                      {row.symbol}
                    </span>
                    {row.name && !compact ? (
                      <span className="ml-1.5 text-muted-foreground">
                        {row.name}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-1.5">
                    <RowStatus row={row} />
                  </td>
                  <td className="px-2 py-1.5">
                    <ChangeBadge change={row.change} />
                  </td>
                  <td className="px-2 py-1.5">
                    <ReevalBadge reeval={row.reeval} />
                  </td>
                  {!compact && (
                    <td className="px-2 py-1.5 text-muted-foreground">
                      {formatFreshnessAge(row.lastSearchAt)}
                    </td>
                  )}
                  {!compact && (
                    <td
                      className="px-2 py-1.5"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {actions.length === 0 ? (
                        <span className="text-muted-foreground/70">—</span>
                      ) : (
                        <span className="inline-flex flex-wrap gap-1">
                          {actions.slice(0, 3).map((a) => (
                            <Link
                              key={a.id}
                              to={a.href!}
                              className="rounded border border-border/70 px-1 py-0.5 text-[10px] text-foreground hover:bg-muted"
                              title={row.reeval?.reason}
                            >
                              {a.label}
                            </Link>
                          ))}
                        </span>
                      )}
                    </td>
                  )}
                  {!compact && (
                    <td className="max-w-[12rem] truncate px-2 py-1.5 text-muted-foreground">
                      {row.reeval?.reason ?? row.detail ?? "—"}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!compact && (
        <p className="text-[10px] leading-snug text-muted-foreground">
          CORE-R: juicio tras cada settle (Mantener / Lab / Valorar cambio). No
          pisa Finalistas. Omitido = frescos. Reevaluar resto = LAB (no cambia
          Trading). Stop → Play continúa. ↻ = desde cero.
        </p>
      )}
    </div>
  );
}
