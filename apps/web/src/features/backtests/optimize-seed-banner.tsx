import { X } from "lucide-react";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";
import type { OptimizeValidationHint } from "@/features/backtests/backtest-optimize-seed";
import { Button } from "@/components/ui/button";
import { formatPct } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

interface OptimizeSeedBannerProps {
  seed: OptimizeSeed;
  /** Heurístico del coach (P6): hold-out / WF / CPCV sugeridos. */
  validationHint: OptimizeValidationHint | null;
  /** Nota de proxy de familia (p. ej. regla sin buscador propio). */
  proxyNote: string | null;
  /** False si la familia de la semilla aún no tiene grid propio. */
  familyReady: boolean;
  onClearSeed?: () => void;
}

/**
 * Banner "Prueba origen" del panel de optimización (Diseño B). Muestra la semilla
 * (prueba origen ancla), sus métricas (retorno / caída máx / ops / barras), el hint
 * de validación del coach, la nota de proxy de familia y el botón de quitar semilla.
 * La lógica (derivación del hint y de familyReady) permanece en el orquestador.
 */
export function OptimizeSeedBanner({
  seed,
  validationHint,
  proxyNote,
  familyReady,
  onClearSeed,
}: OptimizeSeedBannerProps) {
  return (
    <div
      className={cn(
        "space-y-2 rounded-lg border px-3 py-2 text-sm",
        seed.beatBuyHold === false
          ? "border-amber-500/40 bg-amber-500/10"
          : "border-sky-500/40 bg-sky-500/10",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-foreground">
            Prueba origen · {seed.strategyLabel}
            {seed.symbol ? ` · ${seed.symbol}` : ""}
          </p>
          <p
            className="mt-1 text-xs text-muted-foreground"
            title="Esta es la prueba que hiciste antes. La optimización busca parámetros mejores y los compara con estos resultados (ancla)."
          >
            Partimos de tu prueba
            {seed.anchorReturnPct != null
              ? ` · retorno ${formatPct(seed.anchorReturnPct)}`
              : ""}
            {seed.anchorMaxDrawdownPct != null
              ? ` · caída máx. ${formatPct(seed.anchorMaxDrawdownPct)}`
              : ""}
            {seed.anchorTradeCount != null
              ? ` · ${seed.anchorTradeCount} ops`
              : ""}
            {seed.barLimit != null ? ` · ${seed.barLimit} barras` : ""}.
          </p>
          {validationHint && (
            <p
              className="mt-1.5 text-[11px] text-foreground/90"
              title="Prefill heurístico del coach (P6). Puedes cambiar hold-out / WF / CPCV abajo."
            >
              Validación: {validationHint.reason}
            </p>
          )}
          {proxyNote && (
            <p className="mt-1.5 text-[11px] leading-snug text-amber-800 dark:text-amber-300">
              {proxyNote}
            </p>
          )}
        </div>
        {onClearSeed && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            title="Quitar la prueba origen y empezar el laboratorio en blanco"
            aria-label="Quitar prueba origen"
            onClick={onClearSeed}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      {!familyReady && (
        <p className="text-xs text-muted-foreground">
          Esta regla aún no tiene buscador propio: se probará un grid SMA en el
          mismo valor.
        </p>
      )}
    </div>
  );
}
