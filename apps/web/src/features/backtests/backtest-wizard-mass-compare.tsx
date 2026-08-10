import {
  BACKTEST_STRATEGIES,
  type BacktestStrategyType,
  type ChartTimeframe,
  type InstrumentListDetailDto,
} from "@bolsa/shared";
import { BacktestMassComparePanel } from "@/features/backtests/backtest-mass-compare-panel";
import {
  resolveBacktestWindow,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";

const STRATEGY_OPTIONS = Object.entries(BACKTEST_STRATEGIES) as [
  BacktestStrategyType,
  { label: string; description: string },
][];

interface BacktestWizardMassCompareProps {
  listDetail: InstrumentListDetailDto | undefined;
  labels: Record<string, { symbol: string; name?: string }>;
  initialCash: string;
  commissionBps: string;
  slippageBps: string;
  timeframe: ChartTimeframe;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  diaD: string | null | undefined;
}

/** Wizard «Comparación masiva (Q3.3)» del hub de backtesting: lista ×
 * estrategias. Extraído de `backtests-page.tsx` (feature-slicing F4.8) sin
 * cambiar la semántica de hooks/handlers del padre. */
export function BacktestWizardMassCompare({
  listDetail,
  labels,
  initialCash,
  commissionBps,
  slippageBps,
  timeframe,
  periodPreset,
  customDateFrom,
  customDateTo,
  diaD,
}: BacktestWizardMassCompareProps) {
  return (
    <details className="rounded-md border border-border/60 bg-muted/10">
      <summary className="cursor-pointer list-none px-2.5 py-1.5 text-[11px] font-medium text-foreground/90 marker:content-none [&::-webkit-details-marker]:hidden">
        Comparación masiva (Q3.3) · N estrategias × N valores
      </summary>
      <div className="border-t border-border/50 px-2.5 py-2.5">
        {listDetail ? (
          <BacktestMassComparePanel
            instrumentIds={listDetail.instrumentIds}
            labels={labels}
            strategyOptions={STRATEGY_OPTIONS.slice(0, 10).map(
              ([key, meta]) => ({
                key,
                label: meta.label,
                strategyType: key,
              }),
            )}
            initialCash={Number(initialCash)}
            commissionBps={Number(commissionBps) || 0}
            slippageBps={Number(slippageBps) || 0}
            timeframe={timeframe}
            window={resolveBacktestWindow(
              periodPreset,
              customDateFrom,
              customDateTo,
              diaD,
            )}
          />
        ) : (
          <p className="text-[10px] text-muted-foreground">
            Elige una lista en Universo para comparar.
          </p>
        )}
      </div>
    </details>
  );
}
