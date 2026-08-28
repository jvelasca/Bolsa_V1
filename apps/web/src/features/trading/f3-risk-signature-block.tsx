/**
 * P2 — firma de riesgo del TradePlan en el ticket F3.
 * Informativo + override; no ejecuta.
 */

import type { RiskSignatureV1 } from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import { cn } from "@/lib/utils";

type F3RiskSignatureBlockProps = {
  signature: RiskSignatureV1;
  currency: string;
  overrideReason: string;
  onOverrideReasonChange: (value: string) => void;
  className?: string;
};

function Row({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          "tabular-nums",
          emphasis && "font-medium text-foreground",
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function F3RiskSignatureBlock({
  signature,
  currency,
  overrideReason,
  onOverrideReasonChange,
  className,
}: F3RiskSignatureBlockProps) {
  const money = (n: number) => `${formatPrice(n)} ${currency}`;

  if (signature.mode === "no_plan") {
    return (
      <div
        className={cn(
          "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-1 text-xs",
          className,
        )}
        data-testid="f3-risk-signature"
      >
        <div className="flex flex-wrap items-center gap-1.5">
          <p className="text-[11px] font-medium text-foreground">
            Firma de riesgo
          </p>
          <MesaTipButton tip="confirm-risk-signature" />
        </div>
        <p className="text-[11px] text-muted-foreground">
          {signature.blockReason === "no_tradeplan"
            ? "Sin TradePlan TRIGGERED no se puede firmar una apertura SEMI. Usa manual HTTP solo con override explícito de mesa, o espera plan Propuesto."
            : "Sin TradePlan TRIGGERED: no hay stop/R/máx del plan. Indica cantidad manualmente; no se prellena sizing de mandato."}
        </p>
        {signature.blockReason === "no_tradeplan" ? (
          <p className="text-[11px] text-amber-800 dark:text-amber-300">
            Ejecutar apertura bloqueado hasta TRIGGERED.
          </p>
        ) : null}
      </div>
    );
  }

  const qtyLabel =
    signature.suggestedQty != null
      ? `${signature.suggestedQty} (máx. ${signature.maxQty ?? "—"})`
      : "—";

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-2 text-xs",
        className,
      )}
      data-testid="f3-risk-signature"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="text-[11px] font-medium text-foreground">
          Firma de riesgo · TradePlan
        </p>
        <MesaTipButton tip="confirm-risk-signature" />
      </div>
      <div className="space-y-0.5">
        <Row label="Cantidad plan" value={qtyLabel} />
        {signature.stop != null ? (
          <Row label="Stop técnico" value={money(signature.stop)} />
        ) : null}
        {signature.signedLossAtStop != null ? (
          <Row
            label="Pérdida al stop (est.)"
            value={money(signature.signedLossAtStop)}
            emphasis
          />
        ) : null}
        {signature.signedR != null ? (
          <Row label="R firmado" value={`${signature.signedR} R`} />
        ) : null}
        {signature.plannedRiskAmount != null ? (
          <Row label="Riesgo plan" value={money(signature.plannedRiskAmount)} />
        ) : null}
      </div>
      {signature.overrideRequired ? (
        <div className="space-y-1 border-t border-border/60 pt-1.5">
          <p className="text-[11px] text-amber-800 dark:text-amber-300">
            {signature.excess === "qty_above_plan"
              ? "La cantidad supera el plan. Escribe un motivo para firmar."
              : "La pérdida al stop supera el riesgo del plan. Escribe un motivo para firmar."}
          </p>
          <textarea
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-[11px]"
            rows={2}
            value={overrideReason}
            onChange={(e) => onOverrideReasonChange(e.target.value)}
            placeholder="Motivo del override"
            data-testid="f3-risk-override-reason"
          />
        </div>
      ) : signature.blockReason === "stop_wrong_side" ? (
        <p
          className="text-[11px] text-rose-800 dark:text-rose-300"
          data-testid="f3-risk-geometry-block"
        >
          Stop al lado incorrecto de la entrada. Corrige el stop; no se puede
          firmar ni con override.
        </p>
      ) : signature.blockReason === "stop_invalid" ? (
        <p
          className="text-[11px] text-rose-800 dark:text-rose-300"
          data-testid="f3-risk-geometry-block"
        >
          Stop inválido (cero, negativo o no numérico). No se sustituye por el
          del plan — corrige el campo.
        </p>
      ) : signature.blockReason === "targets_invalid" ||
        signature.blockReason === "risk_non_positive" ? (
        <p
          className="text-[11px] text-rose-800 dark:text-rose-300"
          data-testid="f3-risk-geometry-block"
        >
          Niveles operativos inválidos (entrada / stop / T1 / T2). Corrige la
          geometría; no se puede firmar.
        </p>
      ) : (
        <p className="text-[10px] text-muted-foreground">
          El tamaño firma el riesgo del plan, no un % de caja.
        </p>
      )}
    </div>
  );
}
