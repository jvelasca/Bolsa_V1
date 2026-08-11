import type {
  BacktestRunResponseDto,
  BacktestStrategyType,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import type { ResolvedBacktestWindow } from "@/features/backtests/backtest-period";
import { LIST_AUTO_MAX_INSTRUMENTS } from "@/features/backtests/backtest-list-auto";

export type BatchRankRowStatus =
  | "pending"
  | "running"
  | "ok"
  | "error"
  | "skipped";

export type BatchRankRow = {
  instrumentId: string;
  symbol: string;
  name: string;
  status: BatchRankRowStatus;
  error?: string;
  runId?: string;
  totalReturnPct?: number;
  maxDrawdownPct?: number;
  tradeCount?: number;
  winCount?: number;
  sharpeRatio?: number | null;
  buyHoldReturnPct?: number | null;
  excessReturnPct?: number | null;
};

export type BatchSortKey =
  | "sharpe"
  | "return"
  | "drawdown"
  | "trades"
  | "excess";

export type BatchRunParams = {
  instrumentIds: string[];
  labels: Record<string, { symbol: string; name: string }>;
  strategyType?: BacktestStrategyType;
  strategyDefinitionId?: string;
  initialCash: number;
  commissionBps: number;
  slippageBps: number;
  timeframe: string;
  window: ResolvedBacktestWindow;
  /** Soft cap (IBEX-sized lists). Default = LIST_AUTO_MAX_INSTRUMENTS. */
  maxInstruments?: number;
  onProgress?: (rows: BatchRankRow[], done: number, total: number) => void;
  /** Seed detail cache as each OK run finishes (avoids empty detail after prune). */
  onRunComplete?: (
    detail: import("@bolsa/shared").BacktestRunDetailDto,
  ) => void;
  signal?: AbortSignal;
};

function metricNum(
  metrics: Record<string, number | string | null> | undefined,
  key: string,
): number | null {
  if (!metrics) return null;
  const v = metrics[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function sortBatchRows(
  rows: BatchRankRow[],
  sort: BatchSortKey,
): BatchRankRow[] {
  const ok = rows.filter((row) => row.status === "ok");
  const rest = rows.filter((row) => row.status !== "ok");
  const ranked = [...ok].sort((a, b) => {
    if (sort === "return") {
      return (b.totalReturnPct ?? -Infinity) - (a.totalReturnPct ?? -Infinity);
    }
    if (sort === "excess") {
      return (
        (b.excessReturnPct ?? -Infinity) - (a.excessReturnPct ?? -Infinity)
      );
    }
    if (sort === "drawdown") {
      // Lower drawdown is better (less negative magnitude as pct stored positive in UI often)
      return (a.maxDrawdownPct ?? Infinity) - (b.maxDrawdownPct ?? Infinity);
    }
    if (sort === "trades") {
      return (b.tradeCount ?? 0) - (a.tradeCount ?? 0);
    }
    const sa = a.sharpeRatio;
    const sb = b.sharpeRatio;
    if (sa == null && sb == null) {
      return (b.totalReturnPct ?? -Infinity) - (a.totalReturnPct ?? -Infinity);
    }
    if (sa == null) return 1;
    if (sb == null) return -1;
    return sb - sa;
  });
  return [...ranked, ...rest];
}

/** Sequential multi-instrument backtests (Phase C MVP — no batch API). */
export async function runBacktestBatch(
  params: BatchRunParams,
): Promise<BatchRankRow[]> {
  const max = params.maxInstruments ?? LIST_AUTO_MAX_INSTRUMENTS;
  const ids = params.instrumentIds.slice(0, max);
  const rows: BatchRankRow[] = ids.map((id) => {
    const label = params.labels[id];
    return {
      instrumentId: id,
      symbol: label?.symbol ?? id.slice(0, 8),
      name: label?.name ?? "",
      status: "pending" as const,
    };
  });

  const total = rows.length;
  params.onProgress?.([...rows], 0, total);

  for (let i = 0; i < rows.length; i += 1) {
    if (params.signal?.aborted) {
      for (let j = i; j < rows.length; j += 1) {
        if (rows[j]!.status === "pending") {
          rows[j] = { ...rows[j]!, status: "skipped", error: "Cancelado" };
        }
      }
      params.onProgress?.([...rows], i, total);
      break;
    }

    const row = rows[i]!;
    rows[i] = { ...row, status: "running" };
    params.onProgress?.([...rows], i, total);

    try {
      const result: BacktestRunResponseDto = await api.runBacktest({
        instrumentId: row.instrumentId,
        ...(params.strategyDefinitionId
          ? { strategyDefinitionId: params.strategyDefinitionId }
          : { strategyType: params.strategyType }),
        initialCash: params.initialCash,
        commissionBps: params.commissionBps,
        slippageBps: params.slippageBps,
        timeframe: params.timeframe,
        ...params.window,
      });
      rows[i] = {
        ...row,
        status: "ok",
        runId: result.data.id,
        symbol: result.data.symbol || row.symbol,
        name: result.data.name || row.name,
        totalReturnPct: result.data.totalReturnPct,
        maxDrawdownPct: result.data.maxDrawdownPct,
        tradeCount: result.data.tradeCount,
        winCount: result.data.winCount,
        sharpeRatio: metricNum(result.metrics, "sharpeRatio"),
        buyHoldReturnPct: metricNum(result.metrics, "buyHoldReturnPct"),
        excessReturnPct: metricNum(result.metrics, "excessReturnPct"),
      };
      params.onRunComplete?.(result.data);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Error al ejecutar la prueba";
      rows[i] = { ...row, status: "error", error: message };
    }

    params.onProgress?.([...rows], i + 1, total);
  }

  return rows;
}
