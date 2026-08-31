/**
 * Mantener / Reducir / Salir sin salir de Mercado.
 *
 * Encola el ticket y abre el drawer de Confirm (la firma sigue siendo Confirm).
 * No navega a Hoy: el contexto del valor se mantiene.
 * V1.42 F5 — `primaryCtaKind` desde PositionOperatingTruth alinea CTA con Hoy/Journal.
 * V1.42 F7 — `primaryOnly` default true: una CTA primaria; Reducir/Salir solo si son primary.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §3.1
 */

import { useState } from "react";
import type { PositionDto, ProtectPlanV1 } from "@bolsa/shared";
import {
  buildPositionDecisionFromDto,
  formatExitPolicyActionHint,
  isPrimaryPositionExitCta,
  primaryPositionExitCta,
  type PositionExitCtaKindV1,
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
  /** V1.42 F7 — una sola CTA alineada a truth.action (default true · SEMI). */
  primaryOnly = true,
  /** V1.42 F5 — preferir CTA de PositionOperatingTruth (§A.8) cuando existe. */
  primaryCtaKind,
  portfolioReconStatus,
  className,
}: {
  position: PositionDto;
  protectPlan?: ProtectPlanV1 | null;
  compact?: boolean;
  /** Cockpit en fase POSICIÓN muestra «Mantener» como estado, no como botón. */
  showMaintain?: boolean;
  primaryOnly?: boolean;
  primaryCtaKind?: PositionExitCtaKindV1 | null;
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
  const effectivePrimary: PositionExitCtaKindV1 | null =
    primaryCtaKind ?? (decision ? primaryPositionExitCta(decision) : null);

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

  function isPrimaryKind(kind: PositionExitCtaKindV1) {
    if (effectivePrimary) return effectivePrimary === kind;
    if (!decision) return false;
    return isPrimaryPositionExitCta(decision, kind);
  }

  function ctaClass(kind: PositionExitCtaKindV1) {
    const base = btnClass;
    if (isPrimaryKind(kind)) {
      return cn(base, primaryBtnClass);
    }
    return cn(base, "opacity-75");
  }

  const hasProtectHint = positionShowsProtectHint(position, protectPlan);
  // Primary protect, or secondary «Proteger» when Mantener + hint (trail/protect → Confirm).
  const showProtect =
    !reconBlocked &&
    (effectivePrimary === "protect" ||
      decision?.action === "PROTECT" ||
      hasProtectHint);
  const showProtectAsPrimary =
    effectivePrimary === "protect" || decision?.action === "PROTECT";
  const showProtectSecondary =
    primaryOnly &&
    effectivePrimary === "maintain" &&
    hasProtectHint &&
    !showProtectAsPrimary;
  const showMaintainBadge = primaryOnly
    ? effectivePrimary === "maintain"
    : showMaintain || decision?.action === "HOLD";
  const showReview =
    reconBlocked ||
    effectivePrimary === "review" ||
    decision?.action === "REVIEW";
  const showReduceExit =
    !reconBlocked &&
    !showReview &&
    (effectivePrimary === "reduce" || effectivePrimary === "exit");

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
              effectivePrimary === "maintain" ? primaryBtnClass : null,
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
        {showProtect && (showProtectAsPrimary || showProtectSecondary) ? (
          <button
            type="button"
            className={cn(
              showProtectAsPrimary ? ctaClass("protect") : btnClass,
              "border-emerald-500/40 text-emerald-900 dark:text-emerald-100",
              showProtectSecondary && "opacity-75",
            )}
            onClick={() => enqueueExit("protect")}
            data-testid={`position-exit-protect-${position.symbol}`}
            title="Proteger → cola Confirm (firma SEMI · hint ≠ stop)"
          >
            Proteger
          </button>
        ) : null}
        {showReduceExit ? (
          <>
            {effectivePrimary === "reduce" ? (
              <button
                type="button"
                className={cn(ctaClass("reduce"), "border-amber-500/40")}
                onClick={() => enqueueExit("reduce")}
                data-testid={`position-exit-reduce-${position.symbol}`}
                title="Reducir → cola Confirm (firma SEMI)"
              >
                Reducir
              </button>
            ) : null}
            {effectivePrimary === "exit" ? (
              <button
                type="button"
                className={cn(ctaClass("exit"), "border-rose-500/40")}
                onClick={() => enqueueExit("exit_hint")}
                data-testid={`position-exit-full-${position.symbol}`}
                title="Salir → cola Confirm (firma SEMI)"
              >
                Salir
              </button>
            ) : null}
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
