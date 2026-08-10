import type { ChartTimeframe, InstrumentStrategyTopV1 } from "@bolsa/shared";
import {
  InstrumentStrategyTopPanel,
  type FinalistSlotUse,
} from "@/features/backtests/instrument-strategy-top-panel";

interface BacktestResultFocusFinalistsProps {
  instrumentId: string;
  symbol: string;
  timeframe: ChartTimeframe;
  top: InstrumentStrategyTopV1 | null;
  asOfDiaD: string | null | undefined;
  activeProfileId: string | null | undefined;
  proposePendingStrategyId: string | null;
  onUseStrategy: (strategyId: string, slot?: FinalistSlotUse) => void;
  onOpenChecklist: (slot: FinalistSlotUse) => void;
  onProposeSupervised: (slot: FinalistSlotUse) => void;
  onGoToCoach: () => void;
}

/** Resultado «Finalistas» de la pestaña de backtesting: TOP del valor con
 * checklist/Proponer. Extraído de `backtests-page.tsx` (feature-slicing F4.8)
 * sin cambiar la semántica de hooks/handlers del padre. */
export function BacktestResultFocusFinalists({
  instrumentId,
  symbol,
  timeframe,
  top,
  asOfDiaD,
  activeProfileId,
  proposePendingStrategyId,
  onUseStrategy,
  onOpenChecklist,
  onProposeSupervised,
  onGoToCoach,
}: BacktestResultFocusFinalistsProps) {
  return (
    <div className="space-y-3 overflow-auto">
      {instrumentId ? (
        <InstrumentStrategyTopPanel
          instrumentId={instrumentId}
          symbol={symbol}
          timeframe={timeframe}
          top={top}
          asOfDiaD={asOfDiaD}
          activeProfileId={activeProfileId}
          onUseStrategy={onUseStrategy}
          onOpenChecklist={onOpenChecklist}
          onProposeSupervised={onProposeSupervised}
          proposePendingStrategyId={proposePendingStrategyId}
          onGoToCoach={onGoToCoach}
        />
      ) : (
        <div className="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Elige un valor</p>
          <p className="mt-1">
            Universo → Lista: clic en un miembro (IBEX, S&P…) para abrirlo en
            Valor. O elige un ticker en la pestaña Valor. Aquí verás Checklist y
            Proponer cuando haya TOP.
          </p>
        </div>
      )}
    </div>
  );
}
