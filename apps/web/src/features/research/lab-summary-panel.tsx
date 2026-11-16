/**
 * Asesor → Laboratorio · resumen corto — R5 (una sola puerta LAB).
 *
 * El Asesor explica «¿Por qué?» y delega la experimentación en `/backtests`. Este
 * panel declara el estado del laboratorio (cuántos experimentos, cuántas pruebas,
 * qué instrumentos y cuándo fue el último) y ofrece el CTA «Abrir el
 * Laboratorio» con deep-link que **conserva el instrumento**.
 *
 * Lo que ya NO vive aquí: la salud/cobertura de métricas y el historial de
 * experimentos con su detalle. Esas dos piezas se movieron a
 * `/backtests?tab=history` (`lab-research-section.tsx`) para que ningún dato del
 * LAB sea alcanzable solo desde el Asesor.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §6 (R5)
 */

import { Link } from "react-router-dom";
import type { LaboratoryResearchSummaryDto } from "@bolsa/shared";
import { formatPct } from "@/features/charts/chart-utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { TechnicalDetail } from "@/components/technical-detail";
import { absentDataLabel, formatOrAbsent } from "@/components/absent-data";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { formatNumberWith } from "@/lib/format";
import { UniverseChip } from "@/features/platform/universe-chip";
import { labHistoryHref } from "@/features/confirm/daily-nav";
import {
  formatShortDate,
  SectionTitle,
  Stat,
} from "@/features/research/asesor-ui";

/** Forma mínima de la consulta de resumen que consume el panel. */
type SummaryQueryState = {
  data?: { data?: LaboratoryResearchSummaryDto } | null;
  isLoading: boolean;
  isError: boolean;
};

/** Ratio con dos decimales localizados (es-ES), sin `toFixed`. */
function formatRatio2(value: number): string {
  return formatNumberWith(value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

type Props = {
  summaryQuery: SummaryQueryState;
  /** Instrumento activo en la URL: el deep-link lo conserva. */
  instrumentId?: string;
  className?: string;
};

export function LabSummaryPanel({
  summaryQuery,
  instrumentId = "",
  className,
}: Props) {
  // Payload defensivo (`UNKNOWN ≠ 0`): una respuesta incompleta se declara ausente,
  // nunca se renderiza como `undefined` ni rompe la pantalla.
  const summaryRaw = summaryQuery.data?.data;
  const summary =
    summaryRaw && typeof summaryRaw.totalTrials === "number"
      ? summaryRaw
      : null;
  const labHref = labHistoryHref(null, instrumentId);
  const openLabel = instrumentId
    ? "Abrir el Laboratorio de este valor"
    : "Abrir el Laboratorio";

  return (
    <div className={cn("space-y-4", className)}>
      {/* Primer nivel (`UI5-01`/`R-G2`): el Asesor explica «¿Por qué?», no experimenta. */}
      <Card data-testid="asesor-why-first-level">
        <CardHeader className="pb-2">
          <SectionTitle>
            ¿Por qué esta tesis, este riesgo, esta acción?
          </SectionTitle>
          <CardDescription>
            El Asesor explica; las pruebas viven en el Laboratorio.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <Link
            to="?tab=cartera"
            className="text-primary underline hover:underline"
          >
            Cartera
          </Link>
          <Link
            to="?tab=opiniones"
            className="text-primary underline hover:underline"
          >
            Análisis
          </Link>
          <Link
            to="/decision-journal"
            className="text-primary underline hover:underline"
          >
            Journal
          </Link>
          <Link
            to="?tab=diario"
            className="text-primary underline hover:underline"
          >
            Diario
          </Link>
          <Link to={labHref} className="text-primary underline hover:underline">
            Laboratorio (pruebas)
          </Link>
        </CardContent>
      </Card>

      <Card data-testid="asesor-lab-summary">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <SectionTitle>Laboratorio</SectionTitle>
              <CardDescription>
                Estado del laboratorio y último experimento. El detalle de cada
                prueba vive en el Laboratorio.
              </CardDescription>
            </div>
            <UniverseChip force="lab" />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {summaryQuery.isLoading && (
            <p className="text-sm text-muted-foreground">
              Cargando resumen del laboratorio…
            </p>
          )}
          {summaryQuery.isError && (
            <p className="text-sm text-destructive">
              No se pudo cargar el resumen del laboratorio. Revisa la API e
              inténtalo de nuevo.
            </p>
          )}
          {summary && summary.totalTrials === 0 && (
            <p className="text-sm text-muted-foreground">
              Aún no hay experimentos registrados. Lanza una prueba en el
              Laboratorio para empezar.
            </p>
          )}
          {summary && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Experimentos" value={String(summary.totalTrials)} />
              <Stat label="Pruebas aplicadas" value={String(summary.totalK)} />
              <Stat
                label="Instrumentos"
                value={String(summary.activeInstruments)}
              />
              <Stat
                label="Último experimento"
                value={
                  summary.lastTrialAt
                    ? formatShortDate(summary.lastTrialAt)
                    : absentDataLabel()
                }
              />
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Link
              to={labHref}
              className={cn(buttonVariants({ variant: "default", size: "sm" }))}
            >
              {openLabel}
            </Link>
            <Link
              to="/backtests?tab=run"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              Probar estrategia
            </Link>
          </div>

          {summary && (
            <TechnicalDetail testId="asesor-lab-metrics-technical">
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat
                  label="Calidad media"
                  value={formatOrAbsent(summary.avgSharpe, formatRatio2)}
                />
                <Stat
                  label="Factor de beneficio medio"
                  value={formatOrAbsent(summary.avgProfitFactor, formatRatio2)}
                />
                <Stat
                  label="Caída máxima media"
                  value={formatOrAbsent(summary.avgMaxDD, formatPct)}
                />
              </div>

              {summary.byInstrument.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-foreground">
                    Por instrumento
                  </p>
                  <ul className="mt-1 space-y-1 text-xs">
                    {summary.byInstrument.map((row) => (
                      <li key={row.instrumentId}>
                        <Link
                          to={labHistoryHref(null, row.instrumentId)}
                          className="text-primary hover:underline"
                        >
                          {row.symbol}
                        </Link>
                        <span className="ml-2 text-muted-foreground tabular-nums">
                          {row.trials} exp · {row.kConsumed} pruebas
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summary.byPreset.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-foreground">
                    Por configuración
                  </p>
                  <ul className="mt-1 space-y-1 text-xs">
                    {summary.byPreset.map((row) => (
                      <li key={row.presetKey}>
                        <Link
                          to={`${labHref}&presetKey=${encodeURIComponent(
                            row.presetKey === "unknown" ? "" : row.presetKey,
                          )}`}
                          className="text-primary hover:underline"
                        >
                          {row.presetKey}
                        </Link>
                        <span className="ml-2 text-muted-foreground tabular-nums">
                          {row.trials} exp
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </TechnicalDetail>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
