/**
 * V1.32 — firma de tamaño de salida (simétrico a F3RiskSignatureBlock).
 */

import type { ExitRiskSignatureV1 } from "@bolsa/shared";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import { cn } from "@/lib/utils";

type F3ExitRiskSignatureBlockProps = {
  signature: ExitRiskSignatureV1;
  overrideReason: string;
  onOverrideReasonChange: (value: string) => void;
  className?: string;
};

export function F3ExitRiskSignatureBlock({
  signature,
  overrideReason,
  onOverrideReasonChange,
  className,
}: F3ExitRiskSignatureBlockProps) {
  if (signature.mode === "no_plan") {
    return (
      <div
        className={cn(
          "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-1 text-xs",
          className,
        )}
        data-testid="f3-exit-risk-signature"
      >
        <div className="flex flex-wrap items-center gap-1.5">
          <p className="text-[11px] font-medium text-foreground">
            Firma de tamaño · salida
          </p>
          <MesaTipButton tip="confirm-risk-signature" />
        </div>
        <p className="text-[11px] text-muted-foreground">
          Sin qty planificada de ExitPlan: no hay tope de firma de tamaño.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-2 text-xs",
        className,
      )}
      data-testid="f3-exit-risk-signature"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="text-[11px] font-medium text-foreground">
          Firma de tamaño · salida
        </p>
        <MesaTipButton tip="confirm-risk-signature" />
      </div>
      <div className="space-y-0.5">
        <div className="flex justify-between gap-2">
          <span className="text-muted-foreground">Qty máx. plan</span>
          <span className="tabular-nums">
            {signature.maxQty ?? signature.plannedQty ?? "—"}
          </span>
        </div>
        {signature.excess != null ? (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Exceso</span>
            <span className="tabular-nums text-amber-800 dark:text-amber-200">
              +{signature.excess}
            </span>
          </div>
        ) : null}
      </div>
      {signature.overrideRequired ? (
        <label className="flex flex-col gap-1">
          <span className="text-[11px] text-amber-800 dark:text-amber-200">
            Motivo de override (obligatorio si qty &gt; plan)
          </span>
          <input
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
            value={overrideReason}
            onChange={(e) => onOverrideReasonChange(e.target.value)}
            placeholder="Por qué firmo más cantidad…"
            data-testid="f3-exit-override-reason"
          />
        </label>
      ) : null}
      {!signature.allowed ? (
        <p className="text-[11px] text-amber-800 dark:text-amber-300">
          Ejecutar salida bloqueado hasta ajustar qty o indicar override.
        </p>
      ) : null}
    </div>
  );
}
