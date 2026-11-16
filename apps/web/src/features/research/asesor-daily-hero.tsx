/**
 * Asesor → Diario · hero del día — slices A3 y A4.
 *
 * Encabezado del día con la cuenta, la fecha, el estado del Estudio y los KPI.
 * El slice A4 retira el gradiente hex, `text-white`, `bg-black/20` y `font-serif`:
 * todo pasa a tokens del sistema (`bg-card`, `text-foreground`,
 * `text-muted-foreground`, `border-border`), de modo que el hero se lee en tema
 * claro y oscuro. La jerarquía y los datos no cambian.
 *
 * La ausencia también se declara con el vocabulario de `@/components/absent-data`:
 * - sin cuenta activa → pide seleccionar cuenta;
 * - cuenta válida, informe cargando → «Midiendo…»;
 * - cuenta válida, sin informe → «Sin dato todavía» (no se culpa a la cuenta).
 *
 * Las cifras de primer nivel usan `formatPriceOrAbsent`: un hueco dice
 * «Sin dato todavía», nunca el guion de auditoría.
 */

import { Link } from "react-router-dom";
import type { DailyOpsReportV1 } from "@bolsa/shared";
import { formatPriceOrAbsent } from "@/features/charts/chart-utils";
import {
  ABSENT_DATA_NOT_MEASURED,
  absentDataLabel,
} from "@/components/absent-data";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ASESOR_CHANNEL_TONE, Kpi } from "@/features/research/asesor-ui";

type Props = {
  /** Nombre de la cuenta activa (`Cuenta DEMO` si aún no hay nombre). */
  accountName?: string;
  /** `true` si hay una cuenta activa efectiva (no basta con que exista la lista). */
  hasActiveAccount: boolean;
  asOf: string;
  /** Modo del libro demo (`loadDemoBookPrefs().mode`). */
  mode: string;
  /** Universo Estudio declarado (`report.estudioCount` o la membresía local). */
  estudioCount: number;
  report: DailyOpsReportV1 | undefined;
  isLoading: boolean;
};

export function AsesorDailyHero({
  accountName,
  hasActiveAccount,
  asOf,
  mode,
  estudioCount,
  report,
  isLoading,
}: Props) {
  const pnl = report?.summary?.totalUnrealizedPnl;
  const pnlTone = pnl == null ? "neutral" : pnl >= 0 ? "pos" : "neg";

  /** Los tres estados de ausencia, sin atribuir el hueco a la cuenta. */
  const absenceCopy = isLoading
    ? "Midiendo…"
    : hasActiveAccount
      ? `${ABSENT_DATA_NOT_MEASURED} · el resumen del día aún no está generado.`
      : "Selecciona una cuenta DEMO activa.";

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Explica el día · no firma
            </p>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {accountName ?? "Cuenta DEMO"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {asOf} · modo {mode.toUpperCase()} · Estudio {estudioCount}{" "}
              valores
            </p>
            {report?.estudioStatus === "unavailable" ? (
              <p
                className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-xs text-foreground"
                data-testid="asesor-estudio-unavailable"
              >
                Estudio no disponible — no se puede generar Daily Ops del
                universo. Esto no significa «0 oportunidades».
              </p>
            ) : null}
            {report?.estudioStatus === "empty" ? (
              <p
                className={cn(
                  "mt-2 rounded-md border px-2 py-1.5 text-xs",
                  ASESOR_CHANNEL_TONE.aviso.chip,
                )}
                data-testid="asesor-estudio-empty"
              >
                Estudio vacío — 0 valores en el universo supervisado.
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Link
              to="/trading"
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "h-7 text-[11px]",
              )}
            >
              Ver en Mercado
            </Link>
            <Link
              to="/research?tab=opiniones"
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "h-7 text-[11px]",
              )}
            >
              Opiniones
            </Link>
          </div>
        </div>
        {report ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Kpi
              label="Equity"
              value={formatPriceOrAbsent(report.summary?.totalEquity)}
            />
            <Kpi
              label="Cash"
              value={formatPriceOrAbsent(report.summary?.cash)}
            />
            <Kpi
              label="P&L latente"
              value={formatPriceOrAbsent(report.summary?.totalUnrealizedPnl)}
              tone={pnlTone}
            />
            <Kpi
              label="Posiciones"
              value={
                report.summary?.positionsCount != null
                  ? String(report.summary.positionsCount)
                  : absentDataLabel()
              }
            />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{absenceCopy}</p>
        )}
      </div>
    </section>
  );
}
