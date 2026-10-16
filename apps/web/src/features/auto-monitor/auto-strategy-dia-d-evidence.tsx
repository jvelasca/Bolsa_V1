/**
 * Explicación P3→P4 — bloque «Por qué se sostiene» (presentacional y PURO).
 *
 * Recibe la vista ya compuesta (`AutoStrategyDiaDExplanationV1`) y sólo la pinta. Separa en
 * primer nivel tres cosas que el usuario NO debe confundir:
 *
 *   1. la estrategia EJECUTADA del ciclo (lo que se verifica),
 *   2. el alcance REAL de la evidencia (el VALOR, no la estrategia),
 *   3. la verificación DURAble enlazada a esta operación (o su hueco declarado).
 *
 * Honestidad: un hueco se rotula con el vocabulario de `absent-data` (`UNKNOWN ≠ 0`); mientras la
 * vista está `loading`, el hueco es TRANSITORIO y no se declara ausencia.
 *
 * @see apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts
 */

import { absentDataLabel } from "@/components/absent-data";
import { MeasurementValue } from "@/components/measurement-value";
import {
  AUTO_STRATEGY_EXPLANATION_DESCRIPTION,
  AUTO_STRATEGY_EXPLANATION_SCOPE_CYCLE_LABEL,
  AUTO_STRATEGY_EXPLANATION_TITLE,
  autoStrategyExplanationLabel,
  type AutoStrategyDiaDExplanationV1,
} from "@/features/auto/auto-strategy-dia-d-explanation";
import { OOS_VERDICT_LABELS } from "@/features/auto-monitor/dia-d-evidence-aggregate-labels";

/** Medición honesta del contador: `COMPLETE` sólo con valor afirmable. */
function measurementOf(value: number | null): string {
  return value === null ? "UNKNOWN" : "COMPLETE";
}

export function AutoStrategyDiaDEvidence({
  view,
  loading = false,
}: {
  view: AutoStrategyDiaDExplanationV1;
  loading?: boolean;
}): React.ReactElement {
  // La carga la puede declarar la propia vista o el llamante: cualquiera de las dos vale, y en
  // carga un valor ausente se declara como carga (nunca como ausencia de dato).
  const isLoading = loading || view.loading;
  const placeholder = isLoading ? "Cargando…" : absentDataLabel();
  const verdictLabel = view.valueVerdict
    ? (OOS_VERDICT_LABELS[view.valueVerdict] ?? view.valueVerdict)
    : placeholder;

  return (
    <div
      className="space-y-2 rounded-md border border-dashed border-border/60 px-3 py-2"
      data-testid="auto-strategy-dia-d"
      data-verified={view.verification.state}
      data-strategy-declared={view.strategyIsDeclaredByCycle ? "true" : "false"}
    >
      <div className="space-y-0.5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {AUTO_STRATEGY_EXPLANATION_TITLE}
        </p>
        <p className="text-[11px] text-muted-foreground">
          {AUTO_STRATEGY_EXPLANATION_DESCRIPTION}
        </p>
      </div>

      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">
            Estrategia ejecutada (lo que se verifica)
          </dt>
          <dd
            className="font-medium"
            data-testid="auto-strategy-dia-d-strategy"
            data-declared-by-cycle={
              view.strategyIsDeclaredByCycle ? "true" : "false"
            }
          >
            {autoStrategyExplanationLabel(view)}
            <span className="mt-0.5 block text-[11px] font-normal text-muted-foreground">
              {view.cyclePresetKey
                ? `Clave del ciclo: ${view.cyclePresetKey} · ${view.matchLabel}`
                : "Sin dato todavía: el ciclo no declara la clave de su estrategia."}
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Verificación D→hoy</dt>
          <dd
            className="font-medium"
            data-testid="auto-strategy-dia-d-verification"
          >
            {view.verification.stateLabel}
            <span className="mt-0.5 block text-[11px] font-normal text-muted-foreground">
              {view.verification.createdAt ?? view.verification.gapReason ?? ""}
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Evidencia DÍA-D medida</dt>
          <dd data-testid="auto-strategy-dia-d-verdict">
            <span className="font-medium">{verdictLabel}</span>
            {/* Alcance DECLARADO: la evidencia agregada es del VALOR, no de la estrategia. */}
            <span
              className="mt-0.5 block text-[11px] text-muted-foreground"
              data-testid="auto-strategy-dia-d-scope"
            >
              {view.valueScopeLabel}
              {view.evidenceQuality ? ` · calidad ${view.evidenceQuality}` : ""}
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            Indicadores que la sustentan
          </dt>
          <dd data-testid="auto-strategy-dia-d-indicators">
            {view.indicators.length > 0
              ? view.indicators.join(" · ")
              : placeholder}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground">
            Muestra medida (del valor) y suelos declarados
          </dt>
          <dd
            className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs"
            data-testid="auto-strategy-dia-d-counts"
          >
            <span>
              ciclos:{" "}
              <MeasurementValue
                value={view.measuredCycles}
                measurement={measurementOf(view.measuredCycles)}
              />
            </span>
            <span>
              R medio:{" "}
              <MeasurementValue
                value={view.expectancyR}
                measurement={measurementOf(view.expectancyR)}
              />
            </span>
            <span>
              acierto:{" "}
              <MeasurementValue
                value={view.hitRate}
                measurement={measurementOf(view.hitRate)}
              />
            </span>
            <span>
              errores:{" "}
              <MeasurementValue
                value={view.errorTotal}
                measurement={measurementOf(view.errorTotal)}
              />
            </span>
            <span
              className="text-[11px] text-muted-foreground"
              data-testid="auto-strategy-dia-d-floors"
            >
              mínimos: ciclos {view.sampleFloors.minCycles ?? absentDataLabel()}{" "}
              · soportado{" "}
              {view.sampleFloors.supportedMinCycles ?? absentDataLabel()} ·
              fuerte {view.sampleFloors.strongMinCycles ?? absentDataLabel()}
            </span>
          </dd>
        </div>
      </dl>

      {/* Las CUATRO capas, sin promoción: la UI no afirma que una capa cierre la siguiente. */}
      <ul className="space-y-1" data-testid="auto-strategy-dia-d-layers">
        {view.evidence.layers.map((layer) => (
          <li
            key={layer.id}
            className="flex flex-wrap items-baseline gap-x-2 text-xs"
            data-testid="auto-strategy-dia-d-layer"
            data-layer={layer.id}
            data-state={layer.state}
          >
            <span className="w-48 shrink-0 text-muted-foreground">
              {layer.title}
            </span>
            <span className="font-medium">
              {layer.state === "measured"
                ? layer.verdictLabel
                : absentDataLabel()}
            </span>
            {layer.measurement ? (
              <span className="text-muted-foreground">{layer.measurement}</span>
            ) : null}
          </li>
        ))}
      </ul>

      {view.cycleEvidence ? (
        <p
          className="text-[11px] text-muted-foreground"
          data-testid="auto-strategy-dia-d-cycle-evidence"
        >
          {AUTO_STRATEGY_EXPLANATION_SCOPE_CYCLE_LABEL} · ciclo{" "}
          {view.cycleEvidence.cycleId} · entrada{" "}
          {view.cycleEvidence.entryDay ?? absentDataLabel()} · R{" "}
          <MeasurementValue
            value={view.cycleEvidence.realizedR}
            measurement={measurementOf(view.cycleEvidence.realizedR)}
          />
        </p>
      ) : null}

      {/* Atribución HONESTA: la evidencia agregada es del valor; sólo el ciclo es exacto. */}
      <p
        className="text-[11px] text-muted-foreground"
        data-testid="auto-strategy-dia-d-attribution"
      >
        {view.attributionNote}
      </p>

      <p
        className="text-[11px] text-muted-foreground"
        data-testid="auto-strategy-dia-d-lab"
        data-lab-active={view.lab.active ? "true" : "false"}
      >
        {view.lab.label} · {view.lab.note}
      </p>

      {isLoading ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="auto-strategy-dia-d-loading"
        >
          Cargando…
        </p>
      ) : view.gapReason ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="auto-strategy-dia-d-gap"
        >
          {view.gapReason}
        </p>
      ) : null}
    </div>
  );
}
