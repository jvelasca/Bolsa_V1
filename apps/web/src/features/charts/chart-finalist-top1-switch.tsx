/**
 * Switch Finalista TOP #1 — misma tipografía/altura que Indicadores y chips de barra.
 * Scope: «todos» (workspace) vs «este» (gráfico activo).
 */

import { cn } from "@/lib/utils";
import {
  CHART_BAR_ZONE_LABEL_BTN_CLASS,
  CHART_BAR_ZONE_ROW_CLASS,
} from "@/features/charts/chart-bar-zone-styles";

export type ChartFinalistTop1Scope = "chart" | "all";

type Props = {
  checked: boolean;
  disabled?: boolean;
  title?: string;
  /** `all` = política workspace (barra general); `chart` = solo este gráfico. */
  scope?: ChartFinalistTop1Scope;
  onCheckedChange: (next: boolean) => void;
  className?: string;
};

export function ChartFinalistTop1Switch({
  checked,
  disabled,
  title,
  scope = "chart",
  onCheckedChange,
  className,
}: Props) {
  const isAll = scope === "all";
  return (
    <div
      className={cn(CHART_BAR_ZONE_ROW_CLASS, "shrink-0", className)}
      title={
        title ??
        (isAll
          ? "Activar Finalista TOP #1 en todos los gráficos abiertos y en los que abras después. Cada gráfico se puede apagar solo."
          : "Mostrar en este gráfico los indicadores del Finalista TOP #1 (mismo timeframe)")
      }
      data-testid={
        isAll ? "chart-finalist-top1-all-switch" : "chart-finalist-top1-switch"
      }
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          CHART_BAR_ZONE_LABEL_BTN_CLASS,
          "inline-flex items-center gap-1.5 pr-1.5 disabled:cursor-not-allowed disabled:opacity-50",
          checked && "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
        )}
      >
        <span
          className={cn(
            "relative inline-flex h-3 w-5 shrink-0 items-center rounded-full border transition-colors",
            checked
              ? "border-emerald-500/80 bg-emerald-500/80"
              : "border-border bg-muted",
          )}
          aria-hidden
        >
          <span
            className={cn(
              "absolute h-2 w-2 rounded-full bg-background shadow transition-transform",
              checked ? "translate-x-2.5" : "translate-x-0.5",
            )}
          />
        </span>
        <span className="chart-indicators-label-text">Finalista #1</span>
        <span className="chart-indicators-label-short">Fin. #1</span>
        <span className="rounded-full bg-muted px-1.5 py-0 text-[10px] font-semibold tabular-nums text-muted-foreground">
          {isAll ? "todos" : "este"}
        </span>
      </button>
    </div>
  );
}

/** Cartel en el gráfico cuando el overlay TOP #1 está ON pero no hay specs. */
export function ChartFinalistTop1EmptyBanner({
  className,
}: {
  className?: string;
}) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute left-2 top-2 z-20 rounded border border-amber-500/40 bg-background/90 px-2 py-1 text-[11px] font-medium leading-none text-amber-800 shadow-sm dark:text-amber-300",
        className,
      )}
      role="status"
      data-testid="chart-finalist-top1-empty-banner"
    >
      No hay indicador finalista
    </div>
  );
}
