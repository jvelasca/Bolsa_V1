import { BacktestRankingTable } from "@/features/backtests/backtest-ranking-table";
import type {
  BatchRankRow,
  BatchSortKey,
} from "@/features/backtests/backtest-batch-run";

interface BacktestResultRankingProps {
  rows: BatchRankRow[];
  sort: BatchSortKey;
  onSortChange: (sort: BatchSortKey) => void;
  selectedRunId: string | null;
  selectedInstrumentId: string | null;
  /** Abre el valor en la pestaña Universo Valor (desde ranking, soft). */
  onOpenInstrument: (id: string, runId: string | null) => void;
  onSelectRun: (runId: string) => void;
  progress: { done: number; total: number };
  listName?: string;
  running: boolean;
}

/** Resultado «ranking» de la lista (Lote/Matriz de exploración). Extraído de
 * `backtests-page.tsx` (feature-slicing F4.8) sin cambiar semántica de
 * hooks/handlers del padre: solo transpone los handlers inline a props. */
export function BacktestResultRanking({
  rows,
  sort,
  onSortChange,
  selectedRunId,
  selectedInstrumentId,
  onOpenInstrument,
  onSelectRun,
  progress,
  listName,
  running,
}: BacktestResultRankingProps) {
  return (
    <BacktestRankingTable
      rows={rows}
      sort={sort}
      onSortChange={onSortChange}
      selectedRunId={selectedRunId}
      selectedInstrumentId={selectedInstrumentId}
      onSelectInstrument={(id) => {
        const row = rows.find((r) => r.instrumentId === id);
        onOpenInstrument(id, row?.runId ?? null);
      }}
      onSelectRun={onSelectRun}
      progress={progress}
      listName={listName}
      running={running}
    />
  );
}
