import { formatPct } from '@/features/charts/chart-utils';
import {
  sortBatchRows,
  type BatchRankRow,
  type BatchSortKey,
} from '@/features/backtests/backtest-batch-run';
import { cn } from '@/lib/utils';

const SORT_OPTIONS: { value: BatchSortKey; label: string }[] = [
  { value: 'excess', label: 'Vs buy & hold' },
  { value: 'sharpe', label: 'Sharpe' },
  { value: 'return', label: 'Resultado %' },
  { value: 'drawdown', label: 'Peor caída' },
  { value: 'trades', label: 'Operaciones' },
];

type Props = {
  rows: BatchRankRow[];
  sort: BatchSortKey;
  onSortChange: (sort: BatchSortKey) => void;
  selectedRunId?: string | null;
  selectedInstrumentId?: string | null;
  onSelectRun: (runId: string) => void;
  /** Abre el valor aunque no haya run (error / pending). */
  onSelectInstrument?: (instrumentId: string) => void;
  progress?: { done: number; total: number };
  listName?: string;
  running?: boolean;
};

function statusLabel(row: BatchRankRow): string {
  if (row.status === 'ok') return 'OK';
  if (row.status === 'running') return '…';
  if (row.status === 'pending') return '—';
  if (row.status === 'skipped') return 'Skip';
  return 'Error';
}

export function BacktestRankingTable({
  rows,
  sort,
  onSortChange,
  selectedRunId,
  selectedInstrumentId,
  onSelectRun,
  onSelectInstrument,
  progress,
  listName,
  running,
}: Props) {
  const ranked = sortBatchRows(rows, sort);
  const okCount = rows.filter((row) => row.status === 'ok').length;
  const errCount = rows.filter((row) => row.status === 'error').length;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="shrink-0 space-y-1">
        <h3
          className="text-sm font-medium text-foreground"
          title="Misma estrategia y periodo en cada valor. Ordena por Sharpe (por defecto), resultado u otras columnas. Clic en una fila para ver el gráfico."
        >
          Ranking de la lista
        </h3>
        <p className="text-xs text-muted-foreground">
          {listName ? `Lista «${listName}» · ` : ''}
          {okCount} ok
          {errCount > 0 ? ` · ${errCount} con error` : ''}
          {progress && progress.total > 0
            ? ` · progreso ${progress.done}/${progress.total}`
            : ''}
          {running ? ' · ejecutando…' : ''}
        </p>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          Ordenar por
          <select
            value={sort}
            onChange={(event) => onSortChange(event.target.value as BatchSortKey)}
            className="rounded-md border border-border bg-background px-2 py-1 text-foreground"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-card text-left text-muted-foreground">
            <tr>
              <th className="p-2 w-10">#</th>
              <th className="p-2">Valor</th>
              <th className="p-2">Estrategia</th>
              <th className="p-2">Buy&hold</th>
              <th className="p-2">Vs B&H</th>
              <th className="p-2">Peor caída</th>
              <th className="p-2">Sharpe</th>
              <th className="p-2">Ops</th>
              <th className="p-2">Estado</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((row, index) => {
              const rank = row.status === 'ok' ? index + 1 : '—';
              const selected =
                Boolean(row.runId && row.runId === selectedRunId) ||
                Boolean(selectedInstrumentId && row.instrumentId === selectedInstrumentId);
              const clickable = Boolean(onSelectInstrument) || (row.status === 'ok' && Boolean(row.runId));
              return (
                <tr
                  key={row.instrumentId}
                  className={cn(
                    'border-t border-border/50',
                    clickable && 'cursor-pointer hover:bg-muted/40',
                    selected && 'bg-amber-500/10 ring-1 ring-inset ring-amber-400/40',
                    row.status === 'error' && 'opacity-80',
                  )}
                  onClick={() => {
                    if (onSelectInstrument) {
                      onSelectInstrument(row.instrumentId);
                      return;
                    }
                    if (row.runId) onSelectRun(row.runId);
                  }}
                  title={row.error || (clickable ? 'Abrir en pestaña Valor' : undefined)}
                >
                  <td className="p-2 tabular-nums text-muted-foreground">{rank}</td>
                  <td className="p-2">
                    <span className="font-medium text-foreground">{row.symbol}</span>
                    {row.name ? (
                      <span className="ml-1 hidden text-xs text-muted-foreground sm:inline">
                        {row.name}
                      </span>
                    ) : null}
                  </td>
                  <td
                    className={cn(
                      'p-2 tabular-nums font-medium',
                      (row.totalReturnPct ?? 0) >= 0 ? 'text-success' : 'text-destructive',
                    )}
                  >
                    {row.totalReturnPct != null ? formatPct(row.totalReturnPct) : '—'}
                  </td>
                  <td
                    className={cn(
                      'p-2 tabular-nums',
                      (row.buyHoldReturnPct ?? 0) >= 0 ? 'text-success' : 'text-destructive',
                    )}
                  >
                    {row.buyHoldReturnPct != null ? formatPct(row.buyHoldReturnPct) : '—'}
                  </td>
                  <td
                    className={cn(
                      'p-2 tabular-nums font-medium',
                      (row.excessReturnPct ?? 0) > 0 && 'text-success',
                      (row.excessReturnPct ?? 0) < 0 && 'text-destructive',
                    )}
                  >
                    {row.excessReturnPct != null ? formatPct(row.excessReturnPct) : '—'}
                  </td>
                  <td className="p-2 tabular-nums text-destructive">
                    {row.maxDrawdownPct != null ? formatPct(row.maxDrawdownPct) : '—'}
                  </td>
                  <td className="p-2 tabular-nums">
                    {row.sharpeRatio != null ? row.sharpeRatio.toFixed(2) : '—'}
                  </td>
                  <td className="p-2 tabular-nums">
                    {row.tradeCount != null ? `${row.tradeCount}/${row.winCount ?? 0}` : '—'}
                  </td>
                  <td className="p-2 text-xs text-muted-foreground">
                    {statusLabel(row)}
                    {row.status === 'error' && row.error ? (
                      <span className="ml-1 truncate" title={row.error}>
                        · {row.error.slice(0, 40)}
                      </span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
