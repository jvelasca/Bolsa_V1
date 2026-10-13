/**
 * P2 (sello 2) — Auto · ESTUDIO: auditoría por VALOR (estrategia + porqué + señal + R + dinero).
 *
 * Read-only: compone piezas YA calculadas (feedback DÍA-D por valor + reporte financiero OOS
 * opt-in). No recalcula el motor. Honestidad: un valor sin ambas mitades sobre su suelo de
 * muestra declara «Sin dato todavía» (nunca `0`); `pointCitable = false` (banda `K`).
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";
import { autoOperacionHref } from "@/features/auto/auto-nav";
import { useAutoEstudioAudit } from "@/features/auto-monitor/use-auto-dia-d-feedback";
import {
  ESTUDIO_VALUE_LABELS,
  describeCycle,
  describeStrategy,
  describeVerdict,
  estudioValueState,
  formatPct,
  formatR,
  formatRate,
} from "@/features/auto-monitor/estudio-audit-view";

export function EstudioAuditPanel() {
  const query = useAutoEstudioAudit();
  const audit = query.data?.audit;

  if (query.isLoading) {
    return (
      <Card className="rounded-xl border border-border bg-card">
        <CardContent
          className="py-4 text-sm text-muted-foreground"
          data-testid="estudio-audit-loading"
        >
          Cargando la auditoría por valor…
        </CardContent>
      </Card>
    );
  }

  if (query.isError || !query.data?.available || !audit) {
    return (
      <Card className="rounded-xl border border-border bg-card">
        <CardContent
          className="space-y-1 py-4"
          data-testid="estudio-audit-unavailable"
        >
          <p className="text-sm text-foreground">Sin dato todavía</p>
          <p className="text-[11px] text-muted-foreground">
            No hay artefacto de feedback para esta cuenta. La auditoría por
            valor compone piezas ya calculadas; no se recalcula en vivo.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className="rounded-xl border border-border bg-card"
      data-testid="estudio-audit-panel"
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">
          Auditoría por valor de ESTUDIO
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Estrategia elegida + porqué + señal + resultado (R y dinero). Fuente:
          artefacto de feedback de la ventana {query.data.window}. Un valor solo
          se declara «medido» si R y dinero alcanzan su suelo de muestra.
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
          <span>{audit.summary.values} valores</span>
          <span>· {audit.summary.measured} medidos</span>
          <span>· {audit.summary.unmeasured} sin dato</span>
          <span>
            · identidad exacta: {audit.summary.withPresetKey}/
            {audit.summary.values}
          </span>
          <span
            className="rounded bg-muted px-1.5 py-0.5"
            data-testid="estudio-audit-point-citable"
          >
            {audit.pointCitable
              ? "Punto citable"
              : "Banda, no punto (pointCitable = false)"}
          </span>
        </div>

        {audit.values.length === 0 ? (
          <p
            className="text-[11px] text-muted-foreground"
            data-testid="estudio-audit-empty"
          >
            Sin valores en la ventana.
          </p>
        ) : (
          <ul className="space-y-2">
            {audit.values.map((value) => {
              const state = estudioValueState(value.measured);
              const gaps = value.unmeasured ?? [];
              const cycles = value.cycles ?? [];
              return (
                <li
                  key={value.symbol}
                  data-testid="estudio-audit-value"
                  data-symbol={value.symbol}
                  data-measure-state={state}
                  className="rounded-lg border border-border/60 p-2"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-mono text-sm font-semibold">
                      {value.symbol}
                    </span>
                    <span
                      data-testid="estudio-audit-value-state"
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        state === "measured"
                          ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {ESTUDIO_VALUE_LABELS[state]}
                    </span>
                  </div>

                  <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] sm:grid-cols-4">
                    <div>
                      <div className="text-muted-foreground">Estrategia</div>
                      <div
                        className="font-mono"
                        data-testid="estudio-audit-value-strategy"
                      >
                        {describeStrategy(value.strategy)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Señal</div>
                      <div className="font-mono">
                        {value.signal.cycles} ciclos ·{" "}
                        {value.signal.measuredCycles} medidos
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Resultado (R)</div>
                      <div
                        className="font-mono"
                        data-testid="estudio-audit-value-r"
                        data-measured={String(value.resultR.measured)}
                      >
                        {formatR(value.resultR.expectancyR)} · hit{" "}
                        {formatRate(value.resultR.hitRate)}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {describeVerdict(value.resultR)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Dinero (OOS)</div>
                      <div
                        className="font-mono"
                        data-testid="estudio-audit-value-money"
                        data-measured={String(value.money.measured)}
                      >
                        {formatPct(value.money.netReturnPct)} ·{" "}
                        {value.money.trades} op.
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        estrés {formatPct(value.money.netReturnPctAtStress)} ·
                        DD {formatPct(value.money.maxDrawdownPct)}
                      </div>
                    </div>
                  </div>

                  {cycles.length > 0 ? (
                    <ul
                      className="mt-1 space-y-0.5 text-[10px]"
                      data-testid="estudio-audit-value-cycles"
                    >
                      {cycles.map((cycle) => (
                        <li
                          key={cycle.cycleId}
                          className="flex flex-wrap items-center gap-2"
                          data-testid="estudio-audit-value-cycle"
                          data-cycle-id={cycle.cycleId}
                        >
                          <span className="font-mono text-muted-foreground">
                            {describeCycle(cycle)}
                          </span>
                          <Link
                            to={autoOperacionHref(cycle.cycleId)}
                            className="underline hover:text-primary"
                            data-testid="estudio-audit-value-cycle-link"
                          >
                            Ver operación →
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p
                      className="mt-1 text-[10px] text-muted-foreground"
                      data-testid="estudio-audit-value-cycles-gap"
                    >
                      Señal sin ciclos enlazables (Sin dato todavía)
                    </p>
                  )}

                  {gaps.length > 0 ? (
                    <ul
                      className="mt-1 list-disc pl-4 text-[10px] text-muted-foreground"
                      data-testid="estudio-audit-value-gap"
                    >
                      {gaps.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        <p className="text-[10px] text-muted-foreground">
          {audit.pointCitableReason}
        </p>
      </CardContent>
    </Card>
  );
}
