/**
 * Fila de Cartera del Asesor — slice A3·b.
 *
 * Una fila publica, en columnas separadas, la recomendación del dictamen y el
 * contexto (tendencia, fuerza, niveles, momento, posición, estado). Nada se
 * combina ni se pondera: la columna «Estado» es una categoría de presentación,
 * no una señal de compra.
 *
 * «Midiendo…» y «ausente» se distinguen en cada celda: mientras una fuente
 * carga no se afirma que falte el dato. El nivel 3 vive en
 * `AsesorCarteraTechnicalDetail`; el primer nivel no lleva jerga de ingeniería.
 *
 * El marcado y los `data-testid` por fila son los del panel original.
 */

import {
  ASESOR_CARTERA_STATES,
  type AsesorCarteraRowV1,
  type InstrumentDailyOpinionV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { AsesorDictamenCell } from "@/features/research/asesor-dictamen-cell";
import { AsesorCarteraTechnicalDetail } from "@/features/research/asesor-cartera-technical-detail";
import { AsesorStrengthBar } from "@/features/research/asesor-strength-bar";
import {
  ASESOR_TREND_TONE,
  AsesorStateBadge,
  toneForChange,
  toneForPnl,
} from "@/features/research/asesor-ui";

type RowLoadingV1 = {
  quotes: boolean;
  bars: boolean;
  opinions: boolean;
};

export function CarteraRow({
  row,
  opinion,
  loading,
  onOpenInMercado,
}: {
  row: AsesorCarteraRowV1;
  opinion: InstrumentDailyOpinionV1 | null;
  loading: RowLoadingV1;
  onOpenInMercado: () => void;
}) {
  const definition =
    ASESOR_CARTERA_STATES.find((state) => state.id === row.state.id) ?? null;
  const stateTitle = [definition?.meaning, ...row.gaps]
    .filter(Boolean)
    .join(" · ");

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
          <p className={cn("text-[10px]", toneForChange(row.quote.changePct))}>
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
        <AsesorDictamenCell
          opinion={opinion}
          loading={loading.opinions}
          emptyLabel="Sin dictamen"
        >
          {row.recommendation.distress ? (
            <span
              className="rounded border border-amber-500/40 bg-amber-500/10 px-1 text-[10px] text-amber-900 dark:text-amber-100"
              data-testid={`asesor-cartera-distress-${row.symbol}`}
              title="El fundamental de este valor está en dificultades; el dictamen no sube de ★3."
            >
              Fundamental en riesgo
            </span>
          ) : null}
          {row.recommendation.gateStatus === "VETO" ? (
            <span className="rounded border border-rose-500/40 bg-rose-500/10 px-1 text-[10px] text-rose-800 dark:text-rose-200">
              Veto del motor
            </span>
          ) : row.recommendation.gateStatus === "WARNING" ? (
            <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1 text-[10px] text-amber-900 dark:text-amber-100">
              Aviso del motor
            </span>
          ) : null}
        </AsesorDictamenCell>
      </td>

      <td
        className="px-2 py-2"
        data-testid={`asesor-cartera-trend-${row.symbol}`}
      >
        <p
          className={cn("font-medium", ASESOR_TREND_TONE[row.trend.tone] ?? "")}
        >
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
        <AsesorStrengthBar
          value={row.strength.value}
          label={row.strength.label}
        />
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
              toneForPnl(row.position.unrealizedPnlPct),
            )}
          >
            {row.position.detail}
          </p>
        ) : null}
      </td>

      <td className="px-2 py-2">
        <AsesorStateBadge
          stateId={row.state.id}
          label={row.state.label}
          title={stateTitle}
          testId={`asesor-cartera-state-${row.state.id}`}
        />
        <AsesorCarteraTechnicalDetail row={row} />
      </td>
    </tr>
  );
}
