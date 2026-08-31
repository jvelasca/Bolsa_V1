/**
 * V1.32 — ExitPlan + fuente evento|manual en el ticket Confirm (Nivel 1).
 * Simétrico a F3TradePlanRiskFirstBlock / firma de apertura.
 * V1.42 F7 — copy humano (sin enums exit_hint / full_exit / TARGET_1).
 */

import {
  formatExitOperativaIntentLabel,
  formatExitPlanStatusLabel,
  formatExitReasonLabel,
  formatExitSuggestedActionLabel,
} from "@bolsa/shared";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import type { OperativaExitMetaV1 } from "@/features/operations/propose-position-exit";
import { cn } from "@/lib/utils";

type F3ExitPlanBlockProps = {
  meta: OperativaExitMetaV1;
  signedQty: number | null;
  className?: string;
};

export function F3ExitPlanBlock({
  meta,
  signedQty,
  className,
}: F3ExitPlanBlockProps) {
  const plan = meta.exitPlan;
  const exceeds =
    signedQty != null &&
    Number.isFinite(signedQty) &&
    signedQty > meta.plannedQty + 1e-9;

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-2 text-xs",
        className,
      )}
      data-testid="f3-exit-plan"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="text-[11px] font-medium text-foreground">
          Plan de salida
        </p>
        <MesaTipButton tip="confirm-risk-signature" />
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
            meta.exitSource === "manual"
              ? "bg-amber-500/15 text-amber-900 dark:text-amber-100"
              : "bg-emerald-500/15 text-emerald-900 dark:text-emerald-100",
          )}
          data-testid="f3-exit-source"
        >
          {meta.exitSource === "manual" ? "MANUAL" : "EVENTO"}
        </span>
      </div>
      <div className="space-y-0.5">
        <div className="flex justify-between gap-2">
          <span className="text-muted-foreground">Intent</span>
          <span className="font-medium tabular-nums text-foreground">
            {formatExitOperativaIntentLabel(meta.operativaIntent)}
          </span>
        </div>
        <div className="flex justify-between gap-2">
          <span className="text-muted-foreground">Qty planificada</span>
          <span className="tabular-nums">{meta.plannedQty}</span>
        </div>
        {signedQty != null ? (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Qty firmada</span>
            <span
              className={cn(
                "tabular-nums",
                exceeds && "font-medium text-amber-800 dark:text-amber-200",
              )}
            >
              {signedQty}
            </span>
          </div>
        ) : null}
        {plan ? (
          <>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Estado</span>
              <span className="tabular-nums">
                {formatExitPlanStatusLabel(plan.status)}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Acción</span>
              <span className="tabular-nums">
                {formatExitSuggestedActionLabel(plan.suggestedAction)}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Motivo</span>
              <span className="tabular-nums">
                {formatExitReasonLabel(plan.primaryReason)}
              </span>
            </div>
          </>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            Sin ExitPlan advisory en el enqueue — la firma humana fuerza la
            salida (MANUAL).
          </p>
        )}
      </div>
      {exceeds ? (
        <p className="text-[11px] text-amber-800 dark:text-amber-300">
          Qty firmada &gt; plan: hace falta motivo de override (firma de
          tamaño).
        </p>
      ) : null}
      {meta.exitSource === "manual" ? (
        <p className="text-[11px] text-muted-foreground">
          Confirm = firma humana. ExitPermission en servidor usa desriesgo SEMI
          (manual).
        </p>
      ) : null}
    </div>
  );
}
