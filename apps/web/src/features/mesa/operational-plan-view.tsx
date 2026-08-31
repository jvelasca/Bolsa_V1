/**
 * Plan operativo unificado (V1.21) — misma tarjeta pre/post entrada.
 * Proyección de TradePlan / PositionState; no entidad nueva.
 * V1.24 — trailing «No aplicado» solo cuando el stop vigente no recoge el hint.
 */

import {
  isTrailingStopApplied,
  targetProgressHint,
  type OperationalPlanViewV1,
} from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

type OperationalPlanViewProps = {
  plan: OperationalPlanViewV1;
  className?: string;
  /** test id suffix (symbol / session). */
  testId?: string;
  /**
   * V1.37 — cuando el Summary ya muestra P&L / precio, el Plan solo geometría.
   */
  omitLiveMetrics?: boolean;
};

function Row({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string | null;
  tone?: "stop" | "target" | "muted" | null;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs">
      <dt
        className={cn(
          "text-muted-foreground",
          tone === "stop" && "text-rose-700 dark:text-rose-300",
          tone === "target" && "text-emerald-700 dark:text-emerald-300",
        )}
      >
        {label}
      </dt>
      <dd className="tabular-nums font-medium">
        {value}
        {hint ? (
          <span className="ml-1 text-[10px] font-normal text-muted-foreground">
            {hint}
          </span>
        ) : null}
      </dd>
    </div>
  );
}

export function OperationalPlanView({
  plan,
  className,
  testId = "operational-plan",
  omitLiveMetrics = false,
}: OperationalPlanViewProps) {
  if (!plan.hasPlan) {
    return (
      <p
        className={cn("text-xs text-muted-foreground", className)}
        data-testid={testId}
      >
        {plan.emptyCopy}
      </p>
    );
  }

  const stopTrace =
    plan.stopInicial != null &&
    plan.stopVigente != null &&
    plan.stopInicial !== plan.stopVigente
      ? `inicial ${formatPrice(plan.stopInicial)}`
      : plan.stopInicial == null && plan.stopVigente != null
        ? "inicial —"
        : null;

  const trailingApplied =
    plan.trailingActive &&
    isTrailingStopApplied({
      direction: plan.direction,
      stopVigente: plan.stopVigente,
      trailingStopHint: plan.trailingStopHint,
    });

  return (
    <div
      className={cn(
        "space-y-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2",
        className,
      )}
      data-testid={testId}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Plan operativo
        </p>
        <span
          className="rounded border border-border/60 px-1.5 py-0.5 text-[10px] font-medium"
          data-testid={`${testId}-phase`}
        >
          {plan.phaseLabel}
        </span>
      </div>
      <dl className="space-y-1">
        <Row
          label="Entrada"
          value={plan.entry != null ? formatPrice(plan.entry) : "—"}
        />
        {!omitLiveMetrics && plan.currentPrice != null ? (
          <Row label="Actual" value={formatPrice(plan.currentPrice)} />
        ) : null}
        <Row
          label="🛡 Stop operativo"
          value={plan.stopVigente != null ? formatPrice(plan.stopVigente) : "—"}
          hint={stopTrace}
          tone="stop"
        />
        <Row
          label="T1"
          value={plan.target1 != null ? formatPrice(plan.target1) : "—"}
          hint={targetProgressHint(plan.target1Touched, plan.target1Managed)}
          tone="target"
        />
        <Row
          label="T2"
          value={plan.target2 != null ? formatPrice(plan.target2) : "—"}
          hint={targetProgressHint(plan.target2Touched, plan.target2Managed)}
          tone="target"
        />
        {plan.expectedRR != null ? (
          <Row label="R/R" value={`1:${plan.expectedRR.toFixed(2)}`} />
        ) : null}
        {plan.riskR != null ? (
          <Row label="Riesgo" value={`${plan.riskR.toFixed(2)}R`} />
        ) : null}
        {!omitLiveMetrics && plan.unrealizedR != null ? (
          <Row
            label="R abierto"
            value={`${plan.unrealizedR >= 0 ? "+" : ""}${plan.unrealizedR.toFixed(2)}R`}
          />
        ) : null}
      </dl>
      {plan.trailingActive ? (
        <div
          className="rounded border border-emerald-500/30 bg-emerald-500/5 px-2 py-1.5"
          data-testid={`${testId}-trailing`}
          data-trailing-applied={trailingApplied ? "true" : "false"}
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-200">
            ↗ Trailing sugerido
          </p>
          <dl className="mt-1 space-y-0.5">
            <Row
              label="Stop operativo"
              value={
                plan.stopVigente != null ? formatPrice(plan.stopVigente) : "—"
              }
              tone="stop"
            />
            {plan.trailingPeakPrice != null ? (
              <Row
                label="Máximo alcanzado"
                value={formatPrice(plan.trailingPeakPrice)}
                hint={
                  plan.trailingPeakMfeR != null
                    ? `${plan.trailingPeakMfeR.toFixed(1)}R`
                    : null
                }
              />
            ) : plan.trailingPeakMfeR != null ? (
              <Row
                label="Pico MFE"
                value={`${plan.trailingPeakMfeR.toFixed(1)}R`}
              />
            ) : null}
            <Row
              label="Stop sugerido"
              value={
                plan.trailingStopHint != null
                  ? formatPrice(plan.trailingStopHint)
                  : "—"
              }
              tone="stop"
            />
            {plan.trailingDistanceR != null ? (
              <Row
                label="Distancia"
                value={`${plan.trailingDistanceR.toFixed(1)}R`}
                tone="muted"
              />
            ) : null}
          </dl>
          {trailingApplied ? (
            <p className="mt-1 text-[10px] font-medium text-emerald-800 dark:text-emerald-200">
              Recogido en el stop vigente
            </p>
          ) : (
            <p className="mt-1 text-[10px] font-medium text-amber-800 dark:text-amber-200">
              ⚠ No aplicado
            </p>
          )}
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            Propuesta thin · SEMI firma · no empeora el stop vigente
          </p>
        </div>
      ) : null}
      {plan.exitAuthorityHint ? (
        <p className="text-[10px] text-muted-foreground">
          {plan.exitAuthorityHint}
        </p>
      ) : null}
    </div>
  );
}
