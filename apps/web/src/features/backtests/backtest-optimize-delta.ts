/**
 * Resumen antes/después de una optimización (ancla vs mejor trial) + narrativa IA.
 */

import type { OptimizeSmaGridResultDto, SmaGridTrialDto } from "@bolsa/shared";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";

export type OptimizeCompareSide = {
  label: string;
  returnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  score: number;
  oosReturnPct?: number | null;
  oosScore?: number | null;
  paramsLabel: string;
};

export type OptimizeBeforeAfterSnapshot = {
  strategyLabel: string;
  symbol?: string;
  strategyType: string;
  before: OptimizeCompareSide;
  after: OptimizeCompareSide;
  deltaReturnPct: number;
  deltaDrawdownPct: number;
  deltaScore: number;
  engine?: string;
  improved: boolean;
};

export type OptimizeCompareAiNote = {
  headline: string;
  summary: string[];
  detailed: string[];
  nextSteps: string[];
  engineLabel: string;
};

function formatParams(trial: SmaGridTrialDto, family?: string): string {
  if (family === "rsi_mean_reversion" || trial.period != null) {
    return `RSI ${trial.period ?? "—"} · ${trial.oversold ?? "—"}/${trial.overbought ?? "—"}`;
  }
  if (family === "macd_signal_cross" || trial.signalPeriod != null) {
    return `MACD ${trial.fastPeriod ?? "—"}/${trial.slowPeriod ?? "—"}/${trial.signalPeriod ?? "—"}`;
  }
  return `SMA ${trial.fastPeriod ?? "—"}/${trial.slowPeriod ?? "—"}`;
}

function sideFromTrial(
  trial: SmaGridTrialDto,
  label: string,
  family?: string,
): OptimizeCompareSide {
  return {
    label,
    returnPct: trial.totalReturnPct,
    maxDrawdownPct: trial.maxDrawdownPct,
    tradeCount: trial.tradeCount,
    score: trial.score,
    oosReturnPct: trial.oosMetrics?.totalReturnPct ?? null,
    oosScore: trial.oosMetrics?.score ?? null,
    paramsLabel: formatParams(trial, family),
  };
}

export function buildOptimizeBeforeAfter(
  seed: OptimizeSeed | null | undefined,
  result: OptimizeSmaGridResultDto,
): OptimizeBeforeAfterSnapshot | null {
  const best = result.trials[0];
  if (!best) return null;
  const family = String(result.strategyFamily ?? "sma_crossover");

  const beforeFromSeed: OptimizeCompareSide | null =
    seed && seed.anchorReturnPct != null
      ? {
          label: "Antes (prueba / ancla)",
          returnPct: seed.anchorReturnPct,
          maxDrawdownPct:
            seed.anchorMaxDrawdownPct ?? result.baseline.maxDrawdownPct,
          tradeCount: seed.anchorTradeCount ?? result.baseline.tradeCount,
          score: seed.anchorScore ?? result.baseline.score,
          paramsLabel:
            seed.anchorFast != null && seed.anchorSlow != null
              ? `SMA ${seed.anchorFast}/${seed.anchorSlow}`
              : seed.anchorPeriod != null
                ? `RSI ${seed.anchorPeriod}`
                : formatParams(result.baseline, family),
        }
      : null;

  const before =
    beforeFromSeed ??
    sideFromTrial(result.baseline, "Antes (baseline lab)", family);
  const after = sideFromTrial(best, "Después (mejor candidato)", family);
  const deltaReturnPct = after.returnPct - before.returnPct;
  const deltaDrawdownPct = after.maxDrawdownPct - before.maxDrawdownPct;
  const deltaScore = after.score - before.score;
  // Prefer OOS improvement when present.
  const improved =
    after.oosScore != null && before.oosScore == null
      ? after.oosScore > 0
      : after.oosScore != null && result.baseline.oosMetrics?.score != null
        ? after.oosScore >= (result.baseline.oosMetrics.score ?? 0)
        : deltaScore > 0 || (deltaReturnPct > 0 && deltaDrawdownPct <= 2);

  return {
    strategyLabel: seed?.strategyLabel ?? "Estrategia",
    symbol: seed?.symbol,
    strategyType: seed?.strategyType ?? family,
    before,
    after,
    deltaReturnPct,
    deltaDrawdownPct,
    deltaScore,
    engine: result.engine,
    improved,
  };
}

export function buildLocalOptimizeCompareNote(
  snap: OptimizeBeforeAfterSnapshot,
): OptimizeCompareAiNote {
  const sign = (n: number) => (n >= 0 ? "+" : "") + n.toFixed(1);
  const summary = [
    snap.improved
      ? `La optimización mejora el perfil operativo de «${snap.strategyLabel}» (${sign(snap.deltaScore)} en score).`
      : `El mejor candidato no mejora con claridad el ancla de «${snap.strategyLabel}» — conviene no adoptar a ciegas.`,
    `Retorno ${sign(snap.deltaReturnPct)} pp · drawdown ${sign(snap.deltaDrawdownPct)} pp.`,
  ];
  if (snap.after.oosReturnPct != null) {
    summary.push(
      `OOS del mejor: retorno ${snap.after.oosReturnPct.toFixed(1)}%` +
        (snap.after.oosScore != null
          ? ` · score OOS ${snap.after.oosScore.toFixed(2)}`
          : ""),
    );
  }
  const detailed = [
    `Antes: ${snap.before.paramsLabel} · ret ${snap.before.returnPct.toFixed(1)}% · DD ${snap.before.maxDrawdownPct.toFixed(1)}% · ${snap.before.tradeCount} ops · score ${snap.before.score.toFixed(2)}.`,
    `Después: ${snap.after.paramsLabel} · ret ${snap.after.returnPct.toFixed(1)}% · DD ${snap.after.maxDrawdownPct.toFixed(1)}% · ${snap.after.tradeCount} ops · score ${snap.after.score.toFixed(2)}.`,
    snap.improved
      ? "Lectura AT: si el tramo reciente del valor sigue el mismo régimen, el nuevo juego de parámetros tiene más sentido como hipótesis a validar (OOS/WF), no como señal final."
      : "Lectura AT: el grid puede estar sobreajustando ruido del tramo antiguo; prioriza validación OOS o vuelve al top-3 del coach por estrellas de futuro.",
  ];
  return {
    headline: snap.improved
      ? `${snap.symbol ? snap.symbol + ": " : ""}optimización con mejora vs ancla`
      : `${snap.symbol ? snap.symbol + ": " : ""}optimización sin ventaja clara`,
    summary,
    detailed,
    nextSteps: snap.improved
      ? [
          "Revisar folds OOS/WF/CPCV en el laboratorio",
          "Reanalizar con Coach y Guardar Finalistas",
          "Contrastar con las otras 2★–5★ del coach si el régimen cambió",
        ]
      : [
          "No adoptar aún",
          "Volver al coach y optimizar la #2 por estrellas futuras",
          "Acotar el espacio de parámetros o subir validación OOS",
        ],
    engineLabel: "local",
  };
}

export type LlmOptimizeComparePayload = {
  headline?: string;
  summary?: string[];
  detailed?: string[];
  nextSteps?: string[];
};

export function mergeOptimizeCompareAi(
  local: OptimizeCompareAiNote,
  llm: LlmOptimizeComparePayload | null | undefined,
  engineLabel: string,
): OptimizeCompareAiNote {
  if (!llm) return { ...local, engineLabel };
  return {
    headline: llm.headline?.trim() || local.headline,
    summary:
      Array.isArray(llm.summary) && llm.summary.length > 0
        ? llm.summary
        : local.summary,
    detailed:
      Array.isArray(llm.detailed) && llm.detailed.length > 0
        ? llm.detailed
        : local.detailed,
    nextSteps:
      Array.isArray(llm.nextSteps) && llm.nextSteps.length > 0
        ? llm.nextSteps
        : local.nextSteps,
    engineLabel,
  };
}

export function optimizeComparePromptBlob(
  snap: OptimizeBeforeAfterSnapshot,
): string {
  return [
    `strategy=${snap.strategyLabel} (${snap.strategyType})`,
    `symbol=${snap.symbol ?? "n/a"}`,
    `before: ${JSON.stringify(snap.before)}`,
    `after: ${JSON.stringify(snap.after)}`,
    `deltaReturn=${snap.deltaReturnPct.toFixed(2)} deltaDD=${snap.deltaDrawdownPct.toFixed(2)} deltaScore=${snap.deltaScore.toFixed(2)}`,
    `improved=${snap.improved}`,
    `engine=${snap.engine ?? "n/a"}`,
  ].join("\n");
}
