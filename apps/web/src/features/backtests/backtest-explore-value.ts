/**
 * Coach / batería de genéricas (Explorar valor).
 *
 * - `ALL_PRESET_COACH_KEYS`: catálogo completo de genéricas para «Probar + coach».
 * - Cada run OK guarda `periodReturns` (tercios de equity) para el ranking ★ estable.
 * - El TOP ★ lo calcula `backtest-deep-coach` (local); la LLM solo narra.
 * - `mergeExploreIntoStrategyMatrix`: misma batería → tabla izquierda (Genéricas).
 *
 * @see docs/engineering/research-lifecycle.md § P2
 */

import {
  BACKTEST_STRATEGIES,
  STRATEGY_PRESET_CATEGORY_LABELS,
  STRATEGY_PRESET_KEYS,
  type BacktestStrategyType,
  type StrategyPresetCategory,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import type { ResolvedBacktestWindow } from "@/features/backtests/backtest-period";
import {
  filterStrategyMatrixRows,
  type StrategyMatrixFilter,
  type StrategyMatrixRow,
} from "@/features/backtests/backtest-strategy-matrix";
import {
  coachValidationNextStep,
  suggestOptimizeValidation,
  type OptimizeValidationHint,
} from "@/features/backtests/backtest-optimize-validation-hint";
import {
  periodReturnsFromEquity,
  type EquityPeriodReturns,
} from "@/features/backtests/backtest-period-returns";

export type ExplorePeriodReturns = EquityPeriodReturns;

export { periodReturnsFromEquity };

/**
 * @deprecated Prefer ALL_PRESET_COACH_KEYS for coach/explore — kept as “batería corta” histórica.
 * Una pregunta por familia; útil como atajo mental, no como catálogo completo.
 */
export const EXPLORE_PRESET_BATTERY: BacktestStrategyType[] = [
  "sma_crossover",
  "ema_crossover",
  "rsi_mean_reversion",
  "macd_signal_cross",
  "bollinger_lower_bounce",
  "golden_cross",
  "pullback_in_uptrend",
  "stoch_oversold",
];

/** Todas las genéricas del producto — coach / explorar completo. */
export const ALL_PRESET_COACH_KEYS: BacktestStrategyType[] = [
  ...STRATEGY_PRESET_KEYS,
];

export type ExploreRowStatus =
  | "pending"
  | "running"
  | "ok"
  | "error"
  | "skipped";

export type ExplorePresetRow = {
  strategyType: BacktestStrategyType;
  label: string;
  category: StrategyPresetCategory;
  categoryLabel: string;
  status: ExploreRowStatus;
  error?: string;
  runId?: string;
  /** Si viene de Mis estrategias / Mejor Lab. */
  strategyDefinitionId?: string | null;
  /**
   * Tras Lab → Coach:
   * - lab_improved: re-simulada desde Mejor
   * - lab_carry: sin mejora; visible pero no reanalizada
   */
  labPass?: "lab_improved" | "lab_carry" | null;
  barCount?: number;
  totalReturnPct?: number;
  maxDrawdownPct?: number;
  tradeCount?: number;
  winCount?: number;
  sharpeRatio?: number | null;
  buyHoldReturnPct?: number | null;
  excessReturnPct?: number | null;
  /**
   * Tercios de equity calculados al cerrar el run.
   * El coach ★ usa esto (sesgo a futuro) sin depender del caché React Query.
   */
  periodReturns?: ExplorePeriodReturns | null;
};

export type ExploreSortKey = "excess" | "sharpe" | "return" | "drawdown";

function metricNum(
  metrics: Record<string, number | string | null> | undefined,
  key: string,
): number | null {
  if (!metrics) return null;
  const v = metrics[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function sortExploreRows(
  rows: ExplorePresetRow[],
  sort: ExploreSortKey,
): ExplorePresetRow[] {
  const ok = rows.filter((row) => row.status === "ok");
  const rest = rows.filter((row) => row.status !== "ok");
  const ranked = [...ok].sort((a, b) => {
    if (sort === "return") {
      return (b.totalReturnPct ?? -Infinity) - (a.totalReturnPct ?? -Infinity);
    }
    if (sort === "drawdown") {
      return (a.maxDrawdownPct ?? Infinity) - (b.maxDrawdownPct ?? Infinity);
    }
    if (sort === "sharpe") {
      const sa = a.sharpeRatio;
      const sb = b.sharpeRatio;
      if (sa == null && sb == null) {
        return (
          (b.excessReturnPct ?? -Infinity) - (a.excessReturnPct ?? -Infinity)
        );
      }
      if (sa == null) return 1;
      if (sb == null) return -1;
      return sb - sa;
    }
    return (b.excessReturnPct ?? -Infinity) - (a.excessReturnPct ?? -Infinity);
  });
  return [...ranked, ...rest];
}

export type ExploreBatteryParams = {
  instrumentId: string;
  presets?: BacktestStrategyType[];
  initialCash: number;
  commissionBps: number;
  slippageBps: number;
  timeframe: string;
  window: ResolvedBacktestWindow;
  onProgress?: (rows: ExplorePresetRow[], done: number, total: number) => void;
  onRunComplete?: (
    detail: import("@bolsa/shared").BacktestRunDetailDto,
  ) => void;
  signal?: AbortSignal;
};

/** Same instrument, N presets — Phase P2 explore battery. */
export async function runExploreValueBattery(
  params: ExploreBatteryParams,
): Promise<ExplorePresetRow[]> {
  const presets = params.presets?.length
    ? params.presets
    : ALL_PRESET_COACH_KEYS;
  const rows: ExplorePresetRow[] = presets.map((strategyType) => {
    const meta = BACKTEST_STRATEGIES[strategyType];
    return {
      strategyType,
      label: meta?.label ?? strategyType,
      category: meta?.category ?? "trend",
      categoryLabel: STRATEGY_PRESET_CATEGORY_LABELS[meta?.category ?? "trend"],
      status: "pending" as const,
    };
  });

  const total = rows.length;
  params.onProgress?.([...rows], 0, total);

  for (let i = 0; i < rows.length; i += 1) {
    if (params.signal?.aborted) {
      for (let j = i; j < rows.length; j += 1) {
        if (rows[j]!.status === "pending") {
          rows[j] = {
            ...rows[j]!,
            status: "skipped",
            error: "Cancelado — no finalizada",
          };
        }
      }
      params.onProgress?.([...rows], i, total);
      break;
    }

    const row = rows[i]!;
    rows[i] = { ...row, status: "running" };
    params.onProgress?.([...rows], i, total);

    try {
      const result = await api.runBacktest(
        {
          instrumentId: params.instrumentId,
          strategyType: row.strategyType,
          initialCash: params.initialCash,
          commissionBps: params.commissionBps,
          slippageBps: params.slippageBps,
          timeframe: params.timeframe,
          ...params.window,
        },
        { signal: params.signal },
      );
      if (params.signal?.aborted) {
        rows[i] = {
          ...row,
          status: "skipped",
          error: "Cancelado — no finalizada",
        };
      } else {
        rows[i] = {
          ...row,
          status: "ok",
          runId: result.data.id,
          barCount: result.data.barCount,
          totalReturnPct: result.data.totalReturnPct,
          maxDrawdownPct: result.data.maxDrawdownPct,
          tradeCount: result.data.tradeCount,
          winCount: result.data.winCount,
          sharpeRatio: metricNum(result.metrics, "sharpeRatio"),
          buyHoldReturnPct: metricNum(result.metrics, "buyHoldReturnPct"),
          excessReturnPct: metricNum(result.metrics, "excessReturnPct"),
          periodReturns: periodReturnsFromEquity(result.data.equityCurve),
        };
        params.onRunComplete?.(result.data);
      }
    } catch (error) {
      if (
        params.signal?.aborted ||
        (error instanceof DOMException && error.name === "AbortError")
      ) {
        rows[i] = {
          ...row,
          status: "skipped",
          error: "Cancelado — no finalizada",
        };
      } else {
        const message =
          error instanceof Error
            ? error.message
            : "Error al ejecutar la prueba";
        rows[i] = { ...row, status: "error", error: message };
      }
    }

    params.onProgress?.([...rows], i + 1, total);
  }

  return rows;
}

export type ExploreCoachNote = {
  headline: string;
  bullets: string[];
  nextSteps: string[];
  buyHoldReturnPct: number | null;
  beatCount: number;
  best?: ExplorePresetRow;
  /** Lab validation the Optimizar tab will prefill (P6). */
  validationHint?: OptimizeValidationHint;
};

/** Heuristic coach (local). Does not invent edge — only reads battery vs buy & hold. */
export function buildExploreCoachNote(
  rows: ExplorePresetRow[],
  symbol: string,
  opts?: { barLimit?: number | null },
): ExploreCoachNote {
  const ok = rows.filter((row) => row.status === "ok");
  const buyHold =
    ok
      .map((row) => row.buyHoldReturnPct)
      .find((v) => v != null && Number.isFinite(v)) ?? null;
  const beaters = sortExploreRows(
    ok.filter((row) => (row.excessReturnPct ?? -Infinity) > 0),
    "excess",
  );
  const best = sortExploreRows(ok, "excess")[0];
  const beatCount = beaters.length;
  const barLimit = opts?.barLimit ?? best?.barCount ?? ok[0]?.barCount;
  const validationHint = suggestOptimizeValidation(barLimit);

  const bhText =
    buyHold == null
      ? "sin baseline"
      : `${buyHold >= 0 ? "+" : ""}${buyHold.toFixed(1)}% buy & hold`;

  if (ok.length === 0) {
    return {
      headline: `${symbol}: la batería no produjo resultados útiles.`,
      bullets: ["Revisa sync OHLCV (≥50 barras) y vuelve a explorar."],
      nextSteps: ["Sincronizar el valor", "Probar un solo preset manualmente"],
      buyHoldReturnPct: null,
      beatCount: 0,
      validationHint,
    };
  }

  if (beatCount === 0) {
    return {
      headline: `${symbol}: ninguna genérica del lote bate comprar y mantener (${bhText}).`,
      bullets: [
        best
          ? `La menos mala fue «${best.label}» (${(best.excessReturnPct ?? 0).toFixed(1)} pp vs B&H).`
          : "Sin candidatos.",
        "En este periodo el edge no aparece con reglas simples — no es momento de optimizar parámetros a ciegas.",
        validationHint.reason,
      ],
      nextSteps: [
        "Probar otro valor del IBEX con el mismo periodo",
        "O acotar una pregunta distinta (p. ej. solo tendencia alcista) antes de mezclar indicadores",
        "No desplegar en paper todavía",
        coachValidationNextStep(validationHint),
      ],
      buyHoldReturnPct: buyHold,
      beatCount: 0,
      best,
      validationHint,
    };
  }

  const top = beaters.slice(0, 3);
  return {
    headline: `${symbol}: ${beatCount} genérica(s) del lote mejoran buy & hold (${bhText}).`,
    bullets: [
      ...top.map(
        (row, index) =>
          `${index + 1}. «${row.label}» · estrategia ${(row.totalReturnPct ?? 0).toFixed(1)}% · exceso ${(row.excessReturnPct ?? 0).toFixed(1)} pp · DD ${(row.maxDrawdownPct ?? 0).toFixed(1)}%`,
      ),
      "Esto es solo evidencia in-sample (mismo periodo). No es luz verde para invertir.",
      "El coach solo interpreta genéricas (presets), no Mis estrategias.",
      validationHint.reason,
    ],
    nextSteps: [
      `Abrir el detalle de «${top[0]!.label}» y revisar operaciones / racional`,
      coachValidationNextStep(validationHint),
      "Revisar checklist pre-paper tras adoptar (OOS/WF/CPCV + Edge lab)",
    ],
    buyHoldReturnPct: buyHold,
    beatCount,
    best: top[0],
    validationHint,
  };
}

/** Map matrix rows (presets / saved con presetKey) into coach/explore rows. */
export function matrixRowsToExploreRows(
  rows: StrategyMatrixRow[],
): ExplorePresetRow[] {
  return rows
    .filter((row) => Boolean(row.presetKey))
    .filter((row) => row.status !== "idle")
    .map((row) => {
      const strategyType = row.presetKey!;
      const meta = BACKTEST_STRATEGIES[strategyType];
      const category = meta?.category ?? "trend";
      const status: ExploreRowStatus =
        row.status === "ok"
          ? "ok"
          : row.status === "error"
            ? "error"
            : row.status === "skipped"
              ? "skipped"
              : row.status === "running"
                ? "running"
                : "pending";
      return {
        strategyType,
        label: row.label,
        category,
        categoryLabel: STRATEGY_PRESET_CATEGORY_LABELS[category],
        status,
        error: row.error,
        runId: row.runId,
        strategyDefinitionId: row.strategyDefinitionId ?? null,
        barCount: row.barCount,
        totalReturnPct: row.totalReturnPct,
        maxDrawdownPct: row.maxDrawdownPct,
        tradeCount: row.tradeCount,
        sharpeRatio: row.sharpeRatio ?? null,
        buyHoldReturnPct: row.buyHoldReturnPct ?? null,
        excessReturnPct: row.excessReturnPct ?? null,
        periodReturns: row.periodReturns ?? null,
      };
    });
}

/**
 * @deprecated Prefer matrixRowsToExploreRows — solo filas preset ya cerradas.
 */
export function matrixPresetRowsToExploreRows(
  rows: StrategyMatrixRow[],
): ExplorePresetRow[] {
  return matrixRowsToExploreRows(
    rows.filter(
      (row) =>
        row.kind === "preset" &&
        (row.status === "ok" ||
          row.status === "error" ||
          row.status === "skipped"),
    ),
  );
}

/**
 * Copia el progreso de la batería coach a la matriz izquierda (filas genéricas).
 * Misma fuente de verdad que «Resultados de la batería» en el panel Coach.
 */
export function mergeExploreIntoStrategyMatrix(
  matrix: StrategyMatrixRow[],
  explore: ExplorePresetRow[],
): StrategyMatrixRow[] {
  if (explore.length === 0) return matrix;
  const byType = new Map(explore.map((row) => [row.strategyType, row]));
  return matrix.map((row) => {
    if (row.kind !== "preset" || !row.presetKey) return row;
    const er = byType.get(row.presetKey);
    if (!er) return row;
    return {
      ...row,
      status: er.status,
      error: er.error,
      runId: er.runId,
      barCount: er.barCount,
      totalReturnPct: er.totalReturnPct,
      maxDrawdownPct: er.maxDrawdownPct,
      tradeCount: er.tradeCount,
      sharpeRatio: er.sharpeRatio ?? null,
      buyHoldReturnPct: er.buyHoldReturnPct ?? null,
      excessReturnPct: er.excessReturnPct ?? null,
      periodReturns: er.periodReturns ?? null,
    };
  });
}

/** Ids del lote a probar: selección dentro del filtro, o todas las del filtro. */
export function resolveMatrixCoachTargetIds(
  rows: StrategyMatrixRow[],
  filter: StrategyMatrixFilter,
  selectedIds: ReadonlySet<string>,
): string[] {
  const visible = filterStrategyMatrixRows(rows, filter);
  const selectedInView = visible.filter((row) => selectedIds.has(row.rowId));
  const targets = selectedInView.length > 0 ? selectedInView : visible;
  return targets.map((row) => row.rowId);
}
