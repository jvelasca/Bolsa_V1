/**
 * Asesor → Diario · resumen de canales y opiniones del día — slice A3.
 *
 * «Canales Estudio» con Alarmas/Avisos y la lista corta de dictámenes del día.
 * Movido TAL CUAL desde `asesor-daily-ops-panel.tsx` (mismo marcado, mismos textos
 * y el mismo `data-testid="asesor-daily-ops-see-all"`).
 */

import { Link } from "react-router-dom";
import type { DailyOpsReportV1 } from "@bolsa/shared";
import { OPINION_CHANNEL_LEVEL_LABELS } from "@bolsa/shared";
import { absentDataLabel } from "@/components/absent-data";
import { cn } from "@/lib/utils";
import { AsesorDictamenCell } from "@/features/research/asesor-dictamen-cell";
import {
  asDeclaredList,
  asDeclaredNumber,
} from "@/features/research/asesor-daily-ops-guards";
import { ASESOR_CHANNEL_TONE } from "@/features/research/asesor-ui";

export function AsesorDailyChannels({ report }: { report: DailyOpsReportV1 }) {
  // Payload parcial (H-22): canales y opiniones se declaran si no llegan.
  const alarma = asDeclaredNumber(report.channels?.alarma);
  const aviso = asDeclaredNumber(report.channels?.aviso);
  const opinions = asDeclaredList<DailyOpsReportV1["opinions"][number]>(
    report.opinions,
  );
  const actionable = opinions
    ? opinions.filter((o) => o.channel === "alarma" || o.channel === "aviso")
    : null;

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-foreground">Canales Estudio</h3>
      <div className="grid grid-cols-2 gap-2">
        <div
          className={cn(
            "rounded-lg border p-3",
            ASESOR_CHANNEL_TONE.alarma.card,
          )}
        >
          <p
            className={cn(
              "text-[10px] uppercase",
              ASESOR_CHANNEL_TONE.alarma.label,
            )}
          >
            Alarmas
          </p>
          <p
            className={cn(
              "text-2xl font-semibold tabular-nums",
              ASESOR_CHANNEL_TONE.alarma.value,
            )}
          >
            {alarma ?? absentDataLabel()}
          </p>
        </div>
        <div
          className={cn(
            "rounded-lg border p-3",
            ASESOR_CHANNEL_TONE.aviso.card,
          )}
        >
          <p
            className={cn(
              "text-[10px] uppercase",
              ASESOR_CHANNEL_TONE.aviso.label,
            )}
          >
            Avisos
          </p>
          <p
            className={cn(
              "text-2xl font-semibold tabular-nums",
              ASESOR_CHANNEL_TONE.aviso.value,
            )}
          >
            {aviso ?? absentDataLabel()}
          </p>
        </div>
      </div>
      {!actionable ? (
        <p className="text-xs text-muted-foreground">
          {absentDataLabel()} · el parte del día no trajo las opiniones.
        </p>
      ) : actionable.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Sin dictámenes para el Estudio en esta fecha. Genera en Opiniones o
          EOD force.
        </p>
      ) : (
        <>
          <ul className="max-h-40 space-y-1 overflow-y-auto text-[11px]">
            {actionable.slice(0, 12).map((o) => (
              <li
                key={o.instrumentId}
                className="border-b border-border/40 py-1"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={cn(
                      "rounded px-1 text-[9px] uppercase",
                      o.channel === "alarma"
                        ? ASESOR_CHANNEL_TONE.alarma.badge
                        : ASESOR_CHANNEL_TONE.aviso.badge,
                    )}
                  >
                    {OPINION_CHANNEL_LEVEL_LABELS[o.channel] ??
                      absentDataLabel()}
                  </span>
                  <span>{o.symbol ?? o.instrumentId.slice(0, 8)}</span>
                </div>
                {/*
                    La fila del parte diario no es `InstrumentDailyOpinionV1`:
                    trae postura, motivos y ★, pero no IO ni alerta fundamental.
                    Si el reporte incluye `opinionDetails` (tipocompatible), se
                    usa el dictamen completo; si no, se pasa una entrada mínima
                    tipada y el bloque declara la ausencia de IO (Confianza/★
                    «Sin medir») sin inventarla.
                  */}
                <AsesorDictamenCell
                  opinion={
                    report.opinionDetails?.find(
                      (detail) => detail.instrumentId === o.instrumentId,
                    ) ?? {
                      stance: o.stance,
                      reasons: o.reasons,
                      dictamenStars: o.dictamenStars,
                    }
                  }
                  emptyLabel="Sin dictamen"
                  className="mt-0.5"
                />
              </li>
            ))}
          </ul>
          <Link
            to="/research?tab=opiniones"
            className="text-[10px] text-muted-foreground underline-offset-2 hover:underline"
            data-testid="asesor-daily-ops-see-all"
          >
            Ver todos en Análisis
            {actionable.length > 12 ? " (lista recortada aquí)" : ""}
          </Link>
        </>
      )}
    </section>
  );
}
