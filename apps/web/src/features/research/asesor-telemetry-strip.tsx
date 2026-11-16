/**
 * Asesor → Análisis · tira de telemetría (A0 y A6) — slices A3 y A4.
 *
 * Movida TAL CUAL desde `asesor-opiniones-panel.tsx`: mismos textos, mismo orden,
 * mismos `data-testid`. El slice A4 la pliega tras el `TechnicalDetail` ÚNICO del
 * panel: A0, A6 y el diagnóstico de la tarjeta (`prec.5d`, `recall≈`, «Proxy
 * Outcomes», «P1–P5 en Consola», «Execute env», recuento de Estudio, silencios y
 * `asOf`) comparten un solo disclosure. Nada se elimina: se pliega.
 *
 * El primer nivel de la tarjeta se queda solo con los tres recuentos honestos
 * (alarmas, avisos, valores sin dictamen).
 *
 * Además vive aquí la `queryKey` de la telemetría A6 porque su `queryFn` consulta
 * con la cuenta efectiva: la cuenta DEBE formar parte de la clave para que el caché
 * no sirva la telemetría de la cuenta anterior al cambiar de cuenta.
 */

import { TechnicalDetail } from "@/components/technical-detail";
import { absentDataLabel } from "@/components/absent-data";

/** `testId` del disclosure único de la tira (A0 + A6 + diagnóstico). */
export const ASESOR_OPINIONS_TELEMETRY_TEST_ID =
  "asesor-opinion-telemetry-technical";

function pctLabel(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return absentDataLabel();
  return `${(v * 100).toFixed(0)}%`;
}

/** Ids ordenados de forma estable: el orden del Estudio no inventa otra entrada de caché. */
export function sortedStudyIds(studyIds: readonly string[]): string[] {
  return [...studyIds].sort();
}

/**
 * `queryKey` de la telemetría A6 (Estudio AUTO).
 *
 * Lleva la cuenta efectiva además de los ids: dos cuentas distintas producen dos
 * entradas de caché distintas (la telemetría se mide contra las posiciones de cada
 * cuenta); antes solo se cacheaba por ids y al cambiar de cuenta se reutilizaba la
 * respuesta de la anterior.
 */
export function autoTelemetryQueryKey(
  studyIds: readonly string[],
  accountId: string | null | undefined,
) {
  return [
    "instrument-daily-opinions-auto-telemetry",
    sortedStudyIds(studyIds),
    accountId ?? null,
  ] as const;
}

/** Telemetría A0: solo los campos que pinta la tira. */
type OpinionTelemetry = {
  daysWithOpinions: number;
  alarmaBuyCount: number;
  buyPrecision5d: number | null;
  buyRecall5d: number | null;
  matureBuySample: number;
  criteriaVersion: string;
  caveats: string[];
};

/** Telemetría A6: solo los campos que pinta la tira. */
type AutoTelemetry = {
  funnel: {
    candidatesAlarma: number;
    candidatesDictamen: number;
  };
  gates: {
    expandSourcesReady: boolean;
    sourcesShouldContract: boolean;
    paperDExecuteEnv: boolean;
  };
};

type Props = {
  telemetry?: OpinionTelemetry | null;
  /** Error de la consulta A0: se declara la ausencia, no se oculta. */
  telemetryError?: boolean;
  autoTelemetry?: AutoTelemetry | null;
  /**
   * Diagnóstico de la tarjeta (nivel 3): recuento de Estudio, valores en silencio
   * y `asOf`. Se pintan DENTRO del mismo disclosure para no abrir un segundo.
   */
  studyCount?: number;
  silentCount?: number;
  asOf?: string | null;
};

export function AsesorTelemetryStrip({
  telemetry,
  telemetryError,
  autoTelemetry,
  studyCount,
  silentCount,
  asOf,
}: Props) {
  const diagnostics = [
    studyCount != null && studyCount > 0
      ? `${studyCount} valores en Estudio`
      : null,
    silentCount != null && silentCount > 0
      ? `${silentCount} en silencio`
      : null,
    asOf ? `asOf ${asOf}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const hasContent = Boolean(
    telemetry || telemetryError || autoTelemetry || diagnostics,
  );
  if (!hasContent) return null;

  return (
    <TechnicalDetail
      testId={ASESOR_OPINIONS_TELEMETRY_TEST_ID}
      className="text-xs"
    >
      {telemetry ? (
        <div
          className="rounded-md border border-border/80 bg-muted/15 px-3 py-2 text-xs"
          data-testid="asesor-opinion-telemetry"
          title={telemetry.caveats.join(" · ")}
        >
          <p className="font-medium text-foreground">
            Telemetría A0 (90d · Estudio)
          </p>
          <p className="mt-1 tabular-nums text-muted-foreground">
            {telemetry.daysWithOpinions} días · {telemetry.alarmaBuyCount}{" "}
            Comprar · alarma · prec.5d {pctLabel(telemetry.buyPrecision5d)} ·
            recall≈ {pctLabel(telemetry.buyRecall5d)} · n=
            {telemetry.matureBuySample}
          </p>
          <p
            className="mt-0.5 text-[10px] text-muted-foreground"
            title="Criterios internos de mejora del estudio (P3 y P4). No activan AUTO ni autorizan operar."
          >
            Criterio de mejora del estudio sin activar AUTO · Proxy Outcomes{" "}
            {telemetry.criteriaVersion}.
          </p>
        </div>
      ) : telemetryError ? (
        <p className="text-xs text-muted-foreground">
          Telemetría A0 no disponible.
        </p>
      ) : null}
      {autoTelemetry ? (
        <div
          className="rounded-md border border-border/80 bg-muted/15 px-3 py-2 text-xs"
          data-testid="asesor-auto-telemetry"
        >
          <p className="font-medium text-foreground">
            Telemetría A6 (Estudio AUTO)
          </p>
          <p className="mt-1 tabular-nums text-muted-foreground">
            {autoTelemetry.funnel.candidatesAlarma} alarma ·{" "}
            {autoTelemetry.funnel.candidatesDictamen} dictamen · ampliar fuentes{" "}
            {autoTelemetry.gates.expandSourcesReady ? "listo" : "bloqueado"}
          </p>
          {autoTelemetry.gates.sourcesShouldContract ? (
            <p
              className="mt-1 rounded border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-[10px] font-medium text-rose-800 dark:text-rose-200"
              data-testid="asesor-a6-contract-alert"
            >
              Veto A6: contraer fuentes AUTO — telemetría degradada. Revisión
              manual.
            </p>
          ) : null}
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            Solo Estudio. Radar/Hoy fuera. P1–P5 en Consola. Execute env{" "}
            {autoTelemetry.gates.paperDExecuteEnv ? "on" : "off"}.
          </p>
        </div>
      ) : null}
      {diagnostics ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="asesor-opinion-diagnostics"
        >
          {diagnostics}
        </p>
      ) : null}
    </TechnicalDetail>
  );
}
