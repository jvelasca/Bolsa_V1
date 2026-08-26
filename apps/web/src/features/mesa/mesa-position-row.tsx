/**
 * Fila comprimida de posición para Mesa · Hoy (P2).
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
  mapMesaStatusDimensions,
} from "@bolsa/shared";
import type { PositionDto } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import {
  buildPositionExitPayload,
  positionShowsProtectHint,
} from "@/features/operations/propose-position-exit";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";

function formatR(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}

function protectionLabel(operational: PositionDto["operational"]): string {
  const action = operational?.exitPlan?.suggestedAction;
  if (!action || action === "hold") return "Protección OK";
  if (action === "protect") return "Revisar protección";
  if (action === "reduce") return "Reducir";
  if (action === "full_exit") return "Salir";
  return action;
}

export function MesaPositionExitActions({
  position,
  protectPlan,
  compact = false,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  compact?: boolean;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const [error, setError] = useState<string | null>(null);
  const hasPlan = Boolean(position.operational?.tradePlanId);
  const showProtect = positionShowsProtectHint(position, protectPlan);

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

  if (!hasPlan) {
    return <span className="text-[10px] text-muted-foreground">sin plan</span>;
  }

  const btnClass = compact
    ? "rounded border px-2 py-1 text-[10px] hover:bg-accent"
    : "rounded border border-border px-1.5 py-0.5 text-[10px] hover:bg-accent";

  return (
    <div className="flex flex-col items-end gap-0.5">
      <div className="flex flex-wrap justify-end gap-1">
        {showProtect ? (
          <button
            type="button"
            className={cn(
              btnClass,
              "border-emerald-500/40 text-emerald-900 dark:text-emerald-100",
            )}
            onClick={() => enqueueExit("protect")}
            data-testid={`mesa-protect-${position.symbol}`}
          >
            Proteger
          </button>
        ) : null}
        <button
          type="button"
          className={btnClass}
          onClick={() => enqueueExit("review")}
        >
          Revisar
        </button>
        {!compact ? (
          <>
            <button
              type="button"
              className={btnClass}
              onClick={() => enqueueExit("reduce")}
            >
              Reducir
            </button>
            <button
              type="button"
              className={cn(
                btnClass,
                "border-amber-500/40 text-amber-900 dark:text-amber-100",
              )}
              onClick={() => enqueueExit("exit_hint")}
            >
              Salir
            </button>
          </>
        ) : null}
      </div>
      {error ? (
        <span className="max-w-[140px] text-right text-[9px] text-destructive">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export function MesaPositionRow({
  position,
  protectPlan,
  study,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  study?: DecisionJournalStudyViewV1 | null;
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

  return (
    <div
      className="flex flex-wrap items-center gap-3 border-b border-border/50 px-3 py-2 last:border-b-0 hover:bg-accent/20"
      data-testid={`mesa-position-${position.symbol}`}
    >
      <div className="min-w-[88px]">
        <div className="font-medium">{position.symbol}</div>
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
      <div className="hidden text-xs tabular-nums sm:block">
        SL{" "}
        {operational?.currentStop != null
          ? formatPrice(operational.currentStop)
          : "—"}
      </div>
      <div className="hidden text-xs tabular-nums sm:block">
        T1{" "}
        {operational?.target1 != null ? formatPrice(operational.target1) : "—"}
      </div>
      <div className="text-[10px] text-muted-foreground">
        {protectionLabel(operational)}
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
      <div className="ml-auto flex items-center gap-2">
        {study ? (
          <Link
            to={mesaJournalTesisHref(position.instrumentId, { ficha: true })}
            className="text-[10px] text-primary hover:underline"
          >
            Ver tesis
          </Link>
        ) : null}
        <MesaPositionExitActions
          position={position}
          protectPlan={protectPlan}
          compact
        />
      </div>
    </div>
  );
}
