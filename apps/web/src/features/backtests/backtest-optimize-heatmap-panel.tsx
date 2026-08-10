/**
 * Heatmap compacto + top-5 + aviso meseta (Lab P1).
 */

import {
  buildOptimizeHeatmap,
  heatmapCellStyle,
  heatmapNorm,
  type OptimizeHeatmapScoreMode,
} from "@/features/backtests/backtest-optimize-heatmap";
import type { OptimizeStrategyFamily, SmaGridTrialDto } from "@bolsa/shared";
import { cn } from "@/lib/utils";

type Props = {
  trials: SmaGridTrialDto[];
  family?: OptimizeStrategyFamily | string;
  scoreMode?: OptimizeHeatmapScoreMode;
  compact?: boolean;
  className?: string;
};

export function BacktestOptimizeHeatmapPanel({
  trials,
  family = "sma_crossover",
  scoreMode = "is",
  compact = false,
  className,
}: Props) {
  const model = buildOptimizeHeatmap({ trials, family, scoreMode, topN: 5 });
  if (!model) return null;

  const cols = model.xTicks.length;
  const maxCells = compact ? 64 : 120;
  const tooDense = model.cells.length > maxCells;

  return (
    <div
      className={cn(
        "space-y-2 rounded-lg border border-border/70 bg-muted/20 px-2.5 py-2",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[11px] font-medium text-foreground">
          Robustness map · {model.xLabel}×{model.yLabel}
          <span className="ml-1 font-normal text-muted-foreground">
            ({scoreMode === "oos" ? "OOS" : "IS"} · Q3.1)
          </span>
        </p>
        {model.best && (
          <p className="text-[10px] tabular-nums text-muted-foreground">
            Mejor {model.best.x}/{model.best.y} · {model.best.score.toFixed(2)}
          </p>
        )}
      </div>

      {model.plateau.isPlateau && (
        <p className="rounded-md border border-amber-500/35 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-100/90">
          {model.plateau.detail}
        </p>
      )}
      {!model.plateau.isPlateau && !compact && (
        <p className="text-[10px] text-muted-foreground">
          {model.plateau.detail}
        </p>
      )}

      {tooDense ? (
        <p className="text-[10px] text-muted-foreground">
          Malla densa ({model.cells.length} celdas) — se muestra el top-5; abre
          menos trials o usa la tabla.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <div
            className="inline-grid gap-px rounded-md border border-border/50 bg-border/40 p-px"
            style={{
              gridTemplateColumns: `auto repeat(${cols}, minmax(${compact ? "1.1rem" : "1.35rem"}, 1fr))`,
            }}
          >
            <div />
            {model.xTicks.map((x) => (
              <div
                key={`x-${x}`}
                className="px-0.5 text-center text-[8px] tabular-nums text-muted-foreground"
              >
                {x}
              </div>
            ))}
            {model.yTicks.map((y) => (
              <div key={`row-${y}`} className="contents">
                <div className="flex items-center pr-1 text-[8px] tabular-nums text-muted-foreground">
                  {y}
                </div>
                {model.xTicks.map((x) => {
                  const cell = model.cells.find((c) => c.x === x && c.y === y);
                  const norm = heatmapNorm(
                    cell?.score ?? null,
                    model.scoreMin,
                    model.scoreMax,
                  );
                  return (
                    <div
                      key={`${x}-${y}`}
                      title={
                        cell?.score != null
                          ? `${model.xLabel} ${x} · ${model.yLabel} ${y} · score ${cell.score.toFixed(2)}`
                          : `${x}/${y} · sin trial`
                      }
                      className={cn(
                        "h-4 min-w-[1.1rem] rounded-[2px]",
                        cell?.isBest &&
                          "ring-1 ring-emerald-300 ring-offset-1 ring-offset-background",
                        cell?.score == null && "bg-muted/30",
                      )}
                      style={
                        cell?.score != null ? heatmapCellStyle(norm) : undefined
                      }
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-0.5">
        <p className="text-[10px] font-medium text-muted-foreground">Top-5</p>
        <ol className="space-y-0.5 text-[10px] text-muted-foreground">
          {model.top5.map((t) => (
            <li
              key={`top-${t.rank}`}
              className="flex flex-wrap items-baseline gap-1.5"
            >
              <span className="font-semibold text-foreground/90">
                #{t.rank}
              </span>
              <span className="tabular-nums text-foreground">
                {t.score.toFixed(2)}
              </span>
              <span className="truncate">{t.paramsLabel}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
