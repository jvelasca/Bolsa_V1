/**
 * Protección Cartera — KPI Confirmada / N en Hoy.
 * V1.31.2 — agregado sobre buildMesaProtectionState (≠ Cobertura Estudio).
 */

import { cn } from "@/lib/utils";
import type { MesaProtectionKpiV1 } from "@bolsa/shared";

type MesaProteccionKpiProps = {
  kpi: MesaProtectionKpiV1;
  className?: string;
  /** Compacto para strip / Libro. */
  compact?: boolean;
};

export function MesaProteccionKpi({
  kpi,
  className,
  compact = false,
}: MesaProteccionKpiProps) {
  const { protected: protectedCount, open, discrepancies, pct } = kpi;
  const empty = open === 0;
  const warn = discrepancies > 0;

  if (compact) {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/15 px-2.5 py-1 text-xs tabular-nums",
          warn && "border-amber-500/40 bg-amber-500/5",
          empty && "text-muted-foreground",
          className,
        )}
        data-testid="mesa-proteccion-kpi"
        data-compact=""
        data-protected={protectedCount}
        data-open={open}
        data-discrepancies={discrepancies}
      >
        <span className="font-semibold uppercase tracking-wide text-muted-foreground">
          Protección
        </span>
        <span className="font-medium">
          {protectedCount}
          <span className="text-muted-foreground"> / {open}</span>
          {pct != null ? (
            <span className="ml-1 text-muted-foreground">{pct}%</span>
          ) : null}
        </span>
        {warn ? (
          <span className="text-[10px] text-amber-800 dark:text-amber-200">
            {discrepancies} disc.
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border border-border/60 bg-muted/15 px-4 py-3",
        warn && "border-amber-500/40 bg-amber-500/5",
        empty && "border-border/40",
        className,
      )}
      data-testid="mesa-proteccion-kpi"
      data-protected={protectedCount}
      data-open={open}
      data-discrepancies={discrepancies}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Protección Cartera
      </p>
      <p className="mt-1 text-base font-semibold tabular-nums tracking-tight">
        {protectedCount}
        <span className="text-muted-foreground"> / {open}</span>
        <span className="ml-2 text-sm font-medium text-muted-foreground">
          confirmadas
          {pct != null ? ` · ${pct}%` : ""}
        </span>
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {empty ? (
          <>Sin posiciones abiertas — no hay stop que confirmar.</>
        ) : warn ? (
          <>
            {discrepancies} con discrepancia (plan/propuesta ≠ stop vigente).
            Revisa en Atención.
          </>
        ) : (
          <>Stop vigente Confirmado vía Confirm (PH-1). ≠ Cobertura Estudio.</>
        )}
      </p>
    </div>
  );
}
