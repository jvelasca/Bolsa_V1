/**
 * Cobertura Estudio — KPI frescos / N en Hoy Resumen.
 * V1.24 — empty ≠ unavailable (no «0 · Añade valores» cuando la API falla).
 *
 * @see docs/engineering/traspaso-relevo-hoy-cobertura-estudio-propuesta-2026-08-27.md
 */

import { cn } from "@/lib/utils";

export type EstudioUniverseStatusV1 = "ok" | "empty" | "unavailable";

type MesaCoberturaKpiProps = {
  frescos: number;
  universeCount: number;
  /** ok = membresía resuelta; empty = 0 ids; unavailable = no se pudo consultar. */
  estudioStatus?: EstudioUniverseStatusV1;
  className?: string;
};

export function MesaCoberturaKpi({
  frescos,
  universeCount,
  estudioStatus = "ok",
  className,
}: MesaCoberturaKpiProps) {
  if (estudioStatus === "unavailable") {
    return (
      <div
        className={cn(
          "rounded-md border border-rose-500/40 bg-rose-500/10 px-4 py-3",
          className,
        )}
        data-testid="mesa-cobertura-kpi"
        data-estudio-status="unavailable"
      >
        <p className="text-[10px] font-semibold uppercase tracking-wide text-rose-800 dark:text-rose-200">
          Estudio
        </p>
        <p className="mt-1 text-base font-semibold tracking-tight text-rose-950 dark:text-rose-50">
          No disponible
        </p>
        <p className="mt-1 text-xs text-rose-900/80 dark:text-rose-100/80">
          No se pudo consultar el universo supervisado. No se puede calcular la
          operativa diaria. Revisa la conexión o la lista Estudio.
        </p>
      </div>
    );
  }

  const n = Math.max(0, universeCount);
  const fresh = Math.max(0, Math.min(frescos, n || frescos));
  const missing = Math.max(0, n - fresh);
  const pct = n > 0 ? Math.round((fresh / n) * 100) : null;
  const empty = estudioStatus === "empty" || n === 0;

  return (
    <div
      className={cn(
        "rounded-md border border-border/60 bg-muted/15 px-4 py-3",
        empty && "border-amber-500/40 bg-amber-500/5",
        className,
      )}
      data-testid="mesa-cobertura-kpi"
      data-frescos={fresh}
      data-universe={n}
      data-estudio-status={empty ? "empty" : "ok"}
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
        {empty ? (
          <>
            Universo vacío. No hay candidatos en Estudio — añade valores en
            Mercado.
          </>
        ) : (
          <>
            Con Decision Study reciente (≤7d). Membresía Estudio ≠ Journal ≠
            WATCH.
            {missing > 0 ? ` · ${missing} sin propose reciente.` : null}
          </>
        )}
      </p>
    </div>
  );
}
