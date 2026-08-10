import { FundamentalCardPanel } from "@/features/instruments/fundamental-card-panel";
import { effectiveDiaD, isDiaDInPast } from "@/features/backtests/backtest-period";

interface BacktestResultFundamentalProps {
  instrumentId: string;
  diaD: string | null | undefined;
}

/** Resultado «fundamental» de la pestaña de backtesting: tarjeta Valor del valor
 * seleccionado (o aviso si no hay ninguno). Se extrae de `backtests-page.tsx`
 * (feature-slicing F4.8) sin cambiar la semántica de hooks/handlers del padre. */
export function BacktestResultFundamental({
  instrumentId,
  diaD,
}: BacktestResultFundamentalProps) {
  if (!instrumentId) {
    return (
      <p className="text-sm text-muted-foreground">
        Elige un valor en Universo para ver la Tarjeta Valor (análisis
        fundamental).
      </p>
    );
  }
  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <FundamentalCardPanel
        instrumentId={instrumentId}
        asOf={isDiaDInPast(diaD) ? effectiveDiaD(diaD) : null}
      />
    </div>
  );
}
