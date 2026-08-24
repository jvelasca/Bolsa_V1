/**
 * Pestaña Pruebas anteriores — lista acotada + enlace Research.
 */

import { Link } from "react-router-dom";
import { BACKTEST_STRATEGIES, type BacktestRunDto } from "@bolsa/shared";
import {
  LEDGER_ASESOR_LINK_LABEL,
  asesorHistoryHref,
} from "@/features/confirm/daily-nav";
import { Button } from "@/components/ui/button";
import { formatPct } from "@/features/charts/chart-utils";
import { formatDateTimeWith } from "@/lib/format";
import { cn } from "@/lib/utils";

type Props = {
  runs: BacktestRunDto[];
  historyMaxKept: number;
  selectedId: string | null;
  onOpenSettings: () => void;
  onSelectRun: (runId: string) => void;
  onGoToRun: () => void;
};

export function BacktestHistoryTab({
  runs,
  historyMaxKept,
  selectedId,
  onOpenSettings,
  onSelectRun,
  onGoToRun,
}: Props) {
  return (
    <div className="mx-auto min-h-0 w-full max-w-[900px] flex-1 space-y-3 overflow-auto px-1">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">
            Pruebas anteriores
          </h3>
          <p className="text-sm text-muted-foreground">
            {runs.length} de hasta {historyMaxKept} en este dispositivo
            {runs.length > 0 ? " · clic abre en Probar" : ""}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-8"
            onClick={onOpenSettings}
            title="Configuración de zona (tope de historial)"
          >
            ⚙ Tope {historyMaxKept}
          </Button>
          <Link
            to={asesorHistoryHref()}
            className="text-xs font-medium text-primary hover:underline"
          >
            {LEDGER_ASESOR_LINK_LABEL}
          </Link>
        </div>
      </div>

      {runs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            Aún no hay backtests guardados. Lanza una prueba en Probar
            estrategia.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={onGoToRun}
          >
            Ir a Probar
          </Button>
        </div>
      ) : (
        <ul className="divide-y divide-border/60 rounded-lg border border-border/80">
          {runs.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                onClick={() => onSelectRun(run.id)}
                className={cn(
                  "flex w-full flex-wrap items-center justify-between gap-2 px-3 py-3 text-left text-sm transition-colors hover:bg-muted/30",
                  selectedId === run.id && "bg-primary/5",
                )}
              >
                <span className="min-w-0">
                  <span className="font-medium">{run.symbol}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    · {BACKTEST_STRATEGIES[run.strategyType].label}
                  </span>
                  {run.dataVersion && (
                    <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                      {run.dataVersion}
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-3 tabular-nums">
                  <span
                    className={cn(
                      "font-medium",
                      run.totalReturnPct >= 0
                        ? "text-success"
                        : "text-destructive",
                    )}
                  >
                    {formatPct(run.totalReturnPct)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDateTimeWith(run.createdAt, {
                      day: "2-digit",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
