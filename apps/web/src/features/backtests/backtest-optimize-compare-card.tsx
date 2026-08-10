import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { formatPct } from "@/features/charts/chart-utils";
import {
  buildLocalOptimizeCompareNote,
  mergeOptimizeCompareAi,
  optimizeComparePromptBlob,
  type OptimizeBeforeAfterSnapshot,
  type OptimizeCompareAiNote,
} from "@/features/backtests/backtest-optimize-delta";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  snapshot: OptimizeBeforeAfterSnapshot;
  onDismiss?: () => void;
  onBackToCoach?: () => void;
};

function Metric({
  label,
  before,
  after,
  deltaLabel,
  better,
}: {
  label: string;
  before: string;
  after: string;
  /** Colored chip for Δ vs ancla (not the absolute after value). */
  deltaLabel?: string;
  better?: "up" | "down" | "neutral";
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background/80 px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-0.5 flex flex-wrap items-baseline gap-2 text-xs">
        <span className="tabular-nums text-muted-foreground">{before}</span>
        <span aria-hidden>→</span>
        <span className="tabular-nums font-semibold text-foreground">
          {after}
        </span>
        {deltaLabel ? (
          <span
            className={cn(
              "rounded px-1 py-0.5 text-[10px] font-medium tabular-nums",
              better === "up" &&
                "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
              better === "down" &&
                "bg-rose-500/15 text-rose-800 dark:text-rose-200",
              better === "neutral" && "bg-muted text-muted-foreground",
            )}
            title="Cambio vs ancla (antes)"
          >
            {deltaLabel} vs ancla
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function BacktestOptimizeCompareCard({
  snapshot,
  onDismiss,
  onBackToCoach,
}: Props) {
  const local = useMemo(
    () => buildLocalOptimizeCompareNote(snapshot),
    [snapshot],
  );
  const [note, setNote] = useState<OptimizeCompareAiNote>(local);

  useEffect(() => {
    setNote(local);
  }, [local]);

  const aiMutation = useMutation({
    mutationFn: () =>
      api.analyzeBacktestCoach({
        context: `Optimización antes/después · ${snapshot.symbol ?? ""} · ${snapshot.strategyLabel}`,
        battery: optimizeComparePromptBlob(snapshot),
        localSummary: [
          ...local.summary,
          ...local.detailed,
          ...local.nextSteps,
        ].join("\n"),
      }),
    onSuccess: (res) => {
      const payload = res.data.payload;
      if (!payload) {
        setNote({ ...local, engineLabel: res.data.engine || "heuristic" });
        return;
      }
      // Map coach-shaped payload into compare note.
      setNote(
        mergeOptimizeCompareAi(
          local,
          {
            headline: payload.headline,
            summary: payload.analysis?.slice(0, 3),
            detailed: [
              ...(payload.analysis?.slice(3) ?? []),
              payload.regimeNarrative,
              ...(payload.outlook ?? []),
            ].filter(Boolean) as string[],
            nextSteps: payload.outlook,
          },
          res.data.provider
            ? `${res.data.provider}${res.data.model ? ` · ${res.data.model}` : ""}`
            : res.data.engine,
        ),
      );
    },
  });

  useEffect(() => {
    aiMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot.strategyType, snapshot.after.paramsLabel, snapshot.deltaScore]);

  const retBetter =
    snapshot.deltaReturnPct > 0.5
      ? "up"
      : snapshot.deltaReturnPct < -0.5
        ? "down"
        : "neutral";
  const ddBetter =
    snapshot.deltaDrawdownPct < -0.5
      ? "up"
      : snapshot.deltaDrawdownPct > 0.5
        ? "down"
        : "neutral";

  return (
    <div
      className={cn(
        "space-y-3 rounded-lg border px-3 py-3",
        snapshot.improved
          ? "border-emerald-500/40 bg-emerald-500/5"
          : "border-amber-500/40 bg-amber-500/5",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p
            className={cn(
              "mb-1 inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
              snapshot.improved
                ? "bg-emerald-500/20 text-emerald-900 dark:text-emerald-100"
                : "bg-amber-500/20 text-amber-950 dark:text-amber-100",
            )}
          >
            {snapshot.improved ? "Mejoró vs ancla" : "Sin mejora clara"}
          </p>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Optimización · antes / después
          </p>
          <p className="text-sm font-semibold text-foreground">
            {note.headline}
          </p>
          <p className="text-[10px] text-muted-foreground">
            {snapshot.strategyLabel}
            {snapshot.symbol ? ` · ${snapshot.symbol}` : ""}
            {aiMutation.isPending ? " · IA…" : ` · ${note.engineLabel}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {onBackToCoach && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 text-[11px]"
              onClick={onBackToCoach}
            >
              Volver al coach
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 text-[11px]"
            disabled={aiMutation.isPending}
            onClick={() => aiMutation.mutate()}
            title="Pide a la IA una explicación del before/after (no reoptimiza)"
          >
            Explicar mejora (IA)
          </Button>
          {onDismiss && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 text-[11px]"
              onClick={onDismiss}
            >
              Cerrar
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-md border border-border/50 bg-background/60 px-2 py-2 text-xs">
          <p className="font-medium text-foreground">Antes</p>
          <p className="text-muted-foreground">{snapshot.before.paramsLabel}</p>
        </div>
        <div className="rounded-md border border-border/50 bg-background/60 px-2 py-2 text-xs">
          <p className="font-medium text-foreground">Después</p>
          <p className="text-muted-foreground">{snapshot.after.paramsLabel}</p>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <Metric
          label="Retorno (↑ mejor)"
          before={formatPct(snapshot.before.returnPct)}
          after={formatPct(snapshot.after.returnPct)}
          deltaLabel={
            snapshot.deltaReturnPct > 0
              ? `+${snapshot.deltaReturnPct.toFixed(1)} pp`
              : `${snapshot.deltaReturnPct.toFixed(1)} pp`
          }
          better={retBetter}
        />
        <Metric
          label="Drawdown (↓ mejor)"
          before={formatPct(snapshot.before.maxDrawdownPct)}
          after={formatPct(snapshot.after.maxDrawdownPct)}
          deltaLabel={
            snapshot.deltaDrawdownPct < 0
              ? `${snapshot.deltaDrawdownPct.toFixed(1)} pp (mejor)`
              : snapshot.deltaDrawdownPct > 0
                ? `+${snapshot.deltaDrawdownPct.toFixed(1)} pp (peor)`
                : "0 pp"
          }
          better={ddBetter}
        />
        <Metric
          label="Score lab (↑ mejor)"
          before={snapshot.before.score.toFixed(2)}
          after={snapshot.after.score.toFixed(2)}
          deltaLabel={
            snapshot.deltaScore > 0
              ? `+${snapshot.deltaScore.toFixed(2)}`
              : snapshot.deltaScore.toFixed(2)
          }
          better={
            snapshot.deltaScore > 0.05
              ? "up"
              : snapshot.deltaScore < -0.05
                ? "down"
                : "neutral"
          }
        />
      </div>
      <p className="text-[10px] text-muted-foreground">
        Verde = mejora operativa · ámbar = sin ventaja clara. El Lab mira sobre
        todo el score
        {snapshot.after.oosScore != null ? " OOS" : ""} (no solo el retorno
        histórico).
      </p>

      <div>
        <p className="text-[11px] font-medium text-foreground">Resumen IA</p>
        <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-muted-foreground">
          {note.summary.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-[11px] font-medium text-foreground">
          Análisis detallado
        </p>
        <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs leading-snug text-muted-foreground">
          {note.detailed.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-[11px] font-medium text-foreground">
          Siguiente paso
        </p>
        <ol className="mt-1 list-inside list-decimal space-y-0.5 text-xs text-muted-foreground">
          {note.nextSteps.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
