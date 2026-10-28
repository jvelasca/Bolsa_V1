/**
 * Protección Cartera — KPI Protegido / N en Hoy.
 * V1.31.2 — agregado sobre buildMesaProtectionState (≠ Cobertura Estudio).
 * V2.29 — sin «propuesta thin» · Planificado ≠ Protegido.
 * P1-06 — si la cartera no se leyó, el KPI declara el hueco: `0` abiertas no es
 * un hecho medido y no autoriza «no hay stop que confirmar».
 */

import { cn } from "@/lib/utils";
import type { MesaProtectionKpiV1 } from "@bolsa/shared";
import {
  collectionAbsenceCopy,
  collectionAbsenceLabel,
  isCollectionAbsent,
  type CollectionReadState,
} from "@/components/query-absence";

type MesaProteccionKpiProps = {
  kpi: MesaProtectionKpiV1;
  className?: string;
  /** Compacto para strip / Libro. */
  compact?: boolean;
  /**
   * P1-06 — estado de lectura de la cartera. `error`/`loading`/`unavailable` no
   * permiten ningún recuento de posiciones ni de stops.
   */
  absenceState?: CollectionReadState;
};

export function MesaProteccionKpi({
  kpi,
  className,
  compact = false,
  absenceState,
}: MesaProteccionKpiProps) {
  const { protected: protectedCount, open, discrepancies, pct } = kpi;
  const absence =
    absenceState && isCollectionAbsent(absenceState) ? absenceState : null;
  const empty = !absence && open === 0;
  const warn = !absence && discrepancies > 0;
  const absenceLabel = absence ? collectionAbsenceLabel(absence) : null;

  if (compact) {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/15 px-2.5 py-1 text-xs tabular-nums",
          warn && "border-amber-500/40 bg-amber-500/5",
          (empty || absence) && "text-muted-foreground",
          className,
        )}
        data-testid="mesa-proteccion-kpi"
        data-compact=""
        data-protected={absence ? undefined : protectedCount}
        data-open={absence ? undefined : open}
        data-discrepancies={absence ? undefined : discrepancies}
        data-absence-state={absence ?? undefined}
      >
        <span className="font-semibold uppercase tracking-wide text-muted-foreground">
          Protección
        </span>
        {absence ? (
          <span data-testid="mesa-proteccion-absence">{absenceLabel}</span>
        ) : (
          <>
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
          </>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border border-border/60 bg-muted/15 px-4 py-3",
        warn && "border-amber-500/40 bg-amber-500/5",
        (empty || absence) && "border-border/40",
        className,
      )}
      data-testid="mesa-proteccion-kpi"
      data-protected={absence ? undefined : protectedCount}
      data-open={absence ? undefined : open}
      data-discrepancies={absence ? undefined : discrepancies}
      data-absence-state={absence ?? undefined}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Protección Cartera
      </p>
      <p className="mt-1 text-base font-semibold tabular-nums tracking-tight">
        {absence ? (
          <span
            className="text-muted-foreground"
            data-testid="mesa-proteccion-unavailable"
          >
            {absenceLabel}
          </span>
        ) : (
          <>
            {protectedCount}
            <span className="text-muted-foreground"> / {open}</span>
            <span className="ml-2 text-sm font-medium text-muted-foreground">
              protegidas
              {pct != null ? ` · ${pct}%` : ""}
            </span>
          </>
        )}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {absence === "error" ? (
          <>
            No disponible — no se pudo leer la cartera; no hay recuento de
            stops.
          </>
        ) : absence ? (
          collectionAbsenceCopy(absence, "la cartera")
        ) : empty ? (
          <>Sin posiciones abiertas — no hay stop que confirmar.</>
        ) : warn ? (
          <>
            {discrepancies} con plan/sugerido ≠ ejecución. Revisa en Atención.
          </>
        ) : (
          <>
            Stop en libro (Protegido) vía Confirm. Plan ≠ ejecución. ≠ Cobertura
            Estudio.
          </>
        )}
      </p>
    </div>
  );
}
