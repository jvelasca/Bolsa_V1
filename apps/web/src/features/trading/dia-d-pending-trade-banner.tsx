import type { BacktestTradeDto } from "@bolsa/shared";
import type { DiaDTradingMode } from "@/stores/dia-d-trading-session-store";
import { formatDateDdMmYyyy } from "@/features/backtests/backtest-date-format";
import { formatPrice } from "@/features/charts/chart-utils";
import { Button } from "@/components/ui/button";

interface Props {
  pendingTrade: BacktestTradeDto | null;
  /** Modo de la sesión DÍA D (Semi/Manual deciden el gate; Auto no propone). */
  mode: DiaDTradingMode;
  /** Aceptar la propuesta (orquestador: gate 'accept'). */
  onAccept: () => void;
  /** Rechazar la propuesta (orquestador: gate 'reject'). */
  onReject: () => void;
}

/** Banner de propuesta de trade pendiente del panel DÍA D (gate Semi/Manual).
 * Extraído de `trading-dia-d-replay-panel.tsx` (feature-slicing M5). Los
 * callbacks de decisión (`decideGate('accept'/'reject')`) se pasan como props
 * (Diseño B), de modo que la lógica del gate/estado del orquestador permanece
 * donde está. */
export function DiaDPendingTradeBanner({
  pendingTrade,
  mode,
  onAccept,
  onReject,
}: Props) {
  if (!pendingTrade) return null;
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px]">
      <span className="font-semibold text-amber-950 dark:text-amber-50">
        Propuesta {mode === 'manual' ? 'Manual' : 'Semi'}
      </span>
      <span className="tabular-nums">
        {pendingTrade.type.toUpperCase()} · {formatDateDdMmYyyy(pendingTrade.timestamp)} ·{' '}
        {formatPrice(pendingTrade.price)}
        {pendingTrade.reason ? ` · ${pendingTrade.reason}` : ''}
      </span>
      <Button type="button" size="sm" className="h-6 px-2 text-[10px]" onClick={onAccept}>
        Aceptar
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-6 px-2 text-[10px]"
        onClick={onReject}
      >
        Rechazar
      </Button>
    </div>
  );
}
