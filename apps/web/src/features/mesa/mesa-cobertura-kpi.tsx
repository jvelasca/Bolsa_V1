/**
 * Cobertura Estudio — KPI frescos / N en Hoy Resumen.
 * No grid · no ?view=cobertura · Ranking ≠ BUY.
 *
 * @see docs/engineering/traspaso-relevo-hoy-cobertura-estudio-propuesta-2026-08-27.md
 */

import { cn } from "@/lib/utils";

type MesaCoberturaKpiProps = {
  frescos: number;
  universeCount: number;
  className?: string;
};

export function MesaCoberturaKpi({
  frescos,
  universeCount,
  className,
}: MesaCoberturaKpiProps) {
  const n = Math.max(0, universeCount);
  const fresh = Math.max(0, Math.min(frescos, n || frescos));
  const missing = Math.max(0, n - fresh);
  const pct = n > 0 ? Math.round((fresh / n) * 100) : null;

  return (
    <div
      className={cn(
        "rounded-md border border-border/60 bg-muted/15 px-4 py-3",
        className,
      )}
      data-testid="mesa-cobertura-kpi"
      data-frescos={fresh}
      data-universe={n}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Cobertura Estudio
      </p>
      <p className="mt-1 text-base font-semibold tabular-nums tracking-tight">
        {fresh}
        <span className="text-muted-foreground"> / {n}</span>
        <span className="ml-2 text-sm font-medium text-muted-foreground">
          frescos
          {pct != null ? ` · ${pct}%` : ""}
        </span>
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Con Decision Study reciente (≤7d). Membresía Estudio ≠ Journal ≠ WATCH.
        {missing > 0 ? ` · ${missing} sin propose reciente.` : null}
        {n === 0 ? " Añade valores a Estudio en Mercado." : null}
      </p>
    </div>
  );
}
