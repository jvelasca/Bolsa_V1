/**
 * Pestaña **Vigilancia** — verificación periódica de estrategia (ADR-050).
 *
 * Responde a una pregunta distinta de «¿ganamos?»: *«¿seguimos con la estrategia correcta?»*.
 * El veredicto es advisory: puede pedir re-LAB o proponer una mutación, y **nunca** activa
 * nada (`activationAllowed=false` viene fijado por el servidor y por el perfil).
 *
 * Dos relojes que NO se mezclan:
 * - **Épocas** no solapadas: son las que deciden. Con `everyDays=30`, 12 muestras tardan ~12
 *   meses; hasta entonces el veredicto es `insufficient_sample`.
 * - **Ventana móvil**: historial visual, nunca certifica.
 *
 * El ledger separa `outcome` (qué pasó) de `decisionQuality` (si la acción fue coherente con
 * el plan). Un perdedor coherente no es un fallo del método.
 */

import { useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, ShieldCheck } from "lucide-react";
import type {
  StrategyVerificationGateDto,
  StrategyVerificationRunDto,
  StrategyVerificationVerdictDto,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  useRecomputeStrategyVerification,
  useStrategyVerification,
  useStrategyVerificationLedger,
  useStrategyVerificationProfile,
  verdictOf,
} from "@/features/auto-monitor/use-strategy-verification";

const VERDICT_LABELS: Record<string, string> = {
  continue: "SEGUIR",
  watch: "VIGILAR",
  relab: "RE-LAB",
  promote_requires_human: "PROMOVER (REQUIERE HUMANO)",
  insufficient_sample: "MUESTRA INSUFICIENTE",
  inconclusive_version_change: "INCONCLUSA (CAMBIO DE VERSIÓN)",
};

function verdictTone(verdict: string): string {
  if (verdict === "continue") return "text-emerald-600 dark:text-emerald-400";
  if (verdict === "relab" || verdict === "promote_requires_human")
    return "text-amber-600 dark:text-amber-400";
  if (verdict === "watch") return "text-sky-600 dark:text-sky-400";
  return "text-muted-foreground";
}

const GATE_STATUS_LABELS: Record<string, string> = {
  pass: "PASS",
  fail: "FAIL",
  not_evaluated: "NO EVALUADO",
};

function gateTone(status: string): string {
  if (status === "pass") return "text-emerald-600 dark:text-emerald-400";
  if (status === "fail") return "text-destructive";
  return "text-amber-600 dark:text-amber-400";
}

function formatNumber(value: number | null | undefined, suffix = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100) / 100}${suffix}`;
}

function GateTable({ gates }: { gates: StrategyVerificationGateDto[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="verification-gates">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
            <th scope="col" className="py-1 pr-3 text-left">
              Gate
            </th>
            <th scope="col" className="py-1 pr-3 text-left">
              Estado
            </th>
            <th scope="col" className="py-1 text-left">
              Motivo
            </th>
          </tr>
        </thead>
        <tbody>
          {gates.map((gate) => (
            <tr
              key={gate.gate}
              className="border-t border-border/60"
              data-testid={`verification-gate-${gate.gate}`}
            >
              <th scope="row" className="py-1.5 pr-3 text-left font-medium">
                {gate.gate}
              </th>
              <td
                className={`py-1.5 pr-3 text-xs font-semibold ${gateTone(gate.status)}`}
              >
                {GATE_STATUS_LABELS[gate.status] ?? gate.status}
              </td>
              <td className="py-1.5 text-xs text-muted-foreground">
                {gate.reason ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EpochSeries({ verdict }: { verdict: StrategyVerificationVerdictDto }) {
  const values = verdict.epochs.map((epoch) =>
    typeof epoch.armsR["as_run"] === "number" ? epoch.armsR["as_run"] : null,
  );
  const max = Math.max(1, ...values.map((value) => Math.abs(value ?? 0)));
  return (
    <div className="space-y-1" data-testid="verification-series">
      {verdict.epochs.map((epoch, index) => {
        const value = values[index] ?? null;
        const width =
          value === null ? 0 : Math.max(2, (Math.abs(value) / max) * 100);
        return (
          <div
            key={epoch.epochId}
            className="flex items-center gap-2 text-[11px]"
          >
            <span className="w-24 shrink-0 font-mono text-muted-foreground">
              {epoch.day}
            </span>
            <span className="relative h-2 flex-1 rounded bg-muted">
              <span
                className={
                  value !== null && value < 0
                    ? "absolute inset-y-0 left-0 rounded bg-destructive/70"
                    : "absolute inset-y-0 left-0 rounded bg-emerald-500/70"
                }
                style={{ width: `${width}%` }}
              />
            </span>
            <span className="w-16 shrink-0 text-right font-mono">
              {formatNumber(value, " R")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function EpochTable({ verdict }: { verdict: StrategyVerificationVerdictDto }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="verification-epochs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
            <th scope="col" className="py-1 pr-3 text-left">
              Época
            </th>
            <th scope="col" className="py-1 pr-3 text-right">
              as-run
            </th>
            <th scope="col" className="py-1 pr-3 text-right">
              Mejor brazo
            </th>
            <th scope="col" className="py-1 pr-3 text-right">
              Ciclos
            </th>
            <th scope="col" className="py-1 pr-3 text-right">
              R vivo
            </th>
            <th scope="col" className="py-1 pr-3 text-right">
              Decisión
            </th>
            <th scope="col" className="py-1 text-left">
              Candidata
            </th>
          </tr>
        </thead>
        <tbody>
          {verdict.epochs.map((epoch) => {
            const competing = Object.entries(epoch.armsR)
              .filter(
                ([arm, value]) =>
                  !["as_run", "cash", "market_bh"].includes(arm) &&
                  typeof value === "number",
              )
              .sort(([, a], [, b]) => (b as number) - (a as number))[0];
            return (
              <tr
                key={epoch.epochId}
                className="border-t border-border/60"
                data-testid={`verification-epoch-${epoch.day}`}
              >
                <th
                  scope="row"
                  className="py-1.5 pr-3 text-left font-mono text-xs"
                >
                  {epoch.day} → {epoch.toDay}
                </th>
                <td className="py-1.5 pr-3 text-right font-mono">
                  {formatNumber(epoch.armsR["as_run"], " R")}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-xs">
                  {competing
                    ? `${competing[0]} · ${formatNumber(competing[1] as number, " R")}`
                    : "—"}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono">
                  {epoch.closedCycles}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-muted-foreground">
                  {formatNumber(epoch.unrealizedR, " R")}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-xs">
                  {epoch.consistentDecisions}/{epoch.inconsistentDecisions}
                </td>
                <td className="py-1.5 text-xs text-muted-foreground">
                  {epoch.candidateMeasured
                    ? formatNumber(epoch.candidateReturnPct, " %")
                    : (epoch.candidateGap ?? "no medida")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const OUTCOME_OPTIONS = ["", "win", "loss", "breakeven", "open", "unmeasured"];
const QUALITY_OPTIONS = ["", "consistent", "inconsistent", "unmeasured"];

function LedgerView({ verdict }: { verdict: StrategyVerificationVerdictDto }) {
  const days = verdict.epochs.map((epoch) => epoch.day);
  const [day, setDay] = useState<string>(days[days.length - 1] ?? "");
  const [instrument, setInstrument] = useState("");
  const [outcome, setOutcome] = useState("");
  const [quality, setQuality] = useState("");
  const query = useStrategyVerificationLedger({
    day: day || null,
    instrument: instrument || undefined,
    outcome: outcome || undefined,
    quality: quality || undefined,
  });
  const rows = query.data?.rows ?? [];

  return (
    <div className="space-y-2" data-testid="verification-ledger">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Día
          <select
            className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
            value={day}
            onChange={(event) => setDay(event.target.value)}
            data-testid="verification-ledger-day"
          >
            {days.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Instrumento
          <input
            className="h-8 w-28 rounded-md border border-border bg-background px-2 text-sm text-foreground"
            value={instrument}
            placeholder="todos"
            onChange={(event) =>
              setInstrument(event.target.value.toUpperCase())
            }
            data-testid="verification-ledger-instrument"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Resultado
          <select
            className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
            data-testid="verification-ledger-outcome"
          >
            {OUTCOME_OPTIONS.map((value) => (
              <option key={value || "all"} value={value}>
                {value || "todos"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Calidad de la decisión
          <select
            className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
            value={quality}
            onChange={(event) => setQuality(event.target.value)}
            data-testid="verification-ledger-quality"
          >
            {QUALITY_OPTIONS.map((value) => (
              <option key={value || "all"} value={value}>
                {value || "todas"}
              </option>
            ))}
          </select>
        </label>
      </div>

      {query.isError ? (
        <p
          className="text-xs text-destructive"
          data-testid="verification-ledger-error"
        >
          No se pudo leer el ledger de ese día.
        </p>
      ) : null}

      {!query.isLoading && rows.length === 0 ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="verification-ledger-empty"
        >
          Sin operaciones para ese filtro
          {query.data?.notes.length ? ` (${query.data.notes.join(", ")})` : ""}.
        </p>
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table
            className="w-full text-sm"
            data-testid="verification-ledger-table"
          >
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-1 pr-3 text-left">
                  Instrumento
                </th>
                <th scope="col" className="py-1 pr-3 text-left">
                  Brazo
                </th>
                <th scope="col" className="py-1 pr-3 text-left">
                  Entrada
                </th>
                <th scope="col" className="py-1 pr-3 text-left">
                  Salida
                </th>
                <th scope="col" className="py-1 pr-3 text-right">
                  R neto
                </th>
                <th scope="col" className="py-1 pr-3 text-left">
                  Resultado
                </th>
                <th scope="col" className="py-1 pr-3 text-left">
                  Decisión
                </th>
                <th scope="col" className="py-1 text-left">
                  Motivo
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.arm}-${row.cycleId ?? row.instrumentId}-${row.entryDay ?? ""}`}
                  className="border-t border-border/60"
                  data-testid={`verification-ledger-row-${row.instrumentId}`}
                >
                  <th scope="row" className="py-1.5 pr-3 text-left font-medium">
                    {row.instrumentId}
                  </th>
                  <td className="py-1.5 pr-3 font-mono text-xs">{row.arm}</td>
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {row.entryDay ?? "—"}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {row.exitDay ?? "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono">
                    {formatNumber(row.netR, " R")}
                  </td>
                  <td className="py-1.5 pr-3 text-xs">{row.outcome}</td>
                  <td className="py-1.5 pr-3 text-xs text-muted-foreground">
                    {row.decisionQuality}
                  </td>
                  <td className="py-1.5 text-xs text-muted-foreground">
                    {row.exitReason ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function VerdictView({ run }: { run: StrategyVerificationRunDto }) {
  const verdict = verdictOf(run);
  if (!verdict) {
    return (
      <p
        className="text-xs text-muted-foreground"
        data-testid="verification-no-verdict"
      >
        El run no declara veredicto legible.
      </p>
    );
  }
  return (
    <div className="space-y-3" data-testid="verification-verdict">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span
          className={`text-sm font-semibold ${verdictTone(verdict.verdict)}`}
          data-testid="verification-verdict-label"
        >
          {VERDICT_LABELS[verdict.verdict] ?? verdict.verdict}
        </span>
        <span>
          Muestras{" "}
          <span className="font-mono text-foreground">
            {verdict.samples}/{verdict.requiredSamples}
          </span>
        </span>
        <span>
          as-run medio{" "}
          <span className="font-mono text-foreground">
            {formatNumber(verdict.asRunMeanR, " R")}
          </span>
        </span>
        <span>
          Mejor brazo{" "}
          <span className="font-mono text-foreground">
            {verdict.bestArm ?? "—"} ·{" "}
            {formatNumber(verdict.bestArmMeanR, " R")}
          </span>
        </span>
        <span>
          Épocas no peores{" "}
          <span className="font-mono text-foreground">
            {verdict.shareEpochsNotWorse === null
              ? "—"
              : `${Math.round(verdict.shareEpochsNotWorse * 100)} %`}
          </span>
        </span>
        <span
          className="font-mono"
          title={verdict.measurementHash ?? undefined}
        >
          medición{" "}
          {(verdict.measurementHash ?? run.measurementHash).slice(0, 12)}…
        </span>
      </div>

      {verdict.reasons.length > 0 ? (
        <ul
          className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground"
          data-testid="verification-reasons"
        >
          {verdict.reasons.map((reason) => (
            <li key={reason} className="font-mono">
              {reason}
            </li>
          ))}
        </ul>
      ) : null}

      <GateTable gates={verdict.gates} />

      {verdict.epochs.length > 0 ? (
        <>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Serie por época (solo no solapadas)
          </p>
          <EpochSeries verdict={verdict} />
          <EpochTable verdict={verdict} />
          <LedgerView verdict={verdict} />
        </>
      ) : null}
    </div>
  );
}

export function StrategyVerificationPanel() {
  const profileQuery = useStrategyVerificationProfile();
  const overviewQuery = useStrategyVerification();
  const recompute = useRecomputeStrategyVerification();

  const latest = overviewQuery.data?.latest ?? null;
  const profile = profileQuery.data?.profile;
  const notes = useMemo(
    () => [
      ...(profileQuery.data?.notes ?? []),
      ...(overviewQuery.data?.notes ?? []),
    ],
    [profileQuery.data?.notes, overviewQuery.data?.notes],
  );

  const recomputeError = recompute.error as {
    status?: number;
    message?: string;
  } | null;

  return (
    <Card className="rounded-xl" data-testid="strategy-verification-panel">
      <CardContent className="space-y-4 py-4">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4" />
            Verificación periódica de estrategia
            <span
              className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
              data-testid="verification-advisory"
            >
              advisory · no activa nada
            </span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Rejuega la operativa real contra brazos contrafactuales y una
            candidata point-in-time para responder si{" "}
            <strong>seguimos con la estrategia correcta</strong>. Solo las{" "}
            <strong>épocas no solapadas</strong> certifican: con un paso de 30
            días, las 12 muestras mínimas tardan ~12 meses y hasta entonces el
            veredicto es «muestra insuficiente». El resultado de un ciclo y la
            calidad de la decisión son ejes distintos.
          </p>
        </div>

        {profile ? (
          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground"
            data-testid="verification-profile"
          >
            <span>
              Perfil{" "}
              <span className="font-mono text-foreground">
                {profile.profileId} / {profile.version}
              </span>
            </span>
            <span className="font-mono" title={profileQuery.data?.profileHash}>
              hash {(profileQuery.data?.profileHash ?? "").slice(0, 12)}…
            </span>
            <span>
              Cadencia cada{" "}
              <span className="font-mono text-foreground">
                {profile.cadence.everyDays} d
              </span>
            </span>
            <span>
              Muestra mínima{" "}
              <span className="font-mono text-foreground">
                {profile.samples.minCohortSamples}
              </span>
            </span>
            <span>
              Universo declarado{" "}
              <span className="font-mono text-foreground">
                {profile.universeInstruments.join(", ") || "—"}
              </span>
            </span>
          </div>
        ) : null}

        {notes.length > 0 ? (
          <ul
            className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground"
            data-testid="verification-notes"
          >
            {notes.map((note) => (
              <li key={note} className="font-mono">
                {note}
              </li>
            ))}
          </ul>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={recompute.isPending}
            onClick={() => recompute.mutate({})}
            data-testid="verification-recompute"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {recompute.isPending ? "Recalculando…" : "Recalcular y sellar"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              void profileQuery.refetch();
              void overviewQuery.refetch();
            }}
            disabled={overviewQuery.isFetching}
            data-testid="verification-refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Actualizar
          </Button>
        </div>

        {recompute.isSuccess ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="verification-sealed"
          >
            Época sellada {recompute.data.run.day} → {recompute.data.run.toDay}{" "}
            ·{" "}
            <span className="font-mono">
              {recompute.data.run.measurementHash.slice(0, 12)}…
            </span>
          </p>
        ) : null}

        {recompute.isError ? (
          <p
            className="flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400"
            data-testid="verification-recompute-error"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            No se pudo sellar el veredicto
            {recomputeError?.status === 409
              ? `: ${recomputeError.message ?? "época ya sellada o sin datos medibles"}`
              : "."}
          </p>
        ) : null}

        {overviewQuery.isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="verification-loading"
          >
            Cargando veredictos…
          </p>
        ) : null}

        {overviewQuery.isError ? (
          <p
            className="text-sm text-destructive"
            data-testid="verification-error"
          >
            No se pudo leer la verificación.
          </p>
        ) : null}

        {!overviewQuery.isLoading && !latest ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="verification-empty"
          >
            Sin veredictos sellados todavía. Cuando existan artefactos as-run de
            épocas completas, «Recalcular y sellar» compone la cohorte.
          </p>
        ) : null}

        {latest ? <VerdictView run={latest} /> : null}
      </CardContent>
    </Card>
  );
}
