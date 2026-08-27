/**
 * Cockpit Mercado — ¿Qué hago? sobre el valor del gráfico activo.
 *
 * Panel contextual por fase (V1.23 Fase 3): VIGILAR / DESCUBIERTO no muestran
 * niveles (anti-ruido); PREPARADA → POSICIÓN muestran `OperationalPlanView`
 * (misma proyección que Hoy / Journal). Confirm sigue siendo la firma.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §3
 */

import { useState } from "react";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import type { InstrumentDailyOpinionV1 } from "@bolsa/shared";
import {
  formatConfirmDrawerCtaLabel,
  openConfirmDrawer,
} from "@/features/confirm/confirm-drawer";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { cn } from "@/lib/utils";
import {
  MERCADO_COCKPIT_PHASE_LABEL,
  mercadoCockpitNoLevelsCopy,
  mercadoCockpitPrimaryCta,
  type MercadoCockpitPhase,
} from "@/features/trading/operativa-cockpit-phase";
import { PositionExitDrawerActions } from "@/features/trading/position-exit-drawer-actions";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";

type OperativaCockpitCardProps = {
  instrumentId: string | null;
  symbol: string;
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
    case "confirmada":
      return "border-teal-600/40 bg-teal-500/5";
    case "disparada":
    case "propuesta":
      return "border-amber-600/40 bg-amber-500/5";
    case "preparada":
      return "border-sky-600/40 bg-sky-500/5";
    case "bloqueada":
      return "border-rose-600/40 bg-rose-500/5";
    case "caducada":
      return "border-amber-700/35 bg-amber-500/5";
    case "descubierto":
      return "border-violet-600/30 bg-violet-500/5";
    default:
      return "border-border/60 bg-muted/15";
  }
}

export function OperativaCockpitCard({
  instrumentId,
  symbol,
  opinion,
  opinionLoading,
  onAddToEstudio,
  onPropose,
  proposePending,
  canPropose = true,
  className,
}: OperativaCockpitCardProps) {
  const [whyOpen, setWhyOpen] = useState(false);
  const context = useInstrumentOperationalContext(instrumentId);
  const operationsOpen = useTradingLayoutStore((s) => s.operationsOpen);
  const toggleOperations = useTradingLayoutStore((s) => s.toggleOperations);

  const { phase, plan, study, position } = context;
  const primaryLabel = mercadoCockpitPrimaryCta(phase);
  const noLevelsCopy = mercadoCockpitNoLevelsCopy(phase);

  if (!instrumentId) {
    return (
      <div
        className={cn(
          "rounded-md border border-border/60 px-3 py-2 text-xs text-muted-foreground",
          className,
        )}
        data-testid="operativa-cockpit"
        data-phase="sin_contexto"
      >
        {noLevelsCopy}
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
            Universo: {context.inEstudio ? "Estudio" : "fuera de Estudio"}
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

      {context.loading ? (
        <p className="text-[11px] text-muted-foreground">Cargando plan…</p>
      ) : context.showsPlanLevels ? (
        <OperationalPlanView
          plan={plan}
          testId={`operativa-cockpit-plan-${symbol}`}
        />
      ) : (
        <p
          className="text-[11px] leading-snug text-muted-foreground"
          data-testid="operativa-cockpit-no-levels"
        >
          {noLevelsCopy ?? plan.emptyCopy}
        </p>
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

        {phase === "propuesta" ||
        (phase === "disparada" && context.confirmQueueCount > 0) ? (
          <button
            type="button"
            className="rounded-md border border-amber-700/35 bg-amber-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-amber-500/20"
            onClick={() => openConfirmDrawer()}
            data-testid="operativa-cockpit-cta-confirm"
          >
            {formatConfirmDrawerCtaLabel(context.confirmQueueCount)}
          </button>
        ) : null}

        {phase === "confirmada" ? (
          <button
            type="button"
            className="rounded-md border border-teal-700/35 bg-teal-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-teal-500/20"
            onClick={() => {
              if (!operationsOpen) toggleOperations();
            }}
            data-testid="operativa-cockpit-cta-operaciones"
            title="Firma hecha · fill pendiente — mira Operaciones abajo"
          >
            {primaryLabel}
          </button>
        ) : null}

        {phase === "posicion" && position ? (
          <PositionExitDrawerActions position={position} showMaintain />
        ) : null}

        {phase === "vigilar" ||
        phase === "bloqueada" ||
        phase === "caducada" ? (
          <button
            type="button"
            className="w-fit rounded-md border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
            onClick={() => setWhyOpen(true)}
            data-testid={
              phase === "vigilar"
                ? "operativa-cockpit-cta-vigilar"
                : `operativa-cockpit-cta-${phase}`
            }
            title={
              phase === "bloqueada"
                ? "Plan bloqueado — mira el motivo en ¿Por qué?"
                : phase === "caducada"
                  ? "Plan caducado — niveles residuales no autorizan"
                  : "Ya está en Estudio: sin disparador todavía — mira el análisis"
            }
          >
            {primaryLabel}
          </button>
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
