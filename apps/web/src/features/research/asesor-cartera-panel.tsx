/**
 * S3 · Cartera del Asesor — lista que reúne recomendación, tendencia, fuerza,
 * soportes/resistencias y momento, sin combinarlos.
 *
 * Regla dura: la ÚNICA recomendación es la del dictamen (`marketStanceLabel`).
 * Tendencia, fuerza, niveles y momento son contexto independiente: se muestran
 * en columnas distintas y no se ordenan ni se ponderan por coincidencia. La
 * columna «Estado» es una categoría de presentación, no una señal de compra.
 *
 * No hay CTA de compra: esta pestaña explica. Firmar vive en Confirm y operar en
 * Mercado.
 *
 * «Midmeas» y «ausente» son estados distintos: mientras una fuente carga, la
 * celda dice «Midiendo…», no «Sin dato». Un hueco medido se declara con su
 * causa y nunca se colapsa a 0.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 * @see docs/engineering/diseno-asesor-backend-ui-2026-11-12.md
 */

import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ASESOR_CARTERA_STATES,
  DEFAULT_ASESOR_CARTERA_FILTER,
  ESTUDIO_LIST_ID,
  MERCADO_COCKPIT_PHASE_LABEL,
  filterAsesorCarteraRows,
  formatConfidence,
  sortAsesorCarteraRows,
  type AsesorCarteraFilterV1,
  type AsesorCarteraRowV1,
  type AsesorCarteraStateIdV1,
} from "@bolsa/shared";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { TechnicalDetail } from "@/components/technical-detail";
import { formatNumberWith } from "@/lib/format";
import { MERCADO_PATH } from "@/features/confirm/daily-nav";
import { focusInstrumentInMercado } from "@/features/trading/focus-instrument-in-mercado";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { cn } from "@/lib/utils";
import { useAsesorCarteraData } from "@/features/research/use-asesor-cartera-data";

const STATE_BADGE: Record<AsesorCarteraStateIdV1, string> = {
  recomendacion_favorable:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
  evaluado_sin_oportunidad: "border-border bg-muted/40 text-muted-foreground",
  posicion_abierta:
    "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200",
  posicion_sin_respaldo:
    "border-amber-500/50 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  sin_datos: "border-border bg-muted/20 text-muted-foreground",
};

const TREND_TONE: Record<string, string> = {
  bullish: "text-emerald-700 dark:text-emerald-300",
  bearish: "text-rose-700 dark:text-rose-300",
  neutral: "text-muted-foreground",
  unknown: "text-muted-foreground",
};

const DIRECTION_LABEL: Record<string, string> = {
  long: "Largo",
  short: "Corto",
};

function changeTone(value: number | null): string {
  if (value == null) return "text-muted-foreground";
  if (value < 0) return "text-rose-700 dark:text-rose-300";
  if (value > 0) return "text-emerald-700 dark:text-emerald-300";
  return "text-muted-foreground";
}

function pnlTone(value: number | null): string {
  if (value == null) return "text-muted-foreground";
  return value < 0 ? "text-rose-700 dark:text-rose-300" : "text-emerald-700 dark:text-emerald-300";
}

function StrengthBar({
  value,
  label,
}: {
  value: number | null;
  label: string;
}) {
  if (value == null) return null;
  const clamped = Math.max(0, Math.min(10, value));
  return (
    <div
      className="mt-1 h-1.5 w-16 overflow-hidden rounded-full bg-muted"
      role="img"
      aria-label={label}
    >
      <div
        className="h-full rounded-full bg-sky-600 dark:bg-sky-400"
        style={{ width: `${clamped * 10}%` }}
      />
    </div>
  );
}

export function AsesorCarteraPanel({ className }: { className?: string }) {
  const data = useAsesorCarteraData();
  const [filter, setFilter] = useState<AsesorCarteraFilterV1>(
    DEFAULT_ASESOR_CARTERA_FILTER,
  );
  const navigate = useNavigate();
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const focusInstrumentFromList = useWorkspaceStore(
    (s) => s.focusInstrumentFromList,
  );

  const rows = useMemo(
    () => sortAsesorCarteraRows(filterAsesorCarteraRows(data.rows, filter)),
    [data.rows, filter],
  );

  const countByState = data.summary.byState;

  const staleCount = useMemo(
    () => data.rows.filter((row) => row.quote.stale).length,
    [data.rows],
  );

  return (
    <div className={cn("space-y-4", className)} data-testid="asesor-cartera">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Cartera del Asesor</CardTitle>
          <CardDescription>
            Universo en Estudio y posiciones de la cuenta activa. Cada columna
            mide una cosa distinta; la lista no combina señales ni autoriza
            compras. La recomendación es la del dictamen.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.empty ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                No hay valores en Estudio ni posiciones abiertas. Añade valores
                en Mercado (Listas → Pasar a Estudio).
              </p>
              <Link
                to={MERCADO_PATH}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                Ir a Mercado
              </Link>
            </div>
          ) : (
            <>
              <p
                className="text-xs text-muted-foreground"
                data-testid="asesor-cartera-totals"
              >
                {data.summary.total} valores ·{" "}
                {data.summary.withPosition} con posición ·{" "}
                {data.summary.unmeasured} sin medir ·{" "}
                {data.summary.withGaps} con huecos declarados
                {data.loading ? " · midiendo…" : ""}
              </p>

              {staleCount > 0 ? (
                <p
                  className="text-xs text-amber-700 dark:text-amber-300"
                  data-testid="asesor-cartera-stale"
                >
                  {staleCount} valor{staleCount === 1 ? "" : "es"} con el cierre
                  desactualizado: el precio y los niveles son de una sesión
                  anterior.
                </p>
              ) : null}

              {data.portfolioError ? (
                <p className="text-xs text-destructive">
                  No se pudo leer la cartera: las filas quedan como «Cartera sin
                  medir». No se afirma que no haya posición.
                </p>
              ) : null}
              {data.studiesError ? (
                <p className="text-xs text-destructive">
                  No se pudo leer el parte diario: tendencia y fuerza se
                  declaran ausentes.
                </p>
              ) : null}
              {data.studiesTruncated ? (
                <p
                  className="text-xs text-muted-foreground"
                  data-testid="asesor-cartera-studies-truncated"
                >
                  El listado del parte diario vino recortado: un valor puede
                  tener plan fuera de la página. No se afirma «sin plan» sobre
                  datos recortados.
                </p>
              ) : null}
              {data.quotesError ? (
                <p className="text-xs text-muted-foreground">
                  Sin cotizaciones en lote: el precio se declara ausente.
                </p>
              ) : null}
              {data.barsFailedIds.length > 0 ? (
                <p
                  className="text-xs text-muted-foreground"
                  data-testid="asesor-cartera-bars-failed"
                >
                  Sin velas para {data.barsFailedIds.length} valor
                  {data.barsFailedIds.length === 1 ? "" : "es"}: sus soportes y
                  resistencias quedan como hueco, no como cero.
                </p>
              ) : null}

              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  aria-pressed={filter.state === "todos"}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                    filter.state === "todos"
                      ? "border-primary/50 bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:bg-accent",
                  )}
                  onClick={() =>
                    setFilter((current) => ({ ...current, state: "todos" }))
                  }
                >
                  Todos ({data.summary.total})
                </button>
                {ASESOR_CARTERA_STATES.map((state) => {
                  const count = countByState[state.id] || 0;
                  return (
                    <button
                      key={state.id}
                      type="button"
                      aria-pressed={filter.state === state.id}
                      title={state.meaning}
                      data-testid={`asesor-cartera-filter-${state.id}`}
                      className={cn(
                        "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                        filter.state === state.id
                          ? "border-primary/50 bg-primary/10 text-primary"
                          : "border-border text-muted-foreground hover:bg-accent",
                      )}
                      onClick={() =>
                        setFilter((current) => ({
                          ...current,
                          state: state.id,
                        }))
                      }
                    >
                      {state.label} ({count})
                    </button>
                  );
                })}
                <label className="ml-1 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={filter.onlyWithPosition}
                    onChange={(event) =>
                      setFilter((current) => ({
                        ...current,
                        onlyWithPosition: event.target.checked,
                      }))
                    }
                    data-testid="asesor-cartera-only-position"
                  />
                  Solo con posición
                </label>
              </div>

              {rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Ningún valor en este filtro.
                </p>
              ) : (
                <div className="max-h-[42rem] overflow-auto rounded-md border border-border">
                  <table className="w-full min-w-[72rem] text-left text-xs">
                    <caption className="sr-only">
                      Cartera del Asesor: recomendación del dictamen, tendencia,
                      fuerza, soportes y resistencias, momento y posición. Las
                      columnas no se combinan entre sí.
                    </caption>
                    <thead className="sticky top-0 z-10 bg-muted text-muted-foreground shadow-sm">
                      <tr>
                        <th
                          scope="col"
                          className="sticky left-0 z-20 bg-muted px-2 py-2 font-medium"
                        >
                          Valor
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Precio / Día
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Recomendación
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Tendencia
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Fuerza
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Soportes / Resistencias
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Momento
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Posición
                        </th>
                        <th scope="col" className="px-2 py-2 font-medium">
                          Estado
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <CarteraRow
                          key={row.instrumentId}
                          row={row}
                          loading={{
                            quotes: data.quotesLoading,
                            bars: data.barsLoading,
                            opinions: data.opinionsLoading,
                          }}
                          onOpenInMercado={() =>
                            focusInstrumentInMercado(
                              navigate,
                              { openChartTab, focusInstrumentFromList },
                              {
                                instrumentId: row.instrumentId,
                                symbol: row.symbol,
                              },
                              { listId: ESTUDIO_LIST_ID },
                            )
                          }
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <p className="text-[10px] text-muted-foreground">
                La recomendación es la del dictamen del día. Tendencia, fuerza,
                soportes/resistencias y momento informan; no se combinan, no
                autorizan una compra y no sustituyen a la firma en Confirm.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

type RowLoadingV1 = {
  quotes: boolean;
  bars: boolean;
  opinions: boolean;
};

function CarteraRow({
  row,
  loading,
  onOpenInMercado,
}: {
  row: AsesorCarteraRowV1;
  loading: RowLoadingV1;
  onOpenInMercado: () => void;
}) {
  const definition =
    ASESOR_CARTERA_STATES.find((state) => state.id === row.state.id) ?? null;
  const stateTitle = [definition?.meaning, ...row.gaps]
    .filter(Boolean)
    .join(" · ");
  const recommendationTitle = row.recommendation.reasonsTooltip
    ? `${row.recommendation.label} · ${row.recommendation.reasonsTooltip}`
    : row.recommendation.label;

  return (
    <tr
      className="border-t border-border/70 align-top"
      data-testid="asesor-cartera-row"
      data-state={row.state.id}
      data-symbol={row.symbol}
    >
      <td className="sticky left-0 z-10 bg-card px-2 py-2">
        <button
          type="button"
          className="font-medium text-foreground hover:underline"
          title="Ver en Mercado"
          onClick={onOpenInMercado}
          data-testid={`asesor-cartera-open-${row.symbol}`}
        >
          {row.symbol}
        </button>
        <p className="max-w-[10rem] truncate text-[10px] text-muted-foreground">
          {row.name}
        </p>
      </td>

      <td className="px-2 py-2 tabular-nums">
        <p className="font-medium">
          {row.quote.measured
            ? row.quote.label
            : loading.quotes
              ? "Midiendo cotizaciones…"
              : "Sin precio"}
        </p>
        {row.quote.measured ? (
          <p className={cn("text-[10px]", changeTone(row.quote.changePct))}>
            {row.quote.changeLabel}
          </p>
        ) : null}
        {row.quote.lastBarDate ? (
          <p
            className={cn(
              "text-[10px]",
              row.quote.stale
                ? "text-amber-700 dark:text-amber-300"
                : "text-muted-foreground",
            )}
            title={
              row.quote.stale
                ? `Se esperaba el cierre de ${row.quote.expectedLastBarDate ?? "la sesión en curso"}`
                : undefined
            }
          >
            {row.quote.stale ? "Cierre desactualizado" : "Cierre"}{" "}
            {row.quote.lastBarDate}
          </p>
        ) : null}
        {row.quote.source === "cartera" ? (
          <p
            className="text-[10px] text-muted-foreground"
            data-testid={`asesor-cartera-price-source-${row.symbol}`}
          >
            {loading.quotes
              ? "Precio de cartera · Midiendo cierre…"
              : "Precio de cartera · sin cierre de mercado"}
          </p>
        ) : null}
        {row.quote.source === "mercado" && !row.quote.lastBarDate ? (
          <p
            className="text-[10px] text-muted-foreground"
            data-testid={`asesor-cartera-price-source-${row.symbol}`}
          >
            Cotización sin fecha declarada
          </p>
        ) : null}
      </td>

      <td
        className="px-2 py-2"
        data-testid={`asesor-cartera-recommendation-${row.symbol}`}
      >
        <p className="font-medium" title={recommendationTitle}>
          {row.recommendation.measured
            ? row.recommendation.label
            : loading.opinions
              ? "Midiendo…"
              : row.recommendation.label}
        </p>
        {row.recommendation.measured || !loading.opinions ? (
          <p className="text-[10px] text-muted-foreground">
            {row.recommendation.measured
              ? row.recommendation.confidenceLabel
              : "Sin dictamen"}
          </p>
        ) : null}
        {row.recommendation.measured ? (
          <p
            className="text-[10px] tabular-nums text-muted-foreground"
            title="Valoración del dictamen (★)"
          >
            {row.recommendation.starsLabel}
          </p>
        ) : null}
        {row.recommendation.distress ? (
          <p
            className="mt-0.5 inline-block rounded border border-amber-500/40 bg-amber-500/10 px-1 text-[10px] text-amber-900 dark:text-amber-100"
            data-testid={`asesor-cartera-distress-${row.symbol}`}
            title="El fundamental de este valor está en dificultades; el dictamen no sube de ★3."
          >
            Fundamental en riesgo
          </p>
        ) : null}
        {row.recommendation.gateStatus === "VETO" ? (
          <p className="mt-0.5 inline-block rounded border border-rose-500/40 bg-rose-500/10 px-1 text-[10px] text-rose-800 dark:text-rose-200">
            Veto del motor
          </p>
        ) : row.recommendation.gateStatus === "WARNING" ? (
          <p className="mt-0.5 inline-block rounded border border-amber-500/40 bg-amber-500/10 px-1 text-[10px] text-amber-900 dark:text-amber-100">
            Aviso del motor
          </p>
        ) : null}
        {row.recommendation.reasons[0] ? (
          <p
            className="max-w-[12rem] truncate text-[10px] text-muted-foreground"
            title={recommendationTitle}
          >
            {row.recommendation.reasons[0]}
          </p>
        ) : null}
      </td>

      <td
        className="px-2 py-2"
        data-testid={`asesor-cartera-trend-${row.symbol}`}
      >
        <p className={cn("font-medium", TREND_TONE[row.trend.tone] ?? "")}>
          {row.trend.measured
            ? `Corto: ${row.trend.shortTermLabel ?? row.trend.label}`
            : loading.opinions
              ? "Midiendo…"
              : row.trend.label}
        </p>
        {row.trend.backgroundLabel ? (
          <p className="max-w-[11rem] truncate text-[10px] text-muted-foreground">
            Fondo: {row.trend.backgroundLabel}
          </p>
        ) : null}
        {row.trend.basis || row.trend.confirmation ? (
          <p className="max-w-[11rem] truncate text-[10px] text-muted-foreground">
            {[row.trend.basis, row.trend.confirmation]
              .filter(Boolean)
              .join(" · ")}
          </p>
        ) : null}
        {row.trend.vigenciaLabel ? (
          <p className="text-[10px] text-muted-foreground">
            {row.trend.vigenciaLabel}
          </p>
        ) : loading.opinions ? (
          <p className="text-[10px] text-muted-foreground">Midiendo…</p>
        ) : null}
      </td>

      <td className="px-2 py-2">
        <p className="tabular-nums">{row.strength.label}</p>
        <StrengthBar value={row.strength.value} label={row.strength.label} />
      </td>

      <td className="px-2 py-2 tabular-nums">
        <p title={row.levels.detail}>
          {row.levels.supportLabel}
          {row.levels.supportDistanceLabel ? (
            <span className="ml-1 text-[10px] text-muted-foreground">
              {row.levels.supportDistanceLabel}
            </span>
          ) : null}
        </p>
        <p title={row.levels.detail}>
          {row.levels.resistanceLabel}
          {row.levels.resistanceDistanceLabel ? (
            <span className="ml-1 text-[10px] text-muted-foreground">
              {row.levels.resistanceDistanceLabel}
            </span>
          ) : null}
        </p>
        {row.levels.structureLabel ? (
          <p className="text-[10px] text-muted-foreground">
            {row.levels.structureLabel}
          </p>
        ) : null}
        {!row.levels.measured ? (
          <p className="max-w-[12rem] text-[10px] text-muted-foreground">
            {loading.bars ? "Midiendo…" : row.levels.detail}
          </p>
        ) : null}
      </td>

      <td className="px-2 py-2">
        <p className="font-medium">{row.moment.phaseLabel}</p>
        {row.moment.kind === "posicion" ? (
          <p className="max-w-[13rem] text-[10px] text-muted-foreground tabular-nums">
            {row.moment.geometryLabel ?? "Sin geometría publicada"}
          </p>
        ) : row.moment.thermometer ? (
          <p
            className="max-w-[13rem] text-[10px] text-muted-foreground"
            title={row.moment.thermometer.detail ?? undefined}
          >
            {row.moment.thermometer.label}
          </p>
        ) : null}
        {row.moment.geometryLabel && row.moment.kind === "entrada" ? (
          <p className="max-w-[13rem] text-[10px] text-muted-foreground tabular-nums">
            {row.moment.geometryLabel}
          </p>
        ) : null}
      </td>

      <td className="px-2 py-2">
        <p
          className={cn(
            "font-medium",
            !row.position.measured
              ? "text-muted-foreground"
              : row.position.hasOpenPosition
                ? "text-foreground"
                : "text-muted-foreground",
          )}
        >
          {row.position.label}
        </p>
        {row.position.detail ? (
          <p
            className={cn(
              "max-w-[12rem] text-[10px] tabular-nums",
              pnlTone(row.position.unrealizedPnlPct),
            )}
          >
            {row.position.detail}
          </p>
        ) : null}
      </td>

      <td className="px-2 py-2">
        <span
          className={cn(
            "inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold",
            STATE_BADGE[row.state.id],
          )}
          data-testid={`asesor-cartera-state-${row.state.id}`}
          title={stateTitle || undefined}
        >
          {row.state.label}
        </span>
        <TechnicalDetail
          testId={`asesor-cartera-detalle-${row.symbol}`}
          className="mt-2 min-w-[16rem] text-[10px]"
        >
          <dl className="space-y-2">
            <div>
              <dt className="font-semibold uppercase text-muted-foreground">
                Dictamen
              </dt>
              <dd className="space-y-0.5">
                <p>{row.recommendation.label}</p>
                <p>
                  Cierre de referencia:{" "}
                  {row.recommendation.asOfBarDate ?? "sin fecha"}
                </p>
                <p>Origen: {row.recommendation.source ?? "sin declarar"}</p>
                <p>Confianza: {formatConfidence(row.recommendation.confidence)}</p>
                <p>
                  Valoración: {row.recommendation.starsLabel}
                  {row.recommendation.strategyStars != null
                    ? ` · estrategia ★${row.recommendation.strategyStars}`
                    : ""}
                </p>
                <p>
                  Componentes: IO{" "}
                  {row.recommendation.confidence == null
                    ? "sin medir"
                    : Math.round(row.recommendation.confidence)}{" "}
                  · FA{" "}
                  {row.recommendation.faScore == null
                    ? "sin medir"
                    : Math.round(row.recommendation.faScore)}{" "}
                  · TA{" "}
                  {row.recommendation.taScore == null
                    ? "sin medir"
                    : Math.round(row.recommendation.taScore)}
                </p>
                <p>
                  Veredicto del motor: {row.recommendation.gateStatus ?? "sin declarar"}
                  {row.recommendation.distress ? " · fundamental en riesgo" : ""}
                </p>
                <p>
                  Motor: {row.recommendation.engineVersion ?? "sin versión"} ·
                  calculado{" "}
                  {row.recommendation.computedAt ?? "sin fecha de cálculo"}
                </p>
                {row.recommendation.reasons.length > 0 ? (
                  <p>Motivos: {row.recommendation.reasons.join(" · ")}</p>
                ) : (
                  <p>Motivos: sin motivos visibles</p>
                )}
                {row.recommendation.hiddenReasonCount > 0 ? (
                  <p className="text-muted-foreground">
                    {row.recommendation.hiddenReasonCount} motivo(s)
                    diagnósticos ocultos en primer nivel.
                  </p>
                ) : null}
              </dd>
            </div>
            <div>
              <dt className="font-semibold uppercase text-muted-foreground">
                Parte diario
              </dt>
              <dd className="space-y-0.5">
                <p>{row.strength.label}</p>
                <p>Corto plazo: {row.trend.shortTermLabel ?? "sin dato"}</p>
                <p>Fondo: {row.trend.backgroundLabel ?? "sin dato"}</p>
                <p>Vigencia: {row.trend.vigenciaLabel ?? "sin parte"}</p>
                <p>Base de tendencia: {row.trend.basis ?? "sin indicador"}</p>
                <p>Confirmación: {row.trend.confirmation ?? "sin indicador"}</p>
                <p>
                  Consenso:{" "}
                  {row.studyDetail?.consensus
                    ? `${row.studyDetail.consensus.bullish} alcistas · ${row.studyDetail.consensus.bearish} bajistas · ${row.studyDetail.consensus.neutral} neutras`
                    : "sin medir"}
                </p>
                <p>
                  R/R esperado:{" "}
                  {row.studyDetail?.expectedRR == null
                    ? "sin medir"
                    : formatNumberWith(row.studyDetail.expectedRR, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{" "}
                  · riesgo{" "}
                  {row.studyDetail?.riskAmount == null
                    ? "sin medir"
                    : formatNumberWith(row.studyDetail.riskAmount, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                </p>
                <p>
                  Dirección:{" "}
                  {row.studyDetail?.direction
                    ? (DIRECTION_LABEL[row.studyDetail.direction] ??
                      row.studyDetail.direction)
                    : "sin plan"}
                  {row.studyDetail?.hasOperationalPlan
                    ? " · plan operativo publicado"
                    : " · sin plan operativo"}
                </p>
                <p>
                  Próxima revisión:{" "}
                  {row.studyDetail?.nextReviewAt ?? "sin fecha"}
                </p>
              </dd>
            </div>
            <div>
              <dt className="font-semibold uppercase text-muted-foreground">
                Estructura del gráfico
              </dt>
              <dd className="space-y-0.5">
                {row.structureProvenance ? (
                  <>
                    <p>
                      {row.structureProvenance.methodId} · v
                      {row.structureProvenance.methodVersion} ·{" "}
                      {row.structureProvenance.timeframe}
                    </p>
                    <p>
                      Ventana: {row.structureProvenance.bars} velas · ATR{" "}
                      {row.structureProvenance.atrRef == null
                        ? "sin medir"
                        : formatNumberWith(row.structureProvenance.atrRef, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                    </p>
                    <p>
                      Pivotes: {row.structureProvenance.supportPivots} soporte /
                      {" "}
                      {row.structureProvenance.resistancePivots} resistencia
                    </p>
                    <p className="break-all">
                      Firma: {row.structureProvenance.inputSignature}
                    </p>
                    <p>
                      Nivel calculado, no validado para comprar ni vender.
                    </p>
                  </>
                ) : (
                  <p>Sin medición de estructura para este valor.</p>
                )}
                <p>
                  Estructura: {row.levels.structureLabel ?? "sin estructura"}
                </p>
                <p className="tabular-nums">
                  Niveles: {row.levels.stateSummary.detectado} detectados ·{" "}
                  {row.levels.stateSummary.enPrecio} en precio ·{" "}
                  {row.levels.stateSummary.roto} rotos ·{" "}
                  {row.levels.stateSummary.noFiable} no fiables ·{" "}
                  {row.levels.stateSummary.noDisponible} no disponibles
                </p>
                <p>
                  {row.levels.supportLabel}
                  {row.levels.supportDistanceLabel
                    ? ` (${row.levels.supportDistanceLabel})`
                    : ""}{" "}
                  · {row.levels.resistanceLabel}
                  {row.levels.resistanceDistanceLabel
                    ? ` (${row.levels.resistanceDistanceLabel})`
                    : ""}
                </p>
                <p>
                  Cierre medido:{" "}
                  {row.levels.close == null
                    ? "sin medir"
                    : formatNumberWith(row.levels.close, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                  {row.levels.atrRef == null
                    ? ""
                    : ` · ATR ${formatNumberWith(row.levels.atrRef, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}`}
                </p>
                {row.levels.nearestStateLabel ? (
                  <p>
                    Sin nivel dibujable: el más cercano está{" "}
                    {row.levels.nearestStateLabel.toLowerCase()}.
                  </p>
                ) : null}
              </dd>
            </div>
            <div>
              <dt className="font-semibold uppercase text-muted-foreground">
                Momento
              </dt>
              <dd className="space-y-0.5">
                <p>Fase: {MERCADO_COCKPIT_PHASE_LABEL[row.moment.phase]}</p>
                <p>
                  {row.moment.kind === "posicion"
                    ? `Posición: ${row.moment.detail ?? "sin geometría"}`
                    : `Termómetro: ${row.moment.thermometer?.label ?? "sin entrada"}`}
                </p>
                <p>Geometría: {row.moment.geometryLabel ?? "sin geometría"}</p>
                <p>Entrada: {row.moment.entry == null ? "sin medir" : formatNumberWith(row.moment.entry, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                <p>Invalidación: {row.moment.invalidation == null ? "sin medir" : formatNumberWith(row.moment.invalidation, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                <p>Objetivo 1: {row.moment.target1 == null ? "sin medir" : formatNumberWith(row.moment.target1, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                <p>Objetivo 2: {row.moment.target2 == null ? "sin medir" : formatNumberWith(row.moment.target2, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                <p>Etiqueta de lectura: no es una orden.</p>
              </dd>
            </div>
            <div>
              <dt className="font-semibold uppercase text-muted-foreground">
                Invalidantes del parte
              </dt>
              <dd>
                {row.studyDetail?.invalidation.length
                  ? row.studyDetail.invalidation.join(" · ")
                  : "Sin invalidantes declarados"}
              </dd>
            </div>
            <div>
              <dt className="font-semibold uppercase text-muted-foreground">
                Huecos declarados
              </dt>
              <dd>
                {row.gaps.length > 0
                  ? row.gaps.join(" · ")
                  : "Ninguno: todo lo que falta está a la vista."}
              </dd>
            </div>
          </dl>
        </TechnicalDetail>
      </td>
    </tr>
  );
}
