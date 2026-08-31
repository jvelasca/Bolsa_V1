/**
 * Fila comprimida de posición para Mesa · Hoy (P2 + V1.16).
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import type {
  DecisionJournalStudyViewV1,
  PositionStatusV1,
  ProtectPlanV1,
} from "@bolsa/shared";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  buildInvestmentPositionAggregate,
  buildMesaProtectionState,
  buildOperationalTruth,
  mapMesaStatusDimensions,
  mesaNextActionFromOperationalTruth,
  stopDistancePct,
  type MesaNextActionKindV1,
} from "@bolsa/shared";
import type { PositionDto } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { buildPositionExitPayload } from "@/features/operations/propose-position-exit";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { PositionRoutePanel } from "@/features/mesa/position-route-panel";

function formatR(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}

/** V1.17 — mostrar ruta ENTRY/STOP/TP cuando hay plan operativo persistido. */
export function mesaPositionShowsRoute(
  position: PositionDto,
  study?: DecisionJournalStudyViewV1 | null,
): boolean {
  if (study?.hasOperationalPlan === true) return true;
  const op = position.operational;
  if (!op) return false;
  return op.currentStop != null || op.target1 != null || op.target2 != null;
}

export function MesaPositionNextActionButton({
  position,
  protectPlan,
  study,
  originStudy,
  compact = true,
  portfolioReconStatus,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  compact?: boolean;
  portfolioReconStatus?: string | null;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const [error, setError] = useState<string | null>(null);
  const truth = buildOperationalTruth({
    position,
    study,
    originStudy,
    portfolioReconStatus,
  });
  const nextAction = truth
    ? mesaNextActionFromOperationalTruth(truth)
    : buildInvestmentPositionAggregate({
        position,
        study,
        originStudy,
        protectPlan,
      }).nextAction;

  function enqueueExit(intent: "review" | "reduce" | "exit_hint" | "protect") {
    setError(null);
    if (!effectiveAccountId) {
      setError("Sin cuenta activa");
      return;
    }
    try {
      const payload = buildPositionExitPayload({
        position,
        accountId: effectiveAccountId,
        intent,
        protectPlan,
      });
      enqueue(payload, { origin: "operativa", symbol: position.symbol });
      openConfirmDrawer();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo encolar");
    }
  }

  const btnClass = compact
    ? "rounded border px-2 py-1 text-[10px] font-medium hover:bg-accent"
    : "rounded border border-border px-2 py-1 text-xs font-medium hover:bg-accent";

  function renderPrimary(kind: MesaNextActionKindV1) {
    switch (kind) {
      case "protect":
        return (
          <button
            type="button"
            className={cn(
              btnClass,
              "border-emerald-500/40 text-emerald-900 dark:text-emerald-100",
            )}
            onClick={() => enqueueExit("protect")}
            data-testid={`mesa-next-action-${position.symbol}`}
          >
            Proteger
          </button>
        );
      case "reduce":
        return (
          <button
            type="button"
            className={cn(btnClass, "border-amber-500/40")}
            onClick={() => enqueueExit("reduce")}
            data-testid={`mesa-next-action-${position.symbol}`}
          >
            Reducir
          </button>
        );
      case "exit":
        return (
          <button
            type="button"
            className={cn(btnClass, "border-rose-500/40")}
            onClick={() => enqueueExit("exit_hint")}
            data-testid={`mesa-next-action-${position.symbol}`}
          >
            Salir
          </button>
        );
      case "review":
        return (
          <button
            type="button"
            className={btnClass}
            onClick={() => enqueueExit("review")}
            data-testid={`mesa-next-action-${position.symbol}`}
          >
            Revisar
          </button>
        );
      case "maintain":
        return (
          <span className="text-[10px] text-muted-foreground">Mantener</span>
        );
      case "view_thesis":
        return study ? (
          <Link
            to={mesaJournalTesisHref(position.instrumentId, { ficha: true })}
            className={cn(btnClass, "inline-block text-center")}
            data-testid={`mesa-next-action-${position.symbol}`}
          >
            Ver tesis
          </Link>
        ) : null;
      case "review_proposal":
        return (
          <Link
            to={CONFIRM_PATH}
            className={cn(
              btnClass,
              "inline-block border-primary/40 bg-primary/10 text-center",
            )}
            data-testid={`mesa-next-action-${position.symbol}`}
          >
            Revisar propuesta
          </Link>
        );
      default:
        return (
          <span className="text-[10px] text-muted-foreground">
            {nextAction.label}
          </span>
        );
    }
  }

  return (
    <div className="flex flex-col items-end gap-0.5">
      {renderPrimary(nextAction.kind)}
      {error ? (
        <span className="max-w-[140px] text-right text-[9px] text-destructive">
          {error}
        </span>
      ) : null}
    </div>
  );
}

/** @deprecated Use MesaPositionNextActionButton — kept for Libro compat. */
export function MesaPositionExitActions({
  position,
  protectPlan,
  compact = false,
  study,
  portfolioReconStatus,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  compact?: boolean;
  study?: DecisionJournalStudyViewV1 | null;
  portfolioReconStatus?: string | null;
}) {
  return (
    <MesaPositionNextActionButton
      position={position}
      protectPlan={protectPlan}
      study={study}
      compact={compact}
      portfolioReconStatus={portfolioReconStatus}
    />
  );
}

export function MesaPositionRow({
  position,
  protectPlan,
  study,
  originStudy,
  showRoute = false,
  portfolioReconStatus,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  showRoute?: boolean;
  portfolioReconStatus?: string | null;
}) {
  const operational = position.operational ?? null;
  const pnlUp = (position.unrealizedPnl ?? 0) >= 0;
  const dims = mapMesaStatusDimensions({
    study,
    positionStatus:
      (operational?.status as PositionStatusV1 | undefined) ?? null,
    hasOpenPosition: true,
    tradePlanStatus: study?.tradePlanStatus ?? null,
  });

  const protection = buildMesaProtectionState({
    study,
    exitSuggestedStop: operational?.exitPlan?.suggestedStop ?? null,
    currentStop: operational?.currentStop ?? null,
    protectPlan,
  });

  const stopForDist = protection.executed.value ?? protection.proposal.value;
  const distPct = stopDistancePct(position.lastPrice, stopForDist);

  const nextAction = buildOperationalTruth({
    position,
    study,
    originStudy,
    portfolioReconStatus,
  });
  const actionLabel = nextAction
    ? nextAction.primaryCta.label
    : buildInvestmentPositionAggregate({
        position,
        study,
        originStudy,
        protectPlan,
      }).nextAction.label;

  return (
    <div
      className="border-b border-border/50 px-3 py-2 last:border-b-0 hover:bg-accent/20"
      data-testid={`mesa-position-${position.symbol}`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[88px]">
          <div className="font-medium">{position.symbol}</div>
          <div
            className="text-[10px] text-muted-foreground"
            data-testid={`mesa-position-action-${position.symbol}`}
          >
            Acción: {actionLabel}
          </div>
          {study?.opinion ? (
            <div className="text-[10px] text-muted-foreground">
              {JOURNAL_STUDY_OPINION_LABELS[study.opinion]}
              {study.strength != null ? ` · ${study.strength.toFixed(1)}` : ""}
            </div>
          ) : null}
        </div>
        <div className="hidden min-w-[140px] flex-1 text-[10px] text-muted-foreground sm:block">
          Tesis: {dims.thesis} · Operativa: {dims.operational} · Posición:{" "}
          {dims.position}
        </div>
        <div className="tabular-nums text-sm font-medium">
          {formatR(operational?.unrealizedR)}
        </div>
        <div className="hidden text-[10px] sm:block">
          <p className="text-muted-foreground">
            Plan{" "}
            {protection.plan.value != null
              ? formatPrice(protection.plan.value)
              : "—"}
          </p>
          <p className="text-muted-foreground">
            Prop.{" "}
            {protection.proposal.value != null
              ? formatPrice(protection.proposal.value)
              : "—"}
          </p>
          <p>
            Ejec.{" "}
            {protection.executed.value != null
              ? formatPrice(protection.executed.value)
              : "—"}
          </p>
        </div>
        <div
          className={cn(
            "text-[10px] font-medium",
            protection.discrepancy
              ? "text-rose-600 dark:text-rose-400"
              : protection.summaryLabel === "Confirmada"
                ? "text-emerald-700 dark:text-emerald-300"
                : "text-muted-foreground",
          )}
        >
          {protection.summaryLabel}
          {distPct != null ? ` · ${distPct}% al stop` : ""}
        </div>
        <div
          className={cn(
            "text-xs tabular-nums",
            pnlUp ? "text-emerald-600 dark:text-emerald-400" : "text-red-500",
          )}
        >
          {position.unrealizedPnl != null
            ? formatPrice(position.unrealizedPnl)
            : "—"}
        </div>
        <div className="ml-auto">
          <MesaPositionNextActionButton
            position={position}
            protectPlan={protectPlan}
            study={study}
            originStudy={originStudy}
            portfolioReconStatus={portfolioReconStatus}
          />
        </div>
      </div>
      {showRoute ? (
        <div className="mt-2 pl-1">
          <PositionRoutePanel
            position={position}
            study={study}
            originStudy={originStudy}
            portfolioReconStatus={portfolioReconStatus}
          />
        </div>
      ) : null}
    </div>
  );
}
