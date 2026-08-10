/**
 * Tabla de batería del panel Coach (evidencia secundaria, colapsable).
 *
 * Presenta el ranking de todos los presets probados por «Probar + coach»:
 * % resultado, vs B&H, DD y estado, con ordenamiento y acceso al Lab.
 * No tiene lógica de ciclo ni de peticiones: el orquestador pasa los datos
 * listos (rows + estado) y los callbacks de interacción.
 */

import { useMemo } from "react";
import { formatPct } from "@/features/charts/chart-utils";
import {
  sortExploreRows,
  type ExplorePresetRow,
  type ExploreSortKey,
} from "@/features/backtests/backtest-explore-value";
import {
  isOptimizableStrategy,
  optimizeFamilyProxyNote,
} from "@/features/backtests/backtest-optimize-seed";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SORT_OPTIONS: { value: ExploreSortKey; label: string }[] = [
  { value: "excess", label: "Vs buy & hold" },
  { value: "sharpe", label: "Sharpe" },
  { value: "return", label: "Resultado %" },
  { value: "drawdown", label: "Peor caída" },
];

interface Props {
  rows: ExplorePresetRow[];
  symbol: string;
  okCount: number;
  progress?: { done: number; total: number };
  running?: boolean;
  sort: ExploreSortKey;
  onSortChange: (sort: ExploreSortKey) => void;
  selectedRunId?: string | null;
  onSelectRun: (runId: string) => void;
  onOptimizeCandidate?: (row: ExplorePresetRow) => void;
}

export function BacktestExploreBatteryTable({
  rows,
  symbol,
  okCount,
  progress,
  running,
  sort,
  onSortChange,
  selectedRunId,
  onSelectRun,
  onOptimizeCandidate,
}: Props) {
  const ranked = useMemo(() => sortExploreRows(rows, sort), [rows, sort]);

  return (
    <details
      className="rounded-lg border border-border/70"
      open={running || okCount === 0}
    >
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-3 py-2 text-[11px] marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="font-medium text-foreground">
          Resultados de la batería
          <span className="ml-1.5 font-normal text-muted-foreground">
            {symbol} · {okCount} ok
            {progress && progress.total > 0
              ? ` · ${progress.done}/${progress.total}`
              : ""}
            {running ? " · ejecutando…" : ""}
          </span>
        </span>
        <span className="text-muted-foreground">Ver tabla</span>
      </summary>
      <div className="space-y-2 border-t border-border/50 px-3 pb-2.5 pt-2">
        <p className="text-[10px] text-muted-foreground">
          Ranking por % / B&H (histórico). Distinto del TOP ★ a futuro. Clic =
          Detalle · Lab = abre laboratorio.
        </p>
        <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
          Ordenar
          <select
            value={sort}
            onChange={(event) =>
              onSortChange(event.target.value as ExploreSortKey)
            }
            className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <div className="max-h-[min(420px,50vh)] overflow-auto rounded-md border border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card text-left text-muted-foreground">
              <tr>
                <th className="w-8 p-1.5">#</th>
                <th className="p-1.5">Preset</th>
                <th className="p-1.5">Estrategia</th>
                <th className="p-1.5">Vs B&H</th>
                <th className="p-1.5">DD</th>
                <th className="p-1.5">Estado</th>
                <th className="p-1.5 text-right">Acción</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((row, index) => {
                const rank = row.status === "ok" ? index + 1 : "—";
                const selected = Boolean(
                  row.runId && row.runId === selectedRunId,
                );
                const clickable = row.status === "ok" && Boolean(row.runId);
                const canLab =
                  row.status === "ok" &&
                  isOptimizableStrategy(row.strategyType);
                const proxy = optimizeFamilyProxyNote(row.strategyType);
                return (
                  <tr
                    key={row.strategyType}
                    className={cn(
                      "border-t border-border/50",
                      clickable && "cursor-pointer hover:bg-muted/40",
                      selected &&
                        "bg-amber-500/10 ring-1 ring-inset ring-amber-400/40",
                    )}
                    onClick={() => {
                      if (row.runId) onSelectRun(row.runId);
                    }}
                    title={row.error}
                  >
                    <td className="p-1.5 tabular-nums text-muted-foreground">
                      {rank}
                    </td>
                    <td className="p-1.5 font-medium text-foreground">
                      {row.label}
                      <span className="mt-0.5 block text-[10px] font-normal text-muted-foreground">
                        {row.categoryLabel}
                      </span>
                    </td>
                    <td
                      className={cn(
                        "p-1.5 tabular-nums",
                        (row.totalReturnPct ?? 0) >= 0
                          ? "text-success"
                          : "text-destructive",
                      )}
                    >
                      {row.totalReturnPct != null
                        ? formatPct(row.totalReturnPct)
                        : "—"}
                    </td>
                    <td
                      className={cn(
                        "p-1.5 tabular-nums",
                        (row.excessReturnPct ?? 0) > 0 && "text-success",
                        (row.excessReturnPct ?? 0) < 0 && "text-destructive",
                      )}
                    >
                      {row.excessReturnPct != null
                        ? formatPct(row.excessReturnPct)
                        : "—"}
                    </td>
                    <td className="p-1.5 tabular-nums text-destructive">
                      {row.maxDrawdownPct != null
                        ? formatPct(row.maxDrawdownPct)
                        : "—"}
                    </td>
                    <td className="p-1.5 text-muted-foreground">
                      {row.status === "ok"
                        ? "OK"
                        : row.status === "running"
                          ? "…"
                          : row.status === "error"
                            ? "Error"
                            : row.status === "skipped"
                              ? "Skip"
                              : "—"}
                    </td>
                    <td className="p-1.5 text-right">
                      {onOptimizeCandidate && canLab ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-6 px-1.5 text-[10px]"
                          title={proxy ?? "Abrir Lab con este preset"}
                          onClick={(event) => {
                            event.stopPropagation();
                            onOptimizeCandidate(row);
                          }}
                        >
                          {proxy ? "Lab≈" : "Lab"}
                        </Button>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}
