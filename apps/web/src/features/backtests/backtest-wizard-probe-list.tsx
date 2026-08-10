import {
  BACKTEST_STRATEGIES,
  type BacktestStrategyType,
  type InstrumentListDetailDto,
} from "@bolsa/shared";
import { LIST_AUTO_MAX_INSTRUMENTS } from "@/features/backtests/backtest-list-auto";
import { Button } from "@/components/ui/button";
import type { RunSource } from "@/features/backtests/backtest-hub-nav";
import type { PeriodPreset } from "@/features/backtests/backtest-period";

const STRATEGY_OPTIONS = Object.entries(BACKTEST_STRATEGIES) as [
  BacktestStrategyType,
  { label: string; description: string },
][];

interface ProbeStrategyItem {
  id: string;
  name: string;
  presetKey?: BacktestStrategyType | null;
}

interface BacktestWizardProbeListProps {
  runSource: RunSource;
  onRunSourceChange: (next: RunSource) => void;
  strategyType: BacktestStrategyType;
  onStrategyTypeChange: (next: BacktestStrategyType) => void;
  strategies: ReadonlyArray<ProbeStrategyItem>;
  savedStrategyId: string;
  onSavedStrategyIdChange: (next: string) => void;
  batchRunning: boolean;
  batchProgress: { done: number; total: number };
  onAbortBatch: () => void;
  onRunListBatch: () => void;
  exploreRunning: boolean;
  listAutoRunning: boolean;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  listId: string;
  listDetail: InstrumentListDetailDto | undefined;
}

/** «Probar lista (opcional) · 1 estrategia × N valores» del wizard en modo
 * lista. Ranking rápido Fase C sobre la watchlist. Extraído de `backtests-page.tsx`
 * (feature-slicing F4.8) sin cambiar la semántica de hooks/handlers del padre. */
export function BacktestWizardProbeList({
  runSource,
  onRunSourceChange,
  strategyType,
  onStrategyTypeChange,
  strategies,
  savedStrategyId,
  onSavedStrategyIdChange,
  batchRunning,
  batchProgress,
  onAbortBatch,
  onRunListBatch,
  exploreRunning,
  listAutoRunning,
  periodPreset,
  customDateFrom,
  customDateTo,
  listId,
  listDetail,
}: BacktestWizardProbeListProps) {
  const strategyMeta =
    runSource === "preset" && strategyType
      ? BACKTEST_STRATEGIES[strategyType]
      : null;
  return (
    <details className="rounded-md border border-border/60 bg-muted/10">
      <summary className="cursor-pointer list-none px-2.5 py-1.5 text-[11px] font-medium text-foreground/90 marker:content-none [&::-webkit-details-marker]:hidden">
        Probar lista (opcional) · 1 estrategia × N valores
      </summary>
      <div className="space-y-2 border-t border-border/50 px-2.5 py-2.5">
        <p className="text-[10px] leading-snug text-muted-foreground">
          Ranking rápido Fase C. No es el embudo Play / Lista AUTO.
        </p>
        <fieldset className="space-y-2">
          <legend
            className="text-[11px] font-medium"
            title="Genérica = catálogo. Optimizadas = Lab/clones. Mis estrategias = autoría (prompt/manual)."
          >
            Estrategia para «Probar lista»
          </legend>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="radio"
              checked={runSource === "preset"}
              onChange={() => onRunSourceChange("preset")}
            />
            Genérica
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="radio"
              checked={runSource === "saved"}
              onChange={() => onRunSourceChange("saved")}
              disabled={strategies.length === 0}
            />
            Mis estrategias / Optimizadas
          </label>
        </fieldset>

        {runSource === "preset" ? (
          <>
            <label className="block text-[11px] font-medium">
              Estrategia
              <select
                value={strategyType}
                onChange={(e) =>
                  onStrategyTypeChange(e.target.value as BacktestStrategyType)
                }
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              >
                {STRATEGY_OPTIONS.map(([key, meta]) => (
                  <option key={key} value={key}>
                    {meta.label}
                  </option>
                ))}
              </select>
            </label>
            {strategyMeta && (
              <p className="text-[11px] text-muted-foreground">
                {strategyMeta.description}
              </p>
            )}
          </>
        ) : (
          <label className="block text-[11px] font-medium">
            Estrategia (guardada)
            <select
              value={savedStrategyId}
              onChange={(e) => onSavedStrategyIdChange(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
            >
              <option value="">Selecciona…</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.presetKey
                    ? ` · ${BACKTEST_STRATEGIES[s.presetKey]?.label ?? s.presetKey}`
                    : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {batchRunning ? (
          <div className="flex gap-2">
            <Button className="flex-1" disabled>
              Probando lista… {batchProgress.done}/{batchProgress.total}
            </Button>
            <Button type="button" variant="outline" onClick={onAbortBatch}>
              Parar
            </Button>
          </div>
        ) : (
          <Button
            className="w-full"
            variant="outline"
            onClick={onRunListBatch}
            disabled={
              batchRunning ||
              exploreRunning ||
              listAutoRunning ||
              (runSource === "saved" && !savedStrategyId) ||
              (periodPreset === "custom" &&
                (!customDateFrom || !customDateTo)) ||
              !listId
            }
          >
            {`Probar lista${
              listDetail
                ? ` (${Math.min(
                    LIST_AUTO_MAX_INSTRUMENTS,
                    listDetail.instrumentIds.length,
                  )})`
                : ""
            }`}
          </Button>
        )}
      </div>
    </details>
  );
}
