/**
 * AUTO · Operativa diaria por valor (universo ESTUDIO).
 *
 * Cuatro estados que NUNCA se mezclan, por valor:
 *   1. señal calculada   — opinión del día (stance, estrellas, canal);
 *   2. decisión tomada   — plan `TRIGGERED` o motivo (`whyNot`/`reason`);
 *   3. operación ejecutada — ciclos durables del audit por valor (deep-link);
 *   4. operativa validada  — veredicto/K/expectancy OOS (nunca `CONFIRMED` aquí).
 *
 * Read-only sobre el parte durable del job `estudio_daily`; el botón solo ENCOLA.
 * Un dato ausente se declara «Sin dato todavía»; nunca se rellena con `0`.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { EstudioDailyPlanV1, EstudioDailyValueV1 } from "@bolsa/shared";
import { absentDataLabel, isAbsent } from "@/components/absent-data";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { autoOperacionHref } from "@/features/auto/auto-nav";
import {
  auditAttributionForValue,
  indexAuditValuesBySymbol,
  useEstudioDailyJob,
  useEstudioDailyOps,
} from "@/features/auto-monitor/use-estudio-daily-ops";
import {
  indexChainValuesByInstrument,
  useEstudioChain,
} from "@/features/auto-monitor/use-estudio-chain";
import { EstudioChainEvidence } from "@/features/auto-monitor/estudio-chain-evidence";
import { useAutoEstudioAudit } from "@/features/auto-monitor/use-auto-dia-d-feedback";

type AuditValue =
  ReturnType<typeof indexAuditValuesBySymbol> extends Map<string, infer V>
    ? V
    : never;

/**
 * `ok` = el motor **propone** un plan en dry-run (`execute: False`). No es una orden
 * enviada ni una operación ejecutada: esas etiquetas se reservan para hechos durables de
 * orden/fill.
 */
const STATUS_LABEL: Record<string, string> = {
  ok: "Plan propuesto",
  no_signal: "Sin señal",
  no_plan: "Sin plan",
  error: "Error",
};

const STATUS_STYLE: Record<string, string> = {
  ok: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  no_signal: "bg-muted text-muted-foreground",
  no_plan: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  error: "bg-destructive/15 text-destructive",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtNumber(value: number | null | undefined): string {
  return isAbsent(value) ? absentDataLabel() : (value as number).toFixed(2);
}

function fmtR(value: number | null | undefined): string {
  if (isAbsent(value)) return absentDataLabel();
  const numeric = value as number;
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}R`;
}

function fmtPct(value: number | null | undefined): string {
  if (isAbsent(value)) return absentDataLabel();
  return `${(value as number).toFixed(2)}%`;
}

function textOrAbsent(value: string | null | undefined): string {
  return value && value.trim() ? value : absentDataLabel();
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      data-testid="estudio-daily-value-status"
      data-status={status}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        STATUS_STYLE[status] ?? "bg-muted text-muted-foreground",
      )}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function PlanLevels({ plan }: { plan: EstudioDailyPlanV1 | null }) {
  if (!plan) {
    return (
      <p
        className="text-[11px] text-muted-foreground"
        data-testid="estudio-daily-value-plan-absent"
      >
        {absentDataLabel()}: no hay `TradePlan` para este valor.
      </p>
    );
  }
  return (
    <dl
      className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] sm:grid-cols-4"
      data-testid="estudio-daily-value-plan"
      data-plan-status={plan.status ?? ""}
    >
      <div>
        <dt className="text-muted-foreground">Entrada</dt>
        <dd className="font-mono tabular-nums">{fmtNumber(plan.entry)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Stop estructural</dt>
        <dd className="font-mono tabular-nums">
          {fmtNumber(plan.structuralStop)}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Objetivo 1 / 2</dt>
        <dd className="font-mono tabular-nums">
          {fmtNumber(plan.target1)} / {fmtNumber(plan.target2)}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">R:R</dt>
        <dd className="font-mono tabular-nums">
          {isAbsent(plan.expectedRR)
            ? absentDataLabel()
            : `${(plan.expectedRR as number).toFixed(2)}R`}
        </dd>
      </div>
    </dl>
  );
}

function ValidationBlock({
  audit,
  auditFailed,
}: {
  audit: AuditValue | undefined;
  auditFailed: boolean;
}) {
  if (auditFailed) {
    return (
      <p
        role="alert"
        className="text-[11px] text-destructive"
        data-testid="estudio-daily-value-validation-error"
      >
        No se pudo leer la auditoría por valor: la evidencia no está disponible.
        Esto <strong>no</strong> significa que no exista.
      </p>
    );
  }
  if (!audit) {
    return (
      <p
        className="text-[11px] text-muted-foreground"
        data-testid="estudio-daily-value-validation-absent"
      >
        {absentDataLabel()}: este valor no aparece en la ventana de auditoría.
      </p>
    );
  }
  const resultR = audit.resultR;
  return (
    <div
      className="space-y-0.5 text-[11px]"
      data-testid="estudio-daily-value-validation"
      data-measured={String(audit.measured)}
    >
      <p className="font-mono">
        {textOrAbsent(resultR.verdict)} · K={resultR.measuredCycles} ·
        expectancy {fmtR(resultR.expectancyR)}
      </p>
      <p className="text-[10px] text-muted-foreground">
        evidencia {textOrAbsent(resultR.evidenceQuality)} · hit{" "}
        {isAbsent(resultR.hitRate)
          ? absentDataLabel()
          : `${((resultR.hitRate as number) * 100).toFixed(1)}%`}{" "}
        · dinero {fmtPct(audit.money.netReturnPct)} · DD{" "}
        {fmtPct(audit.money.maxDrawdownPct)}
      </p>
      {(audit.unmeasured ?? []).length > 0 ? (
        <ul className="list-disc pl-4 text-[10px] text-muted-foreground">
          {audit.unmeasured.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Enlace contextual de la ficha diaria al sandbox DÍA-D.
 *
 * Lleva el día (la vela usada) y el valor **como contexto**, no como validación: el sandbox
 * declara que es una comprobación global del día.
 */
function diaDContextHref(value: EstudioDailyValueV1): string {
  const params = new URLSearchParams({ mode: "dia-d" });
  if (value.asOfBarDate) params.set("day", value.asOfBarDate);
  if (value.symbol) params.set("symbol", value.symbol);
  return `/auto-monitor?${params.toString()}`;
}

function ValueCard({
  value,
  audit,
  auditWindow,
  auditFailed,
  chainValue,
  chain,
  chainLoading,
  chainFailed,
}: {
  value: EstudioDailyValueV1;
  audit: AuditValue | undefined;
  auditWindow: string | null;
  auditFailed: boolean;
  chainValue: import("@bolsa/shared").EstudioChainValueV1 | undefined;
  chain: import("@bolsa/shared").EstudioChainResponseV1 | null;
  chainLoading: boolean;
  chainFailed: boolean;
}) {
  const plan = value.plan ?? null;
  const cycles = audit?.cycles ?? [];
  const whyNot = value.whyNot ?? [];
  // El contrato actual de ciclos NO trae `planId`/`signalId`: se leen si el artefacto los
  // añade en el futuro y, mientras tanto, la atribución es honestamente «no atribuido».
  const attribution = auditAttributionForValue(
    cycles.map((cycle) => ({
      planId: (cycle as { planId?: string | null }).planId,
      signalId: (cycle as { signalId?: string | null }).signalId,
    })),
    {
      planId: value.strategy?.planId,
      signalId: value.strategy?.signalId,
    },
  );

  return (
    <li
      data-testid="estudio-daily-value"
      data-symbol={value.symbol ?? value.instrumentId}
      data-status={value.status}
      className="rounded-lg border border-border/60 p-3"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm font-semibold">
            {value.symbol ?? value.instrumentId}
          </span>
          <span
            className="text-[10px] text-muted-foreground"
            data-testid="estudio-daily-value-bar"
            data-bar-verified={String(Boolean(value.asOfBarDate))}
          >
            {value.asOfBarDate
              ? `vela ${value.asOfBarDate}`
              : "vela no verificada"}{" "}
            ·{" "}
            {value.computedAt
              ? `calculado ${value.computedAt}`
              : "hora de cálculo sin dato"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={diaDContextHref(value)}
            data-testid="estudio-daily-value-dia-d"
            className="text-[10px] text-muted-foreground underline hover:text-primary"
          >
            Ver DÍA-D del día →
          </Link>
          <StatusBadge status={value.status} />
        </div>
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <section data-testid="estudio-daily-value-signal">
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            1 · Señal calculada
          </h4>
          <p className="text-[11px]">
            {textOrAbsent(value.opinion?.stance)} ·{" "}
            {isAbsent(value.opinion?.dictamenStars)
              ? absentDataLabel()
              : `${value.opinion.dictamenStars}★`}{" "}
            · canal {textOrAbsent(value.opinion?.channel)}
          </p>
          <p className="text-[10px] text-muted-foreground">
            {value.opinion?.reasons?.length
              ? value.opinion.reasons.join(" · ")
              : absentDataLabel()}
          </p>
        </section>

        <section data-testid="estudio-daily-value-strategy">
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Estrategia e indicadores
          </h4>
          <p
            className="font-mono text-[11px]"
            data-testid="estudio-daily-value-strategy-name"
          >
            {textOrAbsent(value.strategy?.strategyDefinitionId)} · v
            {isAbsent(value.strategy?.strategyVersion)
              ? absentDataLabel()
              : value.strategy?.strategyVersion}
          </p>
          <p
            className="font-mono text-[10px] text-muted-foreground"
            data-testid="estudio-daily-value-strategy-identity"
          >
            preset de origen {textOrAbsent(value.strategy?.presetKey)} · plan{" "}
            {textOrAbsent(value.strategy?.planId)} · señal{" "}
            {textOrAbsent(value.strategy?.signalId)}
          </p>
          <p
            className="text-[10px] text-muted-foreground"
            data-testid="estudio-daily-value-strategy-winner"
          >
            Indicador ganador: no declarado por el motor · TOP{" "}
            {textOrAbsent(value.opinion?.topId)}
            {isAbsent(value.opinion?.topVersion)
              ? ""
              : ` v${value.opinion?.topVersion}`}
          </p>
          <p className="text-[10px] text-muted-foreground">
            IO {fmtNumber(value.indicators?.io)} · FA{" "}
            {fmtNumber(value.indicators?.fa)} · TA{" "}
            {fmtNumber(value.indicators?.ta)} ·{" "}
            {textOrAbsent(value.indicators?.regime)}
          </p>
        </section>

        <section data-testid="estudio-daily-value-decision">
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            2 · Decisión tomada
          </h4>
          {plan?.status === "TRIGGERED" ? (
            <PlanLevels plan={plan} />
          ) : (
            <>
              <p className="text-[11px] text-muted-foreground">
                {value.reason
                  ? value.reason
                  : plan?.status
                    ? `Plan ${plan.status}`
                    : absentDataLabel()}
              </p>
              {whyNot.length > 0 ? (
                <p
                  className="font-mono text-[10px] text-muted-foreground"
                  data-testid="estudio-daily-value-whynot"
                >
                  whyNot: {whyNot.join(", ")}
                </p>
              ) : null}
            </>
          )}
        </section>

        <section data-testid="estudio-daily-value-operation">
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            3 · Operación ejecutada
          </h4>
          <p
            className="text-[10px] text-muted-foreground"
            data-testid="estudio-daily-value-operation-scope"
            data-attributed={String(attribution.attributed)}
          >
            {attribution.label} · ventana {textOrAbsent(auditWindow)}
          </p>
          {auditFailed ? (
            <p className="text-[11px] text-destructive">
              No se pudo leer la evidencia de ejecución (no implica que no
              exista).
            </p>
          ) : cycles.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">
              {absentDataLabel()}: sin ciclos durables en la ventana de
              auditoría.
            </p>
          ) : (
            <ul className="space-y-0.5 text-[11px]">
              {cycles.map((cycle, index) => (
                <li
                  key={`${cycle.cycleId}#${index}`}
                  className="flex flex-wrap items-center gap-2"
                  data-testid="estudio-daily-value-cycle"
                  data-cycle-id={cycle.cycleId}
                >
                  <span className="font-mono">
                    {cycle.entryDay} → {cycle.exitDay ?? absentDataLabel()} ·{" "}
                    {fmtR(cycle.realizedR)}
                  </span>
                  <Link
                    to={autoOperacionHref(cycle.cycleId)}
                    className="underline hover:text-primary"
                  >
                    Ver operación →
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section
          className="sm:col-span-2"
          data-testid="estudio-daily-value-validated"
        >
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            4 · Operativa validada
          </h4>
          <ValidationBlock audit={audit} auditFailed={auditFailed} />
        </section>

        <EstudioChainEvidence
          value={value}
          chainValue={chainValue}
          chain={chain}
          chainLoading={chainLoading}
          chainFailed={chainFailed}
          audit={audit}
          auditWindow={auditWindow}
        />
      </div>
    </li>
  );
}

export function EstudioDailyOpsPanel() {
  const [asOf, setAsOf] = useState<string>(todayIso());
  const opsQuery = useEstudioDailyOps(asOf);
  const auditQuery = useAutoEstudioAudit();
  const { job, hasAccount, isRunning, isQueuing, run, runError, jobError } =
    useEstudioDailyJob(asOf);

  const auditBySymbol = useMemo(
    () => indexAuditValuesBySymbol(auditQuery.data),
    [auditQuery.data],
  );
  const response = opsQuery.data ?? null;
  const report = response?.report ?? null;

  // Evidencia de cadena: UNA query por informe (no una por valor), habilitada cuando ya hay
  // parte que leer. Se indexa por `instrumentId` para pintarla en cada ficha.
  const chainQuery = useEstudioChain(report ? asOf : null);
  const chainByInstrument = useMemo(
    () => indexChainValuesByInstrument(chainQuery.data),
    [chainQuery.data],
  );
  const chain = chainQuery.data ?? null;
  const chainFailed = chainQuery.isError || Boolean(chain && !chain.available);
  const chainError =
    chain && !chain.available
      ? (chain.error ?? chain.notes.join(", "))
      : chainQuery.error instanceof Error
        ? chainQuery.error.message
        : null;
  const values = report?.values ?? [];
  const auditWindow = auditQuery.data?.window ?? null;
  // Un fallo de la auditoría NO es «este valor no existe»: se declara como error.
  const auditFailed = auditQuery.isError;
  const universeCount = report?.universeCount ?? null;
  const coverageGap =
    typeof universeCount === "number" &&
    universeCount > 0 &&
    universeCount !== report?.scannedCount;
  const runLabel =
    isRunning || isQueuing
      ? "Calculando operativa…"
      : "Calcular operativa diaria";
  const phase = job?.progress?.phase ?? null;
  const percent = job?.progress?.percent ?? null;
  const transportError = runError ?? jobError;

  return (
    <div className="space-y-4" data-testid="estudio-daily-ops-panel">
      <Card className="rounded-xl border border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            Operativa diaria por valor · universo ESTUDIO
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Una fila por valor con los cuatro estados separados. El botón encola
            el mismo job que el scheduler; el parte es durable.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <label
              className="text-[11px] text-muted-foreground"
              htmlFor="estudio-daily-asof"
            >
              Fecha asOf
            </label>
            <input
              id="estudio-daily-asof"
              data-testid="estudio-daily-asof"
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value || todayIso())}
              className="h-8 rounded-md border border-border bg-background px-2 text-xs tabular-nums"
            />
            <Button
              type="button"
              size="sm"
              data-testid="estudio-daily-run"
              disabled={!hasAccount || !asOf || isRunning || isQueuing}
              onClick={() => run()}
            >
              {runLabel}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              data-testid="estudio-daily-refresh"
              disabled={!hasAccount || !asOf}
              onClick={() => {
                // Refresca lo que se VE (parte + auditoría), no el monitor oculto.
                void opsQuery.refetch();
                void auditQuery.refetch();
              }}
            >
              Actualizar
            </Button>
            {!hasAccount ? (
              <span
                data-testid="estudio-daily-no-account"
                className="text-[10px] text-muted-foreground"
              >
                Sin cuenta activa: no se puede calcular ni leer.
              </span>
            ) : null}
            {job ? (
              <span
                data-testid="estudio-daily-job-status"
                data-status={job.status}
                className="text-[10px] uppercase tracking-wide text-muted-foreground"
              >
                job {job.status} · {job.day} · intento {job.attempt}
              </span>
            ) : null}
          </div>

          {isRunning ? (
            <div
              data-testid="estudio-daily-job-progress"
              data-phase={phase ?? ""}
              className="space-y-1"
            >
              <p className="text-[11px] tabular-nums text-muted-foreground">
                {phase ? `Fase ${phase}` : "Progreso no declarado todavía"}
                {percent != null ? ` · ${percent}%` : ""}
              </p>
              {percent != null ? (
                <div className="h-1.5 w-full overflow-hidden rounded bg-muted">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          {job?.status === "failed" ? (
            <p
              role="alert"
              data-testid="estudio-daily-job-error"
              className="text-xs text-destructive"
            >
              La última ejecución falló: {job.error ?? "sin detalle"}
            </p>
          ) : null}

          {transportError ? (
            <p
              role="alert"
              data-testid="estudio-daily-transport-error"
              className="text-xs text-destructive"
            >
              No se pudo consultar la ejecución:{" "}
              {transportError instanceof Error
                ? transportError.message
                : "error desconocido"}
              .
            </p>
          ) : null}

          {response?.notes && response.notes.length > 0 ? (
            <ul
              data-testid="estudio-daily-notes"
              className="space-y-0.5 text-[10px] text-muted-foreground"
            >
              {response.notes.map((note) => (
                <li key={note} className="font-mono">
                  {note}
                </li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>

      <Card className="rounded-xl border border-border bg-card">
        <CardContent className="py-3" data-testid="estudio-daily-legend">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Cuatro estados que no se mezclan
          </p>
          <ol className="mt-1 grid gap-1 text-[11px] text-muted-foreground sm:grid-cols-2">
            <li>1 · Señal calculada: opinión del día (stance y estrellas).</li>
            <li>
              2 · Decisión propuesta: plan en dry-run (no es una orden) o motivo
              declarado.
            </li>
            <li>
              3 · Operación ejecutada: ciclos durables DÍA-D (histórico del
              valor salvo identidad estable).
            </li>
            <li>4 · Operativa validada: veredicto, K y expectancy OOS.</li>
          </ol>
          <p
            className="mt-1 text-[10px] text-muted-foreground"
            data-testid="estudio-daily-chain-legend"
          >
            5 · Cadena y resultado: evidencia durable de las nueve etapas y
            DÍA-D del valor bajo demanda. No es una quinta validación ni emite{" "}
            <code>CONFIRMED</code>.
          </p>
        </CardContent>
      </Card>

      {opsQuery.isError ? (
        <p
          role="alert"
          data-testid="estudio-daily-error"
          className="text-sm text-destructive"
        >
          No se pudo cargar la operativa diaria:{" "}
          {opsQuery.error instanceof Error
            ? opsQuery.error.message
            : "error desconocido"}
          .{" "}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void opsQuery.refetch()}
          >
            Reintentar
          </Button>
        </p>
      ) : null}

      {opsQuery.isLoading ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="estudio-daily-loading"
        >
          Cargando la operativa diaria…
        </p>
      ) : null}

      {auditFailed ? (
        <p
          role="alert"
          data-testid="estudio-daily-audit-error"
          className="text-sm text-destructive"
        >
          No se pudo cargar la auditoría por valor:{" "}
          {auditQuery.error instanceof Error
            ? auditQuery.error.message
            : "error desconocido"}
          . La ausencia de evidencia <strong>no</strong> se declara como «sin
          dato».{" "}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void auditQuery.refetch()}
          >
            Reintentar
          </Button>
        </p>
      ) : null}

      {chainFailed ? (
        <p
          role="alert"
          data-testid="estudio-chain-error"
          className="text-sm text-destructive"
        >
          No se pudo leer la cadena durable por valor:{" "}
          {chainError ?? "error desconocido"}. La ausencia de evidencia{" "}
          <strong>no</strong> se declara como «sin dato».{" "}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void chainQuery.refetch()}
          >
            Reintentar
          </Button>
        </p>
      ) : null}

      {/* Sin cuenta no se ofrece una acción bloqueada: el estado vacío sobra. */}
      {!opsQuery.isLoading &&
      !opsQuery.isError &&
      report === null &&
      hasAccount ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="estudio-daily-empty"
        >
          {absentDataLabel()}: no hay parte calculado para {asOf}. Pulsa
          «Calcular operativa diaria» para encolar el trabajo.
        </p>
      ) : null}

      {report && report.status !== "ok" ? (
        <p
          data-testid="estudio-daily-universe-gap"
          className="text-sm text-amber-600 dark:text-amber-400"
        >
          Universo ESTUDIO {report.status}:{" "}
          {report.notes?.[0] ?? "sin motivo declarado"}. No se escribieron
          opiniones.
        </p>
      ) : null}

      {report && report.status === "ok" ? (
        <Card className="rounded-xl border border-border bg-card">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <CardTitle className="text-sm">Parte de {report.asOf}</CardTitle>
              <span
                data-testid="estudio-daily-counts"
                className="text-[10px] tabular-nums text-muted-foreground"
              >
                {report.scannedCount} valores · plan {report.counts.ok} · sin
                señal {report.counts.no_signal} · sin plan{" "}
                {report.counts.no_plan} · error {report.counts.error}
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <p
              className="text-[10px] tabular-nums text-muted-foreground"
              data-testid="estudio-daily-coverage"
              data-truncated={String(Boolean(report.truncated))}
            >
              Cobertura: {report.scannedCount}
              {universeCount != null ? ` de ${universeCount}` : ""} valores
              ESTUDIO procesados
              {report.truncated ? " · universo recortado" : ""}
              {coverageGap ? " · parte parcial" : ""}.
            </p>
            {report.truncated ||
            coverageGap ||
            report.countsConsistent === false ? (
              <p
                className="text-[11px] text-amber-600 dark:text-amber-400"
                data-testid="estudio-daily-coverage-warning"
              >
                {report.truncated
                  ? "El universo ESTUDIO se ha recortado: este parte NO cubre todos los valores."
                  : coverageGap
                    ? "El parte no cubre todos los valores del universo ESTUDIO."
                    : "Los contadores no cuadran con los valores del parte."}
              </p>
            ) : null}
            {report.notes && report.notes.length > 0 ? (
              <ul
                className="space-y-0.5 text-[10px] text-muted-foreground"
                data-testid="estudio-daily-report-notes"
              >
                {report.notes.map((note) => (
                  <li key={note} className="font-mono">
                    {note}
                  </li>
                ))}
              </ul>
            ) : null}
            {report.generatedAt ? (
              <p
                className="text-[10px] text-muted-foreground"
                data-testid="estudio-daily-generated-at"
              >
                Generado {report.generatedAt}
              </p>
            ) : null}
            {values.length === 0 ? (
              <p
                data-testid="estudio-daily-no-values"
                className="text-[11px] text-muted-foreground"
              >
                El parte no contiene valores.
              </p>
            ) : (
              <ul className="space-y-2">
                {values.map((value) => (
                  <ValueCard
                    key={value.instrumentId}
                    value={value}
                    audit={
                      value.symbol
                        ? auditBySymbol.get(value.symbol.toUpperCase())
                        : undefined
                    }
                    auditWindow={auditWindow}
                    auditFailed={auditFailed}
                    chainValue={chainByInstrument.get(value.instrumentId)}
                    chain={chain}
                    chainLoading={chainQuery.isLoading}
                    chainFailed={chainFailed}
                  />
                ))}
              </ul>
            )}

            <p
              data-testid="estudio-daily-global-validation"
              className="text-[10px] text-muted-foreground"
            >
              Validación global de la ventana PAPER:{" "}
              <strong>INCONCLUSIVE</strong> hasta cumplir la ventana. Esta vista
              no emite <code>CONFIRMED</code>.{" "}
              <Link
                to="/auto-monitor?mode=dia-d"
                className="underline hover:text-primary"
              >
                Ver evidencia PAPER →
              </Link>
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
