/**
 * AUTO · ESTUDIO — bloque «5 · Cadena y resultado (evidencia durable)» por valor.
 *
 * Demuestra, sin fabricar:
 *   1. qué estrategia se EJECUTÓ (identidad sellada por el ciclo) vs la declarada;
 *   2. por qué esa y no otra (puesto, top del ranking, activo mejor puntuado y foto TOP3);
 *   3. qué señal/vela la originó (`planId`/`signalId`, `asOfBarDate`, hora de cálculo);
 *   4. qué entrada/salida tenía (todo de `TradePlan`, nunca inferido del gráfico);
 *   5. qué pasó realmente (9 etapas; un hueco es «Sin dato todavía», jamás `0`);
 *   6. qué evidencia DÍA-D y suficiencia hay (veredicto del gate, K, expectancy).
 *
 * La cadena es HISTÓRICA del valor: se rotula como no atribuida salvo identidad estable.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type {
  EstudioChainCycleV1,
  EstudioChainResponseV1,
  EstudioChainValueV1,
  EstudioDailyPlanV1,
  EstudioDailyValueV1,
} from "@bolsa/shared";
import { ESTUDIO_CHAIN_STEPS } from "@bolsa/shared";
import { describeAttribution } from "@bolsa/shared";
import { absentDataLabel, isAbsent } from "@/components/absent-data";
import { Button } from "@/components/ui/button";
import {
  CHAIN_NOT_ATTRIBUTED_LABEL,
  diaDValueDay,
} from "@/features/auto-monitor/use-estudio-chain";
import {
  diaDValueReplayQueryKey,
  useDiaDValueReplayJob,
} from "@/features/auto-monitor/use-dia-d-value-replay";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type AuditValue = {
  resultR?: {
    verdict?: string | null;
    verdictReason?: string | null;
    evidenceQuality?: string | null;
    expectancyR?: number | null;
    hitRate?: number | null;
    realizedRTotal?: number | null;
    measuredCycles?: number;
    daysCovered?: number;
    measured?: boolean;
    sampleFloor?: number;
  };
  money?: { trades?: number } | null;
  unmeasured?: string[];
};

type StrategyLike = {
  presetKey?: string | null;
  version?: string | null;
  presetKeyAmbiguous?: boolean;
  versionAmbiguous?: boolean;
};

function fmtPrice(value: number | null | undefined): string {
  return isAbsent(value) ? absentDataLabel() : (value as number).toFixed(2);
}

function fmtR(value: number | null | undefined): string {
  if (isAbsent(value)) return absentDataLabel();
  const numeric = value as number;
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}R`;
}

function textOrAbsent(value: string | null | undefined): string {
  return value && value.trim() ? value : absentDataLabel();
}

/** La versión se publica como la declara la evidencia: ``v1`` no se convierte en ``vv1``. */
function versionLabel(value: string | null | undefined): string {
  const text = textOrAbsent(value);
  if (!value || !value.trim()) return text;
  return /^v/i.test(text) ? text : `v${text}`;
}

/** `null` no es «no»: no se puede afirmar con la evidencia disponible. */
function flagLabel(
  value: boolean | null | undefined,
  yes = "Sí",
  no = "No",
): string {
  if (value === true) return yes;
  if (value === false) return no;
  return "Sin dato (no se puede afirmar)";
}

function latestCycle(
  value: EstudioChainValueV1 | undefined,
): EstudioChainCycleV1 | null {
  const cycles = value?.cycles ?? [];
  return cycles.length > 0
    ? (cycles[cycles.length - 1] as EstudioChainCycleV1)
    : null;
}

function StrategyLine({ strategy }: { strategy: StrategyLike | undefined }) {
  if (!strategy?.presetKey && !strategy?.version) {
    return (
      <span className="text-muted-foreground">
        {absentDataLabel()}: el valor no declara identidad única
        {strategy?.presetKeyAmbiguous
          ? " (AMBIGUA: varios ciclos con identidades distintas)"
          : ""}
      </span>
    );
  }
  return (
    <span className="font-mono">
      {textOrAbsent(strategy?.presetKey)} · {versionLabel(strategy?.version)}
      {strategy?.presetKeyAmbiguous ? " · identidad AMBIGUA" : ""}
    </span>
  );
}

function PlanOutcome({ plan }: { plan: EstudioDailyPlanV1 | null }) {
  if (!plan) {
    return (
      <p className="text-[11px] text-muted-foreground">
        {absentDataLabel()}: no hay `TradePlan` para este valor.
      </p>
    );
  }
  return (
    <dl
      className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] sm:grid-cols-4"
      data-testid="estudio-chain-plan-levels"
    >
      <div>
        <dt className="text-muted-foreground">Entrada</dt>
        <dd className="font-mono tabular-nums">{fmtPrice(plan.entry)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Stop</dt>
        <dd className="font-mono tabular-nums">
          {fmtPrice(plan.structuralStop)}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">Objetivos 1/2</dt>
        <dd className="font-mono tabular-nums">
          {fmtPrice(plan.target1)} / {fmtPrice(plan.target2)}
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
      <div className="sm:col-span-2">
        <dt className="text-muted-foreground">Condición de entrada</dt>
        <dd className="font-mono">{textOrAbsent(plan.entryCondition)}</dd>
      </div>
      <div className="sm:col-span-2">
        <dt className="text-muted-foreground">Caduca</dt>
        <dd className="font-mono">{textOrAbsent(plan.expiresAt)}</dd>
      </div>
    </dl>
  );
}

function ChainSteps({ cycle }: { cycle: EstudioChainCycleV1 }) {
  return (
    <ol
      className="flex flex-wrap gap-1"
      data-testid="estudio-chain-steps"
      data-complete={String(cycle.chain.complete)}
    >
      {ESTUDIO_CHAIN_STEPS.map((step) => {
        const reached = cycle.steps[step] === 1;
        return (
          <li
            key={step}
            data-testid="estudio-chain-step"
            data-step={step}
            data-reached={String(reached)}
            className={cn(
              "rounded px-1 py-0.5 font-mono text-[9px] uppercase tracking-wide",
              reached
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "bg-muted text-muted-foreground",
            )}
            title={
              reached
                ? "Hecho durable presente"
                : `Sin dato todavía (${cycle.chain.notReached[step] ?? "unknown"})`
            }
          >
            {step}
            {reached ? "" : " · sin dato"}
          </li>
        );
      })}
    </ol>
  );
}

function DiaDValueVerification({
  value,
  chainValue,
}: {
  value: EstudioDailyValueV1;
  chainValue: EstudioChainValueV1 | undefined;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const symbol = value.symbol?.trim().toUpperCase() ?? null;
  const { day, source } = diaDValueDay({
    chainValue,
    barDate: value.asOfBarDate,
  });
  const [open, setOpen] = useState(false);
  const replay = useDiaDValueReplayJob(day, symbol);

  const artifactQuery = useQuery({
    queryKey: diaDValueReplayQueryKey(effectiveAccountId, day, symbol),
    queryFn: () => api.getAutoDiaDReplayValue(day as string, symbol as string),
    enabled: Boolean(open && effectiveAccountId && day && symbol),
    retry: false,
    staleTime: 10_000,
  });

  if (!symbol) {
    return (
      <p
        className="text-[10px] text-muted-foreground"
        data-testid="estudio-chain-dia-d-no-symbol"
      >
        {absentDataLabel()}: el parte no declara símbolo para este instrumento.
      </p>
    );
  }

  const artifact = artifactQuery.data ?? null;
  const disabled =
    !replay.hasAccount ||
    !day ||
    replay.isRunning ||
    replay.isQueuing ||
    Boolean(replay.occupiedBy);
  const dayLabel =
    source === "cycle"
      ? `día de entrada del ciclo (${day})`
      : source === "bar"
        ? `vela del parte (${day})`
        : "sin día declarado";

  return (
    <div
      className="mt-1 space-y-1 rounded border border-border/60 bg-muted/20 p-2"
      data-testid="estudio-chain-dia-d"
      data-day={day ?? ""}
      data-day-source={source}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          DÍA-D del valor
        </span>
        <span className="text-[10px] text-muted-foreground">{dayLabel}</span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          data-testid="estudio-chain-dia-d-verify"
          disabled={disabled}
          onClick={() => {
            setOpen(true);
            replay.run();
          }}
        >
          {replay.isRunning || replay.isQueuing
            ? "Verificando…"
            : "Verificar DÍA-D de este valor"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          data-testid="estudio-chain-dia-d-toggle"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? "Ocultar evidencia" : "Ver evidencia DÍA-D del valor"}
        </Button>
      </div>

      <p
        className="text-[10px] text-muted-foreground"
        data-testid="estudio-chain-dia-d-scope"
      >
        Día solicitado {day ?? absentDataLabel()} · origen: {source} · cuenta{" "}
        {effectiveAccountId ?? absentDataLabel()}. Ruta de solo lectura:
        consultar el artefacto no ejecuta el replay.
      </p>

      {replay.occupiedBy ? (
        <p
          role="alert"
          data-testid="estudio-chain-dia-d-occupied"
          data-slot-state={replay.slot?.state ?? "unknown"}
          className="text-[10px] text-amber-600 dark:text-amber-400"
        >
          {replay.slotMessage ??
            `Hay otra verificación en curso para ${replay.occupiedBy} el mismo día: la cola serializa una por (cuenta, día). Este valor se podrá verificar cuando termine.`}
        </p>
      ) : null}

      {replay.job ? (
        <p
          data-testid="estudio-chain-dia-d-job"
          data-status={replay.job.status}
          className="text-[10px] text-muted-foreground"
        >
          job {replay.job.status} · {replay.job.day} · intento{" "}
          {replay.job.attempt}
          {replay.job.error ? ` · ${replay.job.error}` : ""}
        </p>
      ) : null}

      {replay.runError || replay.jobError ? (
        <p
          role="alert"
          data-testid="estudio-chain-dia-d-error"
          className="text-[10px] text-destructive"
        >
          No se pudo consultar la verificación:{" "}
          {replay.runError instanceof Error
            ? replay.runError.message
            : replay.jobError instanceof Error
              ? replay.jobError.message
              : "error desconocido"}
          . Un fallo NO borra el artefacto anterior.
        </p>
      ) : null}

      {open ? (
        artifactQuery.isError ? (
          <p
            role="alert"
            data-testid="estudio-chain-dia-d-artifact-error"
            className="text-[10px] text-destructive"
          >
            No se pudo leer el artefacto del valor (esto no implica que no
            exista).
          </p>
        ) : artifact && artifact.available ? (
          <div
            data-testid="estudio-chain-dia-d-artifact"
            className="space-y-0.5 text-[10px]"
          >
            <p className="font-mono">
              verificación {textOrAbsent(artifact.summary?.verdict)} · pasos{" "}
              {artifact.summary?.steps ?? absentDataLabel()} · conciliación{" "}
              {artifact.summary?.match ?? absentDataLabel()}
            </p>
            <p
              className="text-muted-foreground"
              data-testid="estudio-chain-dia-d-artifact-meta"
              data-artifact-account={String(artifact.meta?.account ?? "")}
              data-artifact-day={String(artifact.meta?.day ?? "")}
              data-artifact-watch={
                Array.isArray(artifact.meta?.watch)
                  ? (artifact.meta?.watch as unknown[]).map(String).join(",")
                  : ""
              }
            >
              artefacto {textOrAbsent(artifact.artifactModifiedAt)} · cuenta{" "}
              {String(artifact.meta?.account ?? absentDataLabel())} · día{" "}
              {String(artifact.meta?.day ?? absentDataLabel())} · watch real{" "}
              {Array.isArray(artifact.meta?.watch) &&
              (artifact.meta?.watch as unknown[]).length > 0
                ? (artifact.meta?.watch as unknown[]).map(String).join(",")
                : absentDataLabel()}
            </p>
          </div>
        ) : artifact ? (
          <p
            data-testid="estudio-chain-dia-d-artifact-absent"
            className="text-[10px] text-muted-foreground"
          >
            {absentDataLabel()}: este valor todavía no tiene verificación DÍA-D
            propia
            {artifact.notes?.length ? ` (${artifact.notes.join(", ")})` : ""}.
          </p>
        ) : artifactQuery.isLoading ? (
          <p className="text-[10px] text-muted-foreground">
            Leyendo evidencia DÍA-D…
          </p>
        ) : null
      ) : null}
    </div>
  );
}

export function EstudioChainEvidence({
  value,
  chainValue,
  chain,
  chainLoading,
  chainFailed,
  audit,
  auditWindow,
}: {
  value: EstudioDailyValueV1;
  chainValue: EstudioChainValueV1 | undefined;
  chain: EstudioChainResponseV1 | null;
  chainLoading: boolean;
  chainFailed: boolean;
  audit: AuditValue | undefined;
  auditWindow: string | null;
}) {
  const cycle = latestCycle(chainValue);
  const bestScored = chain?.bestScored ?? null;
  const top3Rows = Array.isArray(bestScored?.rows)
    ? (bestScored?.rows as Array<Record<string, unknown>>)
    : [];
  const resultR = audit?.resultR ?? null;
  const verdict = resultR?.verdict ?? null;
  // Atribución declarada por el servidor (igualdad de ids durables). Sin estado ⇒ hueco:
  // la leyenda histórica se mantiene y NO se infiere por símbolo.
  const attribution = cycle?.attribution ?? null;
  const attributionState = attribution?.state ?? "unmeasured";
  const attributionLabel = attribution
    ? describeAttribution(attribution)
    : CHAIN_NOT_ATTRIBUTED_LABEL;

  return (
    <section
      className="sm:col-span-2 space-y-1 border-t border-border/60 pt-2"
      data-testid="estudio-daily-value-chain"
      data-chain-measured={String(Boolean(chainValue?.measured))}
    >
      <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        5 · Cadena y resultado (evidencia durable)
      </h4>
      <p
        className="text-[9px] text-muted-foreground"
        data-testid="estudio-chain-attribution"
        data-attribution-state={attributionState}
      >
        {attributionLabel}
      </p>

      {chainFailed ? (
        <p
          data-testid="estudio-chain-error-inline"
          className="text-[10px] text-muted-foreground"
        >
          Evidencia de cadena no disponible (ver el error arriba). Esto{" "}
          <strong>no</strong> significa que no exista.
        </p>
      ) : chainLoading ? (
        <p
          className="text-[10px] text-muted-foreground"
          data-testid="estudio-chain-loading"
        >
          Leyendo la cadena durable…
        </p>
      ) : !chainValue ? (
        <p
          data-testid="estudio-chain-absent"
          className="text-[11px] text-muted-foreground"
        >
          {absentDataLabel()}: el valor no aparece en la evidencia de cadena de
          la cuenta.
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          <section data-testid="estudio-chain-strategy">
            <h5 className="text-[10px] font-semibold text-muted-foreground">
              Estrategia e indicadores
            </h5>
            <p className="text-[11px]">
              Ejecutada (ciclo):{" "}
              {cycle ? (
                <span
                  className="font-mono"
                  data-testid="estudio-chain-executed-strategy"
                >
                  {textOrAbsent(cycle.executed.strategyPresetKey)} ·{" "}
                  {versionLabel(cycle.executed.strategyVersion)}
                </span>
              ) : (
                <span className="text-muted-foreground">
                  {absentDataLabel()}: sin ciclo durable
                </span>
              )}
            </p>
            <p className="text-[11px]">
              Declarada por el valor:{" "}
              <StrategyLine strategy={chainValue.strategy} />
            </p>
            <p className="text-[10px] text-muted-foreground">
              Contraste DÍA-D:{" "}
              <StrategyLine strategy={chainValue.strategyDiaD} />
            </p>
          </section>

          <section data-testid="estudio-chain-why">
            <h5 className="text-[10px] font-semibold text-muted-foreground">
              Por qué esa y no otra · ranking del día
            </h5>
            <p
              className="text-[9px] text-muted-foreground"
              data-testid="estudio-chain-why-scope"
            >
              Es una clasificación (puesto en la foto del día), no una
              validación estadística.
            </p>
            {cycle ? (
              <>
                <p className="font-mono text-[11px]">
                  puesto{" "}
                  {isAbsent(cycle.executedVsBest.executedRank)
                    ? absentDataLabel()
                    : cycle.executedVsBest.executedRank}{" "}
                  · top del ranking:{" "}
                  {flagLabel(cycle.executedVsBest.executedIsTopRanked)} · activo
                  mejor puntuado:{" "}
                  {flagLabel(cycle.executedVsBest.executedIsBestScoredAsset)}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Mejor puntuada del ranking:{" "}
                  <span className="font-mono">
                    {textOrAbsent(cycle.executedVsBest.bestScoredAssetId)}
                  </span>{" "}
                  · preset{" "}
                  <span className="font-mono">
                    {cycle.executedVsBest.bestScoredPresetKey ||
                    cycle.executedVsBest.bestScoredStrategyVersion ? (
                      <>
                        {textOrAbsent(cycle.executedVsBest.bestScoredPresetKey)}{" "}
                        ·{" "}
                        {versionLabel(
                          cycle.executedVsBest.bestScoredStrategyVersion,
                        )}
                      </>
                    ) : (
                      absentDataLabel()
                    )}
                  </span>{" "}
                  · misma estrategia que la ejecutada:{" "}
                  {flagLabel(cycle.executedVsBest.presetMatch)}
                  {cycle.executedVsBest.versionMatch !== undefined
                    ? ` · misma versión: ${flagLabel(cycle.executedVsBest.versionMatch)}`
                    : ""}
                  {cycle.executedVsBest.bestScoredPresetKey ||
                  cycle.executedVsBest.bestScoredStrategyVersion
                    ? ""
                    : " (la foto no declara identidad: no se empareja por estrategia)"}
                  {cycle.executedVsBest.strategyMeasurement === "PARTIAL"
                    ? " · identidad: parcial (solo se pudo contrastar uno de preset/versión)"
                    : ""}
                </p>
              </>
            ) : (
              <p className="text-[11px] text-muted-foreground">
                {absentDataLabel()}: sin ciclo no hay comparación de
                estrategias.
              </p>
            )}
            {top3Rows.length > 0 ? (
              <p
                className="font-mono text-[10px] text-muted-foreground"
                data-testid="estudio-chain-top3"
              >
                TOP3:{" "}
                {top3Rows
                  .map((row) => {
                    const preset =
                      typeof row.strategyPresetKey === "string"
                        ? row.strategyPresetKey.trim()
                        : "";
                    const version =
                      typeof row.strategyVersion === "string"
                        ? row.strategyVersion.trim()
                        : "";
                    // La identidad se ANEXA solo si la foto la declara; si no, se omite (la
                    // línea no insinúa un ganador que la evidencia no sella).
                    const identity =
                      preset || version
                        ? ` · ${preset || absentDataLabel()}${
                            version ? ` ${version}` : ""
                          }`
                        : "";
                    return `#${String(row.rank ?? "?")} ${String(
                      row.assetId ?? "?",
                    )}${
                      row.combined != null
                        ? ` (${Number(row.combined).toFixed(2)})`
                        : ""
                    }${identity}`;
                  })
                  .join(" · ")}
              </p>
            ) : (
              <p className="text-[10px] text-muted-foreground">
                Foto TOP3: {absentDataLabel()}
              </p>
            )}
          </section>

          <section data-testid="estudio-chain-signal">
            <h5 className="text-[10px] font-semibold text-muted-foreground">
              Señal y vela
            </h5>
            <p className="font-mono text-[11px]">
              señal {textOrAbsent(value.strategy?.signalId)} · plan{" "}
              {textOrAbsent(value.strategy?.planId)} · oportunidad{" "}
              {textOrAbsent(cycle?.opportunityId)}
            </p>
            {cycle?.dailyProposal ? (
              <p
                className="font-mono text-[10px] text-muted-foreground"
                data-testid="estudio-chain-daily-proposal"
                data-proposal-source={cycle.dailyProposal.source ?? "unknown"}
              >
                propuesta adoptada: día{" "}
                {textOrAbsent(
                  cycle.dailyProposal.day ?? cycle.dailyProposal.barDate,
                )}{" "}
                · plan {textOrAbsent(cycle.dailyProposal.planId)} · señal{" "}
                {textOrAbsent(cycle.dailyProposal.signalId)} · origen{" "}
                {textOrAbsent(cycle.dailyProposal.source)}
              </p>
            ) : null}
            <p className="text-[10px] text-muted-foreground">
              {value.asOfBarDate
                ? `vela ${value.asOfBarDate}`
                : "vela no verificada"}{" "}
              ·{" "}
              {value.computedAt
                ? `calculado ${value.computedAt}`
                : "hora de cálculo sin dato"}
            </p>
          </section>

          <section data-testid="estudio-chain-levels">
            <h5 className="text-[10px] font-semibold text-muted-foreground">
              Entrada y salida (TradePlan)
            </h5>
            <PlanOutcome plan={value.plan ?? null} />
          </section>

          <section
            data-testid="estudio-chain-operation"
            className="sm:col-span-2"
          >
            <h5 className="text-[10px] font-semibold text-muted-foreground">
              Operación simulada (9 etapas)
            </h5>
            {cycle ? (
              <>
                <ChainSteps cycle={cycle} />
                <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                  {cycle.entryDay ?? absentDataLabel()} →{" "}
                  {cycle.exitDay ?? absentDataLabel()} · P&amp;L cierre{" "}
                  {textOrAbsent(cycle.pnl.cycleClosedPnl)} · liquidación{" "}
                  {textOrAbsent(cycle.pnl.settlementPnl)} · conciliado{" "}
                  {flagLabel(cycle.pnl.reconciled)}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  DÍA-D enlazado al ciclo:{" "}
                  {flagLabel(cycle.executedVsDiaD.matches)} · enlazable{" "}
                  {flagLabel(cycle.diaDLink.linkable)}
                </p>
              </>
            ) : (
              <p className="text-[11px] text-muted-foreground">
                {absentDataLabel()}: el valor no tiene ciclos durables
                {chainValue.unmeasured.length > 0
                  ? ` (${chainValue.unmeasured.join(", ")})`
                  : ""}
                .
              </p>
            )}
          </section>

          <section
            data-testid="estudio-chain-sufficiency"
            className="sm:col-span-2"
          >
            <h5 className="text-[10px] font-semibold text-muted-foreground">
              DÍA-D y suficiencia
            </h5>
            {resultR && resultR.measured ? (
              <p className="font-mono text-[10px]">
                veredicto {textOrAbsent(verdict)} · K=
                {resultR.measuredCycles ?? absentDataLabel()} · expectancy{" "}
                {fmtR(resultR.expectancyR)} · R total{" "}
                {fmtR(resultR.realizedRTotal)} · evidencia{" "}
                {textOrAbsent(resultR.evidenceQuality)} · ventana{" "}
                {textOrAbsent(auditWindow)} · CI {absentDataLabel()} (no
                declarado por el audit)
              </p>
            ) : (
              <p className="text-[10px] text-muted-foreground">
                {absentDataLabel()}: este valor no está medido en la ventana
                {auditWindow ? ` ${auditWindow}` : ""}
                {resultR?.verdictReason ? ` (${resultR.verdictReason})` : ""}.
              </p>
            )}
            <p
              className="text-[10px] text-muted-foreground"
              data-testid="estudio-chain-global-validation"
              data-verdict={
                resultR?.measured === true && verdict ? verdict : "NOT_MEASURED"
              }
            >
              Veredicto del gate para este valor
              {auditWindow ? ` en la ventana ${auditWindow}` : ""}:{" "}
              <strong>
                {resultR?.measured === true && verdict
                  ? verdict
                  : absentDataLabel()}
              </strong>
              . No se generaliza a la ventana ni a la cartera. Esta vista no
              emite <code>CONFIRMED</code>: eso es OPERACIÓN, no software.
            </p>
          </section>
        </div>
      )}

      <DiaDValueVerification value={value} chainValue={chainValue} />
    </section>
  );
}
