import { Save } from "lucide-react";
import type {
  OptimizeStrategyFamily,
  OosMetricsDto,
  SmaGridTrialDto,
} from "@bolsa/shared";
import {
  formatDelta,
  formatTrialParams,
} from "@/features/backtests/backtest-optimize-space";
import { formatPct } from "@/features/charts/chart-utils";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type OptimizeCompareRow = {
  id: string;
  status: "anchor" | "candidate" | "best" | "adopted";
  label: string;
  paramsLabel: string;
  fastPeriod: number;
  slowPeriod: number;
  signalPeriod?: number | null;
  period?: number | null;
  oversold?: number | null;
  overbought?: number | null;
  totalReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  score: number;
  oosMetrics?: OosMetricsDto | null;
  /** Deltas vs anchor (null for anchor row). */
  deltaReturnPct: number | null;
  deltaDrawdownPct: number | null;
  deltaScore: number | null;
  deltaOosScore: number | null;
  deltaFast: number | null;
  deltaSlow: number | null;
};

type Props = {
  rows: OptimizeCompareRow[];
  family?: OptimizeStrategyFamily | string;
  showOos?: boolean;
  /** How OOS columns were produced (footer copy). */
  oosMode?: "holdout" | "walkforward";
  onSave?: (row: OptimizeCompareRow) => void;
  savingId?: string | null;
  savedId?: string | null;
};

function DeltaCell({
  value,
  invert = false,
  suffix = " pp",
}: {
  value: number | null;
  invert?: boolean;
  suffix?: string;
}) {
  if (value == null || !Number.isFinite(value)) {
    return <span className="text-muted-foreground">—</span>;
  }
  const good = invert ? value < 0 : value > 0;
  const bad = invert ? value > 0 : value < 0;
  return (
    <span
      className={cn(
        "tabular-nums",
        good && "text-emerald-400",
        bad && "text-rose-400",
        !good && !bad && "text-muted-foreground",
      )}
    >
      {formatDelta(value)}
      {suffix}
    </span>
  );
}

function StatusBadge({ status }: { status: OptimizeCompareRow["status"] }) {
  const map = {
    anchor: {
      label: "Ancla",
      className: "border-sky-500/40 bg-sky-500/15 text-sky-200",
    },
    best: {
      label: "Mejor",
      className: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
    },
    adopted: {
      label: "Guardada",
      className: "border-amber-500/40 bg-amber-500/15 text-amber-200",
    },
    candidate: {
      label: "Candidato",
      className: "border-border/70 bg-muted/40 text-muted-foreground",
    },
  } as const;
  const item = map[status];
  return (
    <span
      className={cn(
        "inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        item.className,
      )}
    >
      {item.label}
    </span>
  );
}

function trialKey(trial: SmaGridTrialDto, family: string): string {
  if (family === "rsi_mean_reversion") {
    return `rsi-${trial.period}-${trial.oversold}-${trial.overbought}`;
  }
  if (family === "macd_signal_cross") {
    return `macd-${trial.fastPeriod}-${trial.slowPeriod}-${trial.signalPeriod}`;
  }
  return `sma-${trial.fastPeriod}-${trial.slowPeriod}`;
}

/** Comparison table: original anchor vs optimized candidates with deltas. */
export function BacktestOptimizeCompareTable({
  rows,
  family = "sma_crossover",
  showOos = false,
  oosMode = "holdout",
  onSave,
  savingId = null,
  savedId = null,
}: Props) {
  if (rows.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border/70 bg-muted/30 text-left text-muted-foreground">
            <th className="p-2">Estado</th>
            <th className="p-2">Operativa</th>
            <th className="p-2">Params</th>
            <th className="p-2">Δ params</th>
            <th className="p-2">Ret. IS</th>
            <th className="p-2">Δ ret.</th>
            <th className="p-2">DD IS</th>
            <th className="p-2">Score IS</th>
            <th className="p-2">Δ score</th>
            {showOos && (
              <>
                <th className="p-2">Ret. OOS</th>
                <th className="p-2">Score OOS</th>
                <th className="p-2">Δ OOS</th>
              </>
            )}
            <th className="p-2">Ops</th>
            {onSave && <th className="p-2 text-right">Acción</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isSaved = savedId === row.id;
            const status = isSaved ? "adopted" : row.status;
            return (
              <tr
                key={row.id}
                className={cn(
                  "border-t border-border/50",
                  row.status === "anchor" && "bg-sky-500/5",
                  row.status === "best" && "bg-emerald-500/5",
                )}
              >
                <td className="p-2">
                  <StatusBadge status={status} />
                </td>
                <td className="p-2 font-medium text-foreground">{row.label}</td>
                <td className="p-2 tabular-nums">{row.paramsLabel}</td>
                <td className="p-2 tabular-nums text-muted-foreground">
                  {row.deltaFast == null && row.deltaSlow == null ? (
                    "—"
                  ) : (
                    <>
                      {row.deltaFast != null && row.deltaFast !== 0 && (
                        <span className="mr-1">
                          Δa {formatDelta(row.deltaFast, 0)}
                        </span>
                      )}
                      {row.deltaSlow != null && row.deltaSlow !== 0 && (
                        <span>Δb {formatDelta(row.deltaSlow, 0)}</span>
                      )}
                      {row.deltaFast === 0 && row.deltaSlow === 0 && "igual"}
                    </>
                  )}
                </td>
                <td className="p-2 tabular-nums">
                  {formatPct(row.totalReturnPct)}
                </td>
                <td className="p-2">
                  <DeltaCell value={row.deltaReturnPct} />
                </td>
                <td className="p-2 tabular-nums">
                  {formatPct(row.maxDrawdownPct)}
                </td>
                <td className="p-2 font-medium tabular-nums">
                  {(Number.isFinite(row.score) ? row.score : 0).toFixed(2)}
                </td>
                <td className="p-2">
                  <DeltaCell value={row.deltaScore} suffix="" />
                </td>
                {showOos && (
                  <>
                    <td className="p-2 tabular-nums">
                      {row.oosMetrics
                        ? formatPct(row.oosMetrics.totalReturnPct)
                        : "—"}
                    </td>
                    <td className="p-2 tabular-nums">
                      {row.oosMetrics ? row.oosMetrics.score.toFixed(2) : "—"}
                    </td>
                    <td className="p-2">
                      <DeltaCell value={row.deltaOosScore} suffix="" />
                    </td>
                  </>
                )}
                <td className="p-2 tabular-nums">{row.tradeCount}</td>
                {onSave && (
                  <td className="p-2 text-right">
                    {row.status === "anchor" ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant={isSaved ? "default" : "outline"}
                        className="h-7 w-7 p-0"
                        title={
                          isSaved
                            ? "Ya guardada como estrategia propia"
                            : `Guardar «${row.paramsLabel} · opt»`
                        }
                        aria-label={`Guardar ${row.paramsLabel}`}
                        disabled={savingId === row.id}
                        onClick={() => onSave(row)}
                      >
                        <Save className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {showOos && (
        <p className="border-t border-border/50 px-2 py-1.5 text-[10px] text-muted-foreground">
          Familia {family} · columnas OOS ={" "}
          {oosMode === "walkforward"
            ? "último pliegue walk-forward (ver resumen arriba)"
            : "hold-out (un corte)"}
        </p>
      )}
    </div>
  );
}

export type OptimizeRankBy = "is" | "oos";

/** OOS with fewer trades than this is treated as weak evidence when ranking. */
export const MIN_OOS_TRADES_FOR_RANK = 2;

function trialOosScore(trial: SmaGridTrialDto): number | null {
  const score = trial.oosMetrics?.score;
  return typeof score === "number" && Number.isFinite(score) ? score : null;
}

function trialOosTradeCount(trial: SmaGridTrialDto): number {
  const count = trial.oosMetrics?.tradeCount;
  return typeof count === "number" && Number.isFinite(count) ? count : 0;
}

/** Sort key for OOS: sparse OOS (few trades) ranks below denser evidence. */
export function oosRankScore(trial: SmaGridTrialDto): number {
  const score = trialOosScore(trial);
  if (score == null) return Number.NEGATIVE_INFINITY;
  if (trialOosTradeCount(trial) < MIN_OOS_TRADES_FOR_RANK) {
    return score - 1_000;
  }
  return score;
}

/** Rank candidates for the compare table. OOS only when every trial has oosMetrics. */
export function rankTrialsForCompare(
  trials: SmaGridTrialDto[],
  rankBy: OptimizeRankBy,
): SmaGridTrialDto[] {
  const copy = [...trials];
  const oosReady =
    rankBy === "oos" &&
    copy.length > 0 &&
    copy.every((trial) => trialOosScore(trial) != null);

  copy.sort((a, b) => {
    if (oosReady) {
      const diff = oosRankScore(b) - oosRankScore(a);
      if (diff !== 0) return diff;
    }
    return b.score - a.score;
  });
  return copy;
}

export function buildCompareRows(opts: {
  family: OptimizeStrategyFamily | string;
  anchor: {
    fastPeriod?: number;
    slowPeriod?: number;
    signalPeriod?: number;
    period?: number;
    oversold?: number;
    overbought?: number;
    totalReturnPct: number;
    maxDrawdownPct: number;
    tradeCount: number;
    score: number;
    label: string;
    oosMetrics?: OosMetricsDto | null;
  };
  trials: SmaGridTrialDto[];
  topN?: number;
  /** When 'oos' and data allows, «Mejor» = best out-of-sample score. */
  rankBy?: OptimizeRankBy;
}): OptimizeCompareRow[] {
  const { family, anchor, trials, topN = 8, rankBy = "is" } = opts;
  const anchorParams = formatTrialParams(anchor, family);
  const ranked = rankTrialsForCompare(trials, rankBy);
  const rankedIs = rankTrialsForCompare(trials, "is");
  const effectiveRankBy: OptimizeRankBy =
    rankBy === "oos" &&
    trials.length > 0 &&
    trials.every((trial) => trialOosScore(trial) != null)
      ? "oos"
      : "is";

  const rows: OptimizeCompareRow[] = [
    {
      id: `anchor-${trialKey(anchor as SmaGridTrialDto, family)}`,
      status: "anchor",
      label: anchor.label,
      paramsLabel: anchorParams,
      fastPeriod: anchor.fastPeriod ?? 0,
      slowPeriod: anchor.slowPeriod ?? 0,
      signalPeriod: anchor.signalPeriod,
      period: anchor.period,
      oversold: anchor.oversold,
      overbought: anchor.overbought,
      totalReturnPct: anchor.totalReturnPct,
      maxDrawdownPct: anchor.maxDrawdownPct,
      tradeCount: anchor.tradeCount,
      score: anchor.score,
      oosMetrics: anchor.oosMetrics,
      deltaReturnPct: null,
      deltaDrawdownPct: null,
      deltaScore: null,
      deltaOosScore: null,
      deltaFast: null,
      deltaSlow: null,
    },
  ];

  const bestKey = ranked.length > 0 ? trialKey(ranked[0]!, family) : null;
  const bestIsKey = rankedIs.length > 0 ? trialKey(rankedIs[0]!, family) : null;
  const anchorKey = trialKey(anchor as SmaGridTrialDto, family);
  const bestLabel = effectiveRankBy === "oos" ? "Mejor OOS" : "Mejor IS";

  for (const trial of ranked.slice(0, topN)) {
    const key = trialKey(trial, family);
    if (key === anchorKey) continue;
    const isBest = key === bestKey;
    const isIsChamp = key === bestIsKey;
    let label = "Candidato";
    if (isBest) label = bestLabel;
    else if (effectiveRankBy === "oos" && isIsChamp)
      label = "Mejor IS (no OOS)";

    rows.push({
      id: `trial-${key}`,
      status: isBest ? "best" : "candidate",
      label,
      paramsLabel: formatTrialParams(trial, family),
      fastPeriod: trial.fastPeriod ?? 0,
      slowPeriod: trial.slowPeriod ?? 0,
      signalPeriod: trial.signalPeriod,
      period: trial.period,
      oversold: trial.oversold,
      overbought: trial.overbought,
      totalReturnPct: trial.totalReturnPct,
      maxDrawdownPct: trial.maxDrawdownPct,
      tradeCount: trial.tradeCount,
      score: trial.score,
      oosMetrics: trial.oosMetrics,
      deltaReturnPct: trial.totalReturnPct - anchor.totalReturnPct,
      deltaDrawdownPct: trial.maxDrawdownPct - anchor.maxDrawdownPct,
      deltaScore: trial.score - anchor.score,
      deltaOosScore:
        trial.oosMetrics && anchor.oosMetrics
          ? trial.oosMetrics.score - anchor.oosMetrics.score
          : null,
      deltaFast:
        (trial.fastPeriod ?? trial.period ?? 0) -
        (anchor.fastPeriod ?? anchor.period ?? 0),
      deltaSlow:
        (trial.slowPeriod ?? trial.oversold ?? 0) -
        (anchor.slowPeriod ?? anchor.oversold ?? 0),
    });
  }

  return rows;
}
