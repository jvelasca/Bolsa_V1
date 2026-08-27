/**
 * Cockpit Mercado — ¿Qué hago? sobre el valor del gráfico activo.
 * Proyección OperationalPlanView (misma que Hoy/Journal). No BUY gigante.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type {
  DecisionJournalStudyViewV1,
  InstrumentDailyOpinionV1,
  PositionDto,
} from "@bolsa/shared";
import {
  buildInvestmentPositionAggregate,
  buildOperationalPlanFromPosition,
  buildOperationalPlanFromStudy,
  pickPositionStudies,
  studiesByDecisionIdMap,
  studiesByInstrumentMap,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import {
  formatConfirmDrawerCtaLabel,
  openConfirmDrawer,
} from "@/features/confirm/confirm-drawer";
import {
  CONFIRM_PATH,
  hoyViewHref,
  HOY_VIEW,
} from "@/features/confirm/daily-nav";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { cn } from "@/lib/utils";
import {
  MERCADO_COCKPIT_PHASE_LABEL,
  mercadoCockpitPrimaryCta,
  resolveMercadoCockpitPhase,
  type MercadoCockpitPhase,
} from "@/features/trading/operativa-cockpit-phase";

type OperativaCockpitCardProps = {
  instrumentId: string | null;
  symbol: string;
  accountId: string | null;
  inEstudio: boolean;
  position: PositionDto | null;
  opinion?: InstrumentDailyOpinionV1 | null;
  opinionLoading?: boolean;
  onAddToEstudio?: () => void;
  onPropose?: () => void;
  proposePending?: boolean;
  canPropose?: boolean;
  className?: string;
};

function phaseTone(phase: MercadoCockpitPhase): string {
  switch (phase) {
    case "posicion":
      return "border-emerald-600/40 bg-emerald-500/5";
    case "disparada":
    case "propuesta":
      return "border-amber-600/40 bg-amber-500/5";
    case "preparada":
      return "border-sky-600/40 bg-sky-500/5";
    case "descubierto":
      return "border-violet-600/30 bg-violet-500/5";
    default:
      return "border-border/60 bg-muted/15";
  }
}

export function OperativaCockpitCard({
  instrumentId,
  symbol,
  accountId,
  inEstudio,
  position,
  opinion,
  opinionLoading,
  onAddToEstudio,
  onPropose,
  proposePending,
  canPropose = true,
  className,
}: OperativaCockpitCardProps) {
  const [whyOpen, setWhyOpen] = useState(false);
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const confirmQueueCount = queueItems.length;
  const inConfirmQueue = useMemo(() => {
    if (!instrumentId) return false;
    return queueItems.some((i) => i.payload.instrumentId === instrumentId);
  }, [instrumentId, queueItems]);

  // Same source as Mesa Hoy / Libro — projection only; no history endpoint.
  const studiesQuery = useQuery({
    queryKey: ["decision-studies", accountId, "mesa"],
    queryFn: () => api.getDecisionStudies(accountId!, { limit: 200 }),
    enabled: Boolean(accountId),
    staleTime: 30_000,
  });

  const studies = studiesQuery.data?.data?.studies ?? [];
  const byInstrument = useMemo(
    () => studiesByInstrumentMap(studies),
    [studies],
  );
  const byDecision = useMemo(() => studiesByDecisionIdMap(studies), [studies]);

  const { study, originStudy } = useMemo(() => {
    if (!instrumentId) {
      return {
        study: null as DecisionJournalStudyViewV1 | null,
        originStudy: null as DecisionJournalStudyViewV1 | null,
      };
    }
    if (position && Math.abs(Number(position.quantity ?? 0)) > 0) {
      const pair = pickPositionStudies(position, byDecision, byInstrument);
      return {
        study: pair.evolutionStudy,
        originStudy: pair.originStudy,
      };
    }
    const soft = byInstrument.get(instrumentId) ?? null;
    return { study: soft, originStudy: soft };
  }, [instrumentId, position, byInstrument, byDecision]);

  const plan = useMemo(() => {
    if (position && Math.abs(Number(position.quantity ?? 0)) > 0) {
      const aggregate = buildInvestmentPositionAggregate({
        position,
        study,
        originStudy: originStudy ?? study,
      });
      return buildOperationalPlanFromPosition({
        aggregate,
        markPrice: position.lastPrice ?? null,
      });
    }
    return buildOperationalPlanFromStudy(study);
  }, [position, study, originStudy]);

  const phase = resolveMercadoCockpitPhase({
    instrumentId,
    inEstudio,
    hasOpenPosition: Boolean(
      position && Math.abs(Number(position.quantity ?? 0)) > 0,
    ),
    inConfirmQueue,
    tradePlanStatus: study?.tradePlanStatus ?? null,
    hasOperationalPlan: study?.hasOperationalPlan === true || plan.hasPlan,
  });

  const primaryLabel = mercadoCockpitPrimaryCta(phase);

  if (!instrumentId) {
    return (
      <div
        className={cn(
          "rounded-md border border-border/60 px-3 py-2 text-xs text-muted-foreground",
          className,
        )}
        data-testid="operativa-cockpit"
      >
        Selecciona un valor en listas o gráfico.
      </div>
    );
  }

  return (
    <section
      className={cn(
        "space-y-2 rounded-md border px-3 py-2",
        phaseTone(phase),
        className,
      )}
      data-testid="operativa-cockpit"
      data-phase={phase}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold tracking-tight">
            {symbol}
          </p>
          <p className="text-[10px] text-muted-foreground">
            Universo: {inEstudio ? "Estudio" : "fuera de Estudio"}
            {opinion?.asOfBarDate ? ` · as-of ${opinion.asOfBarDate}` : null}
          </p>
        </div>
        <span
          className="rounded border border-border/70 bg-background/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
          data-testid="operativa-cockpit-phase"
        >
          {MERCADO_COCKPIT_PHASE_LABEL[phase]}
        </span>
      </div>

      {studiesQuery.isLoading ? (
        <p className="text-[11px] text-muted-foreground">Cargando plan…</p>
      ) : (
        <OperationalPlanView
          plan={plan}
          testId={`operativa-cockpit-plan-${symbol}`}
        />
      )}

      <div className="flex flex-col gap-1">
        {phase === "descubierto" && onAddToEstudio ? (
          <button
            type="button"
            className="rounded-md border border-violet-600/35 bg-violet-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-violet-500/20"
            onClick={onAddToEstudio}
            data-testid="operativa-cockpit-cta-estudio"
          >
            {primaryLabel}
          </button>
        ) : null}

        {(phase === "preparada" || phase === "disparada") && onPropose ? (
          <button
            type="button"
            disabled={proposePending || !canPropose}
            className="rounded-md border border-emerald-700/35 bg-emerald-500/10 px-2 py-1.5 text-left text-xs font-medium text-emerald-950 hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-50"
            onClick={onPropose}
            data-testid="operativa-cockpit-cta-preparar"
            title="Propose → cola Confirm · Ranking ≠ BUY"
          >
            {proposePending ? "Proponiendo…" : primaryLabel}
          </button>
        ) : null}

        {phase === "propuesta" || phase === "disparada" ? (
          <button
            type="button"
            className="rounded-md border border-amber-700/35 bg-amber-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-amber-500/20"
            onClick={() => openConfirmDrawer()}
            data-testid="operativa-cockpit-cta-confirm"
          >
            {phase === "propuesta"
              ? formatConfirmDrawerCtaLabel(confirmQueueCount)
              : "Revisar y confirmar"}
          </button>
        ) : null}

        {phase === "posicion" ? (
          <div className="flex flex-wrap gap-1">
            <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              Mantener
            </span>
            <Link
              to={hoyViewHref(HOY_VIEW.posiciones)}
              className="rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-accent"
            >
              Reducir / salir
            </Link>
            <Link
              to={CONFIRM_PATH}
              className="rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-accent"
            >
              Confirmar
            </Link>
          </div>
        ) : null}

        {phase === "vigilar" ? (
          <p className="text-[10px] text-muted-foreground">
            En supervisión. Sin disparador de entrada todavía — Ranking ≠ BUY.
          </p>
        ) : null}
      </div>

      <div className="border-t border-border/50 pt-1.5">
        <button
          type="button"
          className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
          onClick={() => setWhyOpen((v) => !v)}
          data-testid="operativa-cockpit-why"
        >
          {whyOpen ? "Ocultar ¿Por qué?" : "¿Por qué?"}
        </button>
        {whyOpen ? (
          <dl
            className="mt-1.5 space-y-1 text-[10px] text-muted-foreground"
            data-testid="operativa-cockpit-why-body"
          >
            <div className="flex justify-between gap-2">
              <dt>Dictamen</dt>
              <dd className="font-medium text-foreground">
                {opinionLoading
                  ? "…"
                  : (opinion?.stance ?? study?.opinion ?? "—")}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Gate</dt>
              <dd className="font-medium text-foreground">
                {opinion?.gateStatus ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Plan</dt>
              <dd className="font-medium text-foreground">
                {study?.tradePlanStatus ??
                  (plan.hasPlan ? plan.phaseLabel : "—")}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Fuente opinión</dt>
              <dd className="font-medium text-foreground">
                {opinion?.source ?? "—"}
              </dd>
            </div>
            <p className="pt-0.5 leading-snug">
              La IA no firma. Confirm es la única firma · trail = propuesta.
            </p>
          </dl>
        ) : null}
      </div>
    </section>
  );
}
