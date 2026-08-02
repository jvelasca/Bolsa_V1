/**
 * Q3.3 — panel comparación masiva (lista × estrategias, soft-cap).
 */

import { useMemo, useRef, useState } from 'react';
import type { BacktestStrategyType } from '@bolsa/shared';
import { Button } from '@/components/ui/button';
import type { ResolvedBacktestWindow } from '@/features/backtests/backtest-period';
import {
  MASS_COMPARE_MAX_CELLS,
  MASS_COMPARE_MAX_INSTRUMENTS,
  MASS_COMPARE_MAX_STRATEGIES,
  massCompareHeatNorm,
  planMassCompareJobs,
  rankMassCompareByInstrument,
  runMassCompare,
  type MassCompareCell,
} from '@/features/backtests/backtest-mass-compare';
import { cn } from '@/lib/utils';

type StrategyOpt = {
  key: string;
  label: string;
  strategyType?: BacktestStrategyType;
  strategyDefinitionId?: string;
};

type Props = {
  instrumentIds: string[];
  labels: Record<string, { symbol: string; name?: string }>;
  strategyOptions: StrategyOpt[];
  initialCash: number;
  commissionBps: number;
  slippageBps: number;
  timeframe: string;
  window: ResolvedBacktestWindow;
  className?: string;
};

function cellBg(norm: number | null): string | undefined {
  if (norm == null) return undefined;
  const hue = 8 + norm * 120;
  return `hsl(${hue} 55% 42% / 0.35)`;
}

export function BacktestMassComparePanel({
  instrumentIds,
  labels,
  strategyOptions,
  initialCash,
  commissionBps,
  slippageBps,
  timeframe,
  window,
  className,
}: Props) {
  const [selected, setSelected] = useState<string[]>(() =>
    strategyOptions.slice(0, 3).map((s) => s.key),
  );
  const [cells, setCells] = useState<MassCompareCell[]>([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const abortRef = useRef<AbortController | null>(null);

  const strategies = useMemo(
    () => strategyOptions.filter((s) => selected.includes(s.key)).slice(0, MASS_COMPARE_MAX_STRATEGIES),
    [strategyOptions, selected],
  );

  const planned = planMassCompareJobs({
    instrumentIds,
    labels,
    strategies,
    initialCash,
    commissionBps,
    slippageBps,
    timeframe,
    window,
  });

  const sharpes = cells.filter((c) => c.status === 'ok' && c.sharpeRatio != null).map((c) => c.sharpeRatio!);
  const minS = sharpes.length ? Math.min(...sharpes) : 0;
  const maxS = sharpes.length ? Math.max(...sharpes) : 1;
  const ranking = rankMassCompareByInstrument(cells);

  const symbols = [...new Set(cells.map((c) => c.symbol))];
  const stratKeys = [...new Set(cells.map((c) => c.strategyKey))];

  async function start() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setCells([]);
    try {
      await runMassCompare({
        instrumentIds,
        labels,
        strategies,
        initialCash,
        commissionBps,
        slippageBps,
        timeframe,
        window,
        signal: controller.signal,
        onProgress: (next, done, total) => {
          setCells(next);
          setProgress({ done, total });
        },
      });
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  return (
    <div className={cn('space-y-2', className)}>
      <p className="text-[10px] leading-snug text-muted-foreground">
        Lista × estrategias (máx. {MASS_COMPARE_MAX_INSTRUMENTS}×{MASS_COMPARE_MAX_STRATEGIES},{' '}
        {MASS_COMPARE_MAX_CELLS} celdas). Ranking por Sharpe medio · heatmap. No es Play / Lista AUTO.
      </p>
      <div className="flex flex-wrap gap-2">
        {strategyOptions.slice(0, 12).map((s) => {
          const on = selected.includes(s.key);
          return (
            <label key={s.key} className="flex items-center gap-1 text-[10px]">
              <input
                type="checkbox"
                checked={on}
                disabled={running}
                onChange={() => {
                  setSelected((prev) =>
                    on ? prev.filter((k) => k !== s.key) : [...prev, s.key].slice(0, MASS_COMPARE_MAX_STRATEGIES),
                  );
                }}
              />
              {s.label}
            </label>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={running || strategies.length === 0 || instrumentIds.length === 0}
          onClick={() => void start()}
        >
          {running
            ? `Comparando… ${progress.done}/${progress.total}`
            : `Comparar masivo (${planned.length} celdas)`}
        </Button>
        {running ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => abortRef.current?.abort()}
          >
            Cancelar
          </Button>
        ) : null}
      </div>

      {cells.length > 0 && stratKeys.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[10px]">
            <thead>
              <tr>
                <th className="px-1 py-0.5 text-left font-medium">Activo</th>
                {stratKeys.map((k) => (
                  <th key={k} className="px-1 py-0.5 text-center font-medium">
                    {cells.find((c) => c.strategyKey === k)?.strategyLabel ?? k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {symbols.map((sym) => (
                <tr key={sym} className="border-t border-border/40">
                  <td className="px-1 py-0.5 font-medium">{sym}</td>
                  {stratKeys.map((k) => {
                    const cell = cells.find((c) => c.symbol === sym && c.strategyKey === k);
                    const norm = massCompareHeatNorm(cell?.sharpeRatio, minS, maxS);
                    return (
                      <td
                        key={k}
                        className="px-1 py-0.5 text-center tabular-nums"
                        style={{ backgroundColor: cell?.status === 'ok' ? cellBg(norm) : undefined }}
                        title={cell?.error ?? cell?.runId}
                      >
                        {cell?.status === 'ok'
                          ? cell.sharpeRatio == null
                            ? '—'
                            : cell.sharpeRatio.toFixed(2)
                          : cell?.status === 'error'
                            ? 'err'
                            : cell?.status === 'running'
                              ? '…'
                              : '·'}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {ranking.length > 0 ? (
        <ol className="list-decimal space-y-0.5 pl-4 text-[10px] text-muted-foreground">
          {ranking.slice(0, 10).map((r) => (
            <li key={r.instrumentId}>
              <span className="font-medium text-foreground">{r.symbol}</span>
              {' · '}
              Sharpe medio {r.avgSharpe == null ? '—' : r.avgSharpe.toFixed(2)} ({r.okCount} ok)
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
