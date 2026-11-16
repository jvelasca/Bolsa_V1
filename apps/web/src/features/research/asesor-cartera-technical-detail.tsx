/**
 * Nivel 3 de una fila de Cartera — slice A3·b.
 *
 * El bloque `TechnicalDetail` de la fila vive aquí: dictamen completo, parte
 * diario, estructura del gráfico, momento, invalidantes y huecos declarados. Es
 * el ÚNICO sitio de la fila donde se admite la jerga de ingeniería (procedencia,
 * firmas, componentes); el primer nivel solo declara resultado y ausencia.
 *
 * Se extrajo del panel sin cambiar una coma del marcado.
 *
 * @see apps/web/src/components/technical-detail.tsx
 */

import {
  MERCADO_COCKPIT_PHASE_LABEL,
  formatConfidence,
  type AsesorCarteraRowV1,
} from "@bolsa/shared";
import { TechnicalDetail } from "@/components/technical-detail";
import { formatNumberWith } from "@/lib/format";

const DIRECTION_LABEL: Record<string, string> = {
  long: "Largo",
  short: "Corto",
};

export function AsesorCarteraTechnicalDetail({
  row,
}: {
  row: AsesorCarteraRowV1;
}) {
  return (
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
              Veredicto del motor:{" "}
              {row.recommendation.gateStatus ?? "sin declarar"}
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
                {row.recommendation.hiddenReasonCount} motivo(s) diagnósticos
                ocultos en primer nivel.
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
              Próxima revisión: {row.studyDetail?.nextReviewAt ?? "sin fecha"}
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
                  Pivotes: {row.structureProvenance.supportPivots} soporte /{" "}
                  {row.structureProvenance.resistancePivots} resistencia
                </p>
                <p className="break-all">
                  Firma: {row.structureProvenance.inputSignature}
                </p>
                <p>Nivel calculado, no validado para comprar ni vender.</p>
              </>
            ) : (
              <p>Sin medición de estructura para este valor.</p>
            )}
            <p>Estructura: {row.levels.structureLabel ?? "sin estructura"}</p>
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
            <p>
              Entrada:{" "}
              {row.moment.entry == null
                ? "sin medir"
                : formatNumberWith(row.moment.entry, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
            </p>
            <p>
              Invalidación:{" "}
              {row.moment.invalidation == null
                ? "sin medir"
                : formatNumberWith(row.moment.invalidation, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
            </p>
            <p>
              Objetivo 1:{" "}
              {row.moment.target1 == null
                ? "sin medir"
                : formatNumberWith(row.moment.target1, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
            </p>
            <p>
              Objetivo 2:{" "}
              {row.moment.target2 == null
                ? "sin medir"
                : formatNumberWith(row.moment.target2, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
            </p>
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
  );
}
