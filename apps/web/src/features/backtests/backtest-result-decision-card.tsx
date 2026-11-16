/**
 * Resultado de un run · primer nivel de decisión (R4 · P2 + P3).
 *
 * El resultado del LAB ya no enseña solo un Sharpe: declara **qué estrategia es**
 * y **con qué indicadores se sostiene** (P3), y **cómo se entra y se sale** (P2)
 * sin obligar a abrir el detalle.
 *
 * Reutiliza las proyecciones existentes en vez de recalcular:
 * - `strategySlotToIndicatorDetails` (definición → preset → hueco declarado),
 * - `buildInstrumentDailyAnalysis` (fase, plan, niveles y `gaps`).
 *
 * `UNKNOWN ≠ 0`: un hueco se declara («Sin dato todavía», «Sin plan declarado
 * todavía») y distingue `WATCH` (`vigilar`), `BLOCKED` (`bloqueada`) y `EXPIRED`
 * (`caducada`) de la simple ausencia de plan.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §7 (R4)
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BACKTEST_STRATEGIES,
  buildInstrumentDailyAnalysis,
  strategySlotToIndicatorDetails,
  type BacktestRunDetailDto,
  type InstrumentStrategyTopSlotV1,
  type ResearchTrialDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { absentDataLabel, formatOrAbsent } from "@/components/absent-data";
import { formatPrice } from "@/features/charts/chart-utils";
import { formatNumberWith } from "@/lib/format";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";

type Props = {
  detail: BacktestRunDetailDto;
  linkedTrial?: ResearchTrialDto | null;
  /** Último cierre disponible (distancia a la entrada); `null` = sin serie. */
  markPrice?: number | null;
  className?: string;
};

function strategyLabelOf(
  detail: BacktestRunDetailDto,
  trial?: ResearchTrialDto | null,
) {
  return (
    trial?.strategyName ??
    BACKTEST_STRATEGIES[detail.strategyType]?.label ??
    detail.strategyType
  );
}

export function BacktestResultDecisionCard({
  detail,
  linkedTrial = null,
  markPrice = null,
  className,
}: Props) {
  const strategyLabel = strategyLabelOf(detail, linkedTrial);
  const strategyDefinitionId =
    detail.strategyDefinitionId ?? linkedTrial?.strategyDefinitionId ?? null;

  const definitionQuery = useQuery({
    queryKey: ["strategy", strategyDefinitionId],
    queryFn: () => api.getStrategy(strategyDefinitionId!),
    enabled: Boolean(strategyDefinitionId),
    staleTime: 60_000,
  });
  const definition = definitionQuery.data?.data?.definition ?? null;

  /**
   * El run es su propio «#1»: se proyecta como slot para reutilizar la fuente
   * única de indicadores (definición → preset → hueco declarado).
   */
  const slot = useMemo<InstrumentStrategyTopSlotV1>(
    () => ({
      rank: 1,
      label: strategyLabel,
      strategyType: detail.strategyType,
      strategyDefinitionId,
      stars: 0,
      score: 0,
      source: "user",
    }),
    [strategyLabel, detail.strategyType, strategyDefinitionId],
  );

  const indicators = useMemo(
    () => strategySlotToIndicatorDetails({ slot, definition }),
    [slot, definition],
  );

  const operationalContext = useInstrumentOperationalContext(
    detail.instrumentId,
  );
  const analysis = useMemo(
    () =>
      buildInstrumentDailyAnalysis({
        instrumentId: detail.instrumentId,
        inEstudio: operationalContext.inEstudio,
        study: operationalContext.study,
        phase: operationalContext.phase,
        showsPlanLevels: operationalContext.showsPlanLevels,
        plan: operationalContext.plan,
        trailing: operationalContext.trailing,
        markPrice,
        slot,
        definition,
        reasons: [],
        evidenceLevel: null,
        stabilityLabel: null,
      }),
    [
      detail.instrumentId,
      operationalContext.inEstudio,
      operationalContext.study,
      operationalContext.phase,
      operationalContext.showsPlanLevels,
      operationalContext.plan,
      operationalContext.trailing,
      markPrice,
      slot,
      definition,
    ],
  );

  const { entry, exit } = analysis;
  const planKnown =
    !operationalContext.loading && !operationalContext.studiesError;
  const noPlan = planKnown && !operationalContext.plan.hasPlan;
  const stateLabel = entry?.stateLabel ?? (exit ? "Posición" : null);

  return (
    <section
      className={cn(
        "rounded-xl border border-border/70 bg-muted/20 px-3 py-2",
        className,
      )}
      data-testid="backtest-decision-first-level"
      data-phase={entry?.state ?? (exit ? "posicion" : "desconocido")}
      aria-label="Estrategia y plan del resultado"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Cómo se opera
          </p>
          {/* P3 · estrategia #1 + especificación de indicadores, en primer nivel. */}
          <p className="text-sm font-medium text-foreground">
            #{analysis.tracking.strategyRank ?? 1}{" "}
            {analysis.tracking.strategyLabel ?? strategyLabel}
          </p>
          <p
            className="text-xs text-muted-foreground"
            data-testid="backtest-decision-indicators"
          >
            Indicadores:{" "}
            {indicators.items.length > 0
              ? indicators.items.map((item) => item.display).join(" · ")
              : absentDataLabel()}
          </p>
        </div>
        {stateLabel ? (
          <span
            className="rounded border border-border/70 bg-background/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-foreground"
            data-testid="backtest-decision-phase"
          >
            {stateLabel}
          </span>
        ) : null}
      </div>

      {/* P2 · entrada, stop y objetivos (o el hueco declarado con su motivo). */}
      <div className="mt-1.5 space-y-0.5">
        {operationalContext.loading ? (
          <p className="text-xs text-muted-foreground">
            Leyendo el plan operativo…
          </p>
        ) : operationalContext.studiesError ? (
          <p className="text-xs text-muted-foreground">
            No disponible ahora: no se pudo leer el plan operativo.
          </p>
        ) : (
          <>
            {entry && entry.entry != null ? (
              <p
                className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs tabular-nums text-foreground"
                data-testid="backtest-decision-levels"
              >
                <span>
                  Entrada <strong>{formatPrice(entry.entry)}</strong>
                </span>
                <span>Stop {formatOrAbsent(entry.stop, formatPrice)}</span>
                <span>T1 {formatOrAbsent(entry.target1, formatPrice)}</span>
                <span>T2 {formatOrAbsent(entry.target2, formatPrice)}</span>
                {entry.expectedRR != null ? (
                  <span>
                    R:R{" "}
                    {formatNumberWith(entry.expectedRR, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </span>
                ) : null}
              </p>
            ) : null}

            {exit ? (
              <p
                className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs tabular-nums text-foreground"
                data-testid="backtest-decision-levels"
              >
                <span>
                  Stop vigente {formatOrAbsent(exit.stop, formatPrice)}
                </span>
                <span>T1 {exit.target1Hint}</span>
                <span>T2 {exit.target2Hint}</span>
              </p>
            ) : null}

            {noPlan ? (
              <p
                className="text-xs text-muted-foreground"
                data-testid="backtest-decision-no-plan"
              >
                Sin plan declarado todavía
              </p>
            ) : null}
            {entry?.missing && entry.entry == null ? (
              <p className="text-xs text-muted-foreground">{entry.missing}</p>
            ) : null}
          </>
        )}
      </div>

      {analysis.gaps.length > 0 ? (
        <p
          className="mt-1 text-[11px] text-muted-foreground"
          data-testid="backtest-decision-gaps"
        >
          Falta: {analysis.gaps.join(" · ")}
        </p>
      ) : null}
    </section>
  );
}
