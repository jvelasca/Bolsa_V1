/**
 * DÍA-D retrospectivo **as-run** (ADR-049) — panel read-only + encolado del replay.
 *
 * Responde a la pregunta: *«si en D hubiéramos seguido exactamente la operativa que
 * llevábamos, ¿qué habría pasado hasta hoy?»*. Compara el brazo `as_run` (fills reales)
 * contra `hold_structural`, `cash`, `engine_params`, `candidate` y el benchmark `market_bh`.
 *
 * Doctrina «Sin dato todavía»: un brazo no medible llega con `measured=false` y un motivo;
 * se pinta como hueco declarado, NUNCA como `0` ni como «sin operaciones». El benchmark de
 * mercado no tiene stop, así que publica retorno y no R: convertirlo en `0 R` sería mentir.
 *
 * La certificación que se pinta es la del **método**, no la del resultado: un DÍA-D
 * certificado puede ser negativo y seguir siendo útil. Este panel no autoriza nada.
 */

import { useState } from "react";
import { Play, RefreshCw } from "lucide-react";
import type {
  DiaDAsRunArmV1,
  DiaDAsRunArtifactV1,
  DiaDAsRunCertificationV1,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  useAutoDiaDAsRun,
  useAutoDiaDAsRunDays,
  useEnqueueDiaDAsRun,
} from "@/features/auto-monitor/use-dia-d-as-run";

const ARM_LABELS: Record<string, string> = {
  as_run: "As-run (real)",
  hold_structural: "Hold estructural",
  cash: "Caja",
  engine_params: "Motor (params vigentes)",
  candidate: "Candidata",
  market_bh: "Mercado (buy & hold)",
};

function armLabel(arm: string): string {
  return ARM_LABELS[arm] ?? arm;
}

/** Un hueco se declara con raya y motivo; nunca se convierte en 0. */
function formatNumber(value: number | null, suffix = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const rounded = Math.round(value * 100) / 100;
  return `${rounded}${suffix}`;
}

function formatMoney(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const rounded = Math.round(value * 100) / 100;
  return `${rounded.toLocaleString("es-ES")} €`;
}

const CERT_LABELS: Record<string, string> = {
  certified: "MÉTODO CERTIFICADO",
  not_certified: "MÉTODO NO CERTIFICADO",
  insufficient_sample: "MUESTRA INSUFICIENTE",
};

function CertificationBadge({
  certification,
}: {
  certification: DiaDAsRunCertificationV1 | null | undefined;
}) {
  if (!certification) {
    return (
      <span
        className="font-semibold text-muted-foreground"
        data-testid="as-run-certification"
        title="Artefacto sin certificación: no puede sostener ninguna decisión"
      >
        SIN CERTIFICAR
      </span>
    );
  }
  const verdict = certification.verdict;
  const tone =
    verdict === "certified"
      ? "text-emerald-600 dark:text-emerald-400"
      : verdict === "insufficient_sample"
        ? "text-amber-600 dark:text-amber-400"
        : "text-destructive";
  return (
    <span
      className={`font-semibold ${tone}`}
      data-testid="as-run-certification"
      title={
        certification.reasons.join(" · ") || "Ocho condiciones verificadas"
      }
    >
      {CERT_LABELS[verdict] ?? "SIN CERTIFICAR"}
    </span>
  );
}

function ArmRow({ arm }: { arm: DiaDAsRunArmV1 }) {
  return (
    <tr
      className="border-t border-border/60"
      data-testid={`as-run-arm-${arm.arm}`}
    >
      <th scope="row" className="py-2 pr-3 text-left font-medium">
        {armLabel(arm.arm)}
      </th>
      <td className="py-2 pr-3 text-right font-mono">
        {arm.measured ? formatNumber(arm.realizedR, " R") : "—"}
      </td>
      <td className="py-2 pr-3 text-right font-mono">
        {formatNumber(arm.returnPct, " %")}
      </td>
      <td className="py-2 pr-3 text-right font-mono">
        {formatMoney(arm.pnlCurrency)}
      </td>
      <td className="py-2 pr-3 text-right font-mono">
        {formatNumber(arm.maeR)}
      </td>
      <td className="py-2 pr-3 text-right font-mono">
        {formatNumber(arm.mfeR)}
      </td>
      <td className="py-2 pr-3 text-right font-mono">
        {arm.capture === null ? "—" : `${Math.round(arm.capture * 100)} %`}
      </td>
      <td className="py-2 pr-3 text-right font-mono">
        {arm.measured ? `${arm.exits} / ${arm.stops} / ${arm.targets}` : "—"}
      </td>
      <td className="py-2 text-left text-xs text-muted-foreground">
        {arm.measured ? "" : (arm.reason ?? "no medido")}
      </td>
    </tr>
  );
}

function ExecutionLine({ artifact }: { artifact: DiaDAsRunArtifactV1 }) {
  const execution = artifact.audit?.execution;
  if (!execution) return null;
  return (
    <p
      className="text-[11px] text-muted-foreground"
      data-testid="as-run-execution"
    >
      Ejecución declarada: comisión{" "}
      <span className="font-mono text-foreground">
        {formatNumber(execution.commissionBps, " bps")}
      </span>
      {" · "}deslizamiento{" "}
      <span className="font-mono text-foreground">
        {formatNumber(execution.slippageBps, " bps")}
      </span>
      {" · "}spread{" "}
      <span className="font-mono text-foreground">
        {formatNumber(execution.spreadBps, " bps")}
      </span>
      {" · "}liquidez máx.{" "}
      <span className="font-mono text-foreground">
        {execution.maxParticipationPct === null
          ? "—"
          : `${Math.round(execution.maxParticipationPct * 100)} % del volumen`}
      </span>
      {" · "}gaps{" "}
      <span className="font-mono text-foreground">{execution.gapPolicy}</span>
    </p>
  );
}

function AuditLine({ artifact }: { artifact: DiaDAsRunArtifactV1 }) {
  const audit = artifact.audit;
  if (!audit) return null;
  return (
    <p className="text-[11px] text-muted-foreground" data-testid="as-run-audit">
      Auditoría: estado{" "}
      <span
        className="font-mono text-foreground"
        title={audit.pointInTime.legsHash}
      >
        {audit.pointInTime.legsHash.slice(0, 10)}…
      </span>
      {" · "}barras{" "}
      <span className="font-mono text-foreground" title={audit.data.barsHash}>
        {audit.data.barsHash.slice(0, 10)}…
      </span>
      {" · "}
      <span className="font-mono text-foreground">
        {audit.versions.engine} / {audit.versions.schema}
        {audit.versions.bump ? ` / ${audit.versions.bump}` : ""}
      </span>
      {" · "}punto en el tiempo{" "}
      <span className="font-mono text-foreground">{audit.pointInTime.day}</span>
      {audit.pointInTime.sourceIsReconstructed ? " (reconstruido)" : " (real)"}
    </p>
  );
}

function ArtifactView({ artifact }: { artifact: DiaDAsRunArtifactV1 }) {
  const status = artifact.status ?? "not_measured";
  return (
    <div className="space-y-3" data-testid="as-run-artifact">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          Día <span className="font-mono text-foreground">{artifact.day}</span>
        </span>
        <span>
          Coste round-trip{" "}
          <span className="font-mono text-foreground">
            {formatNumber(artifact.costBps, " bps")}
          </span>
        </span>
        <span>
          Estado{" "}
          <span
            className={
              status === "measured"
                ? "font-semibold text-emerald-600 dark:text-emerald-400"
                : "font-semibold text-amber-600 dark:text-amber-400"
            }
            data-testid="as-run-status"
          >
            {status === "measured" ? "MEDIDO" : "NO MEDIDO"}
          </span>
        </span>
        <CertificationBadge certification={artifact.certification} />
        <span>
          Posiciones en D:{" "}
          <span className="font-mono text-foreground">
            {artifact.startingState.legs ?? 0}
          </span>
          {artifact.startingState.cashOnly ? " (sólo caja)" : ""}
        </span>
        {artifact.hash ? (
          <span className="font-mono" title={artifact.hash}>
            hash {artifact.hash.slice(0, 12)}…
          </span>
        ) : null}
      </div>

      <ExecutionLine artifact={artifact} />

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="py-1 pr-3 text-left">
                Brazo
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                R neto
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                Retorno
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                PnL
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                MAE
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                MFE
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                Captura
              </th>
              <th scope="col" className="py-1 pr-3 text-right">
                Salidas/stop/target
              </th>
              <th scope="col" className="py-1 text-left">
                Hueco
              </th>
            </tr>
          </thead>
          <tbody>
            {artifact.arms.map((arm) => (
              <ArmRow key={arm.arm} arm={arm} />
            ))}
          </tbody>
        </table>
      </div>

      {artifact.gaps.length > 0 ? (
        <div
          className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2"
          data-testid="as-run-gaps"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            Huecos declarados
          </p>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            {artifact.gaps.map((gap) => (
              <li key={`${gap.arm}-${gap.reason}`}>
                <span className="font-medium text-foreground">
                  {armLabel(gap.arm)}
                </span>
                : {gap.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <AuditLine artifact={artifact} />

      {artifact.certification && !artifact.certification.certified ? (
        <div
          className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2"
          data-testid="as-run-certification-reasons"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            Método no certificado
          </p>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            {(artifact.certification.reasons.length > 0
              ? artifact.certification.reasons
              : ["sin_detalle"]
            ).map((reason) => (
              <li key={reason} className="font-mono">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function DiaDAsRunPanel() {
  const daysQuery = useAutoDiaDAsRunDays();
  const days = daysQuery.data?.days ?? [];
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [runDay, setRunDay] = useState("");
  const [runTo, setRunTo] = useState("");
  const activeDay = selectedDay ?? days[0] ?? null;
  const artifactQuery = useAutoDiaDAsRun(activeDay, {
    enabled: Boolean(activeDay),
  });
  const enqueue = useEnqueueDiaDAsRun();

  const notes = daysQuery.data?.notes ?? [];

  return (
    <Card className="rounded-xl" data-testid="as-run-panel">
      <CardContent className="space-y-4 py-4">
        <div>
          <p className="text-sm font-semibold">DÍA-D retrospectivo as-run</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Rejuega la operativa que <strong>realmente</strong> llevábamos desde
            el día D: compara los fills reales (
            <span className="font-mono">as_run</span>) contra mantener, caja, el
            motor con los parámetros vigentes, una candidata y el benchmark de
            mercado (<span className="font-mono">market_bh</span>). Read-only;
            sin look-ahead. Un brazo no medible se declara, nunca se rellena con
            0. La certificación valida el <strong>método</strong>, no la
            rentabilidad: un resultado negativo certificado sigue siendo un
            resultado útil.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Día D a rejugar
            <input
              type="date"
              className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
              value={runDay}
              onChange={(event) => setRunDay(event.target.value)}
              data-testid="as-run-run-day"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Hasta (opcional)
            <input
              type="date"
              className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
              value={runTo}
              onChange={(event) => setRunTo(event.target.value)}
              data-testid="as-run-run-to"
            />
          </label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!runDay || enqueue.isPending}
            onClick={() =>
              enqueue.mutate({
                day: runDay || null,
                to: runTo || null,
              })
            }
            data-testid="as-run-run"
          >
            <Play className="h-3.5 w-3.5" />
            {enqueue.isPending ? "Encolando…" : "Encolar replay"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => void daysQuery.refetch()}
            disabled={daysQuery.isFetching}
            data-testid="as-run-refresh-days"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Actualizar días
          </Button>
        </div>

        {enqueue.data ? (
          <p className="text-xs text-muted-foreground" data-testid="as-run-job">
            Job <span className="font-mono">{enqueue.data.id}</span> ·{" "}
            {enqueue.data.status}
            {enqueue.data.created ? " (encolado)" : " (ya activo)"} · día{" "}
            <span className="font-mono">{enqueue.data.day}</span>
          </p>
        ) : null}
        {enqueue.error ? (
          <p
            className="text-xs text-destructive"
            data-testid="as-run-job-error"
          >
            No se pudo encolar el replay as-run.
          </p>
        ) : null}

        {daysQuery.isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="as-run-days-loading"
          >
            Cargando días…
          </p>
        ) : null}

        {daysQuery.isError ? (
          <p
            className="text-sm text-destructive"
            data-testid="as-run-days-error"
          >
            No se pudieron cargar los días con artefacto as-run.
          </p>
        ) : null}

        {!daysQuery.isLoading && days.length === 0 ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="as-run-empty"
          >
            Sin artefactos as-run todavía
            {notes.includes("no_account_scope")
              ? " (no hay cuenta activa)."
              : ". Encola un día D para medir la operativa real."}
          </p>
        ) : null}

        {days.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Artefacto disponible
              <select
                className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                value={activeDay ?? ""}
                onChange={(event) => setSelectedDay(event.target.value)}
                data-testid="as-run-day-select"
              >
                {days.map((day) => (
                  <option key={day} value={day}>
                    {day}
                  </option>
                ))}
              </select>
            </label>
            {artifactQuery.data?.artifactModifiedAt ? (
              <span className="text-[11px] text-muted-foreground">
                artefacto de{" "}
                {new Date(artifactQuery.data.artifactModifiedAt).toLocaleString(
                  "es-ES",
                )}
              </span>
            ) : null}
          </div>
        ) : null}

        {artifactQuery.isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="as-run-loading"
          >
            Cargando artefacto…
          </p>
        ) : null}

        {artifactQuery.isError ? (
          <p className="text-sm text-destructive" data-testid="as-run-error">
            No se pudo leer el artefacto as-run.
          </p>
        ) : null}

        {artifactQuery.data && !artifactQuery.data.available ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="as-run-unavailable"
          >
            Sin artefacto para ese día
            {artifactQuery.data.notes.length > 0
              ? ` (${artifactQuery.data.notes.join(", ")})`
              : ""}
            .
          </p>
        ) : null}

        {artifactQuery.data?.available ? (
          <ArtifactView artifact={artifactQuery.data} />
        ) : null}
      </CardContent>
    </Card>
  );
}
