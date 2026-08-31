/**
 * Mantener / Reducir / Salir sin salir de Mercado.
 *
 * Encola el ticket y abre el drawer de Confirm (la firma sigue siendo Confirm).
 * No navega a Hoy: el contexto del valor se mantiene.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §3.1
 */

import { useState } from "react";
import type { PositionDto, ProtectPlanV1 } from "@bolsa/shared";
import {
  buildPositionDecisionFromDto,
  formatExitPolicyActionHint,
  isPrimaryPositionExitCta,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import {
  buildPositionExitPayload,
  positionShowsProtectHint,
  type PositionExitIntent,
} from "@/features/operations/propose-position-exit";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";

export function PositionExitDrawerActions({
  position,
  protectPlan,
  compact = false,
  showMaintain = false,
  portfolioReconStatus,
  className,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  compact?: boolean;
  /** Cockpit en fase POSICIÓN muestra «Mantener» como estado, no como botón. */
  showMaintain?: boolean;
  portfolioReconStatus?: string | null;
  className?: string;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);
  const [error, setError] = useState<string | null>(null);

  const decision = buildPositionDecisionFromDto(position, {
    portfolioReconStatus,
  });
  const reconBlocked = decision?.reconHealth === "CRITICAL";

  function enqueueExit(intent: PositionExitIntent) {
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
      const id = enqueue(payload, {
        origin: "operativa",
        symbol: position.symbol,
      });
      setActive(id);
      openConfirmDrawer();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo encolar");
    }
  }

  const btnClass = compact
    ? "rounded border px-2 py-1 text-[10px] font-medium hover:bg-accent"
    : "rounded-md border px-2 py-1 text-xs font-medium hover:bg-accent";

  const primaryBtnClass = compact
    ? "ring-1 ring-primary/45 bg-primary/10 font-semibold"
    : "ring-1 ring-primary/45 bg-primary/10 font-semibold";

  function ctaClass(
    kind: "maintain" | "protect" | "reduce" | "exit" | "review",
  ) {
    const base = btnClass;
    if (!decision) return base;
    if (isPrimaryPositionExitCta(decision, kind)) {
      return cn(base, primaryBtnClass);
    }
    return cn(base, "opacity-75");
  }

  const showProtect =
    !reconBlocked &&
    (decision?.action === "PROTECT" ||
      positionShowsProtectHint(position, protectPlan));
  const showMaintainBadge = showMaintain || decision?.action === "HOLD";
  const showReview = reconBlocked || decision?.action === "REVIEW";
  const showReduceExit = !reconBlocked && !showReview;

  const exitPlan = position.operational?.exitPlan;
  const policyHint = formatExitPolicyActionHint({
    suggestedAction: exitPlan?.suggestedAction,
    suggestedQty: exitPlan?.suggestedQty,
    primaryReason: exitPlan?.primaryReason,
    templateId: exitPlan?.policyTemplateId,
  });

  return (
    <div className={cn("flex flex-col items-start gap-0.5", className)}>
      <div className="flex flex-wrap items-center gap-1">
        {showMaintainBadge ? (
          <span
            className={cn(
              "rounded-md border border-border px-2 py-1 text-xs text-muted-foreground",
              decision && isPrimaryPositionExitCta(decision, "maintain")
                ? primaryBtnClass
                : null,
            )}
          >
            Mantener
          </span>
        ) : null}
        {showReview ? (
          <button
            type="button"
            className={ctaClass("review")}
            onClick={() => enqueueExit("review")}
            data-testid={`position-exit-review-${position.symbol}`}
            title="Revisar → cola Confirm (reconciliación / tesis)"
          >
            Revisar
          </button>
        ) : null}
        {showProtect ? (
          <button
            type="button"
            className={cn(
              ctaClass("protect"),
              "border-emerald-500/40 text-emerald-900 dark:text-emerald-100",
            )}
            onClick={() => enqueueExit("protect")}
            data-testid={`position-exit-protect-${position.symbol}`}
            title="Proteger → cola Confirm (firma SEMI)"
          >
            Proteger
          </button>
        ) : null}
        {showReduceExit ? (
          <>
            <button
              type="button"
              className={cn(ctaClass("reduce"), "border-amber-500/40")}
              onClick={() => enqueueExit("reduce")}
              data-testid={`position-exit-reduce-${position.symbol}`}
              title="Reducir → cola Confirm (firma SEMI)"
            >
              Reducir
            </button>
            <button
              type="button"
              className={cn(ctaClass("exit"), "border-rose-500/40")}
              onClick={() => enqueueExit("exit_hint")}
              data-testid={`position-exit-full-${position.symbol}`}
              title="Salir → cola Confirm (firma SEMI)"
            >
              Salir
            </button>
          </>
        ) : null}
      </div>
      {policyHint ? (
        <span
          className="max-w-[240px] text-[9px] text-muted-foreground"
          data-testid={`position-exit-policy-hint-${position.symbol}`}
        >
          {policyHint}
        </span>
      ) : null}
      {error ? (
        <span className="max-w-[200px] text-[9px] text-destructive">
          {error}
        </span>
      ) : null}
    </div>
  );
}
