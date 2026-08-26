/**
 * V1.17 — ticket Confirm con orden riesgo → entrada → objetivo.
 */

import { type ReactNode } from "react";
import { formatPrice } from "@/features/charts/chart-utils";
import type { F3TicketPreviewView } from "@/features/trading/f3-ticket-preview";
import { cn } from "@/lib/utils";

type F3TradePlanRiskFirstBlockProps = {
  ticket: F3TicketPreviewView;
  stop?: number | null;
  target1?: number | null;
  riskPct?: number | null;
  /** Cantidad/precio editados vs plan TRIGGERED — firma recalculada. */
  inputsStale?: boolean;
  className?: string;
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums font-medium">{value}</span>
    </div>
  );
}

export function F3TradePlanRiskFirstBlock({
  ticket,
  stop,
  target1,
  riskPct,
  inputsStale = false,
  className,
}: F3TradePlanRiskFirstBlockProps) {
  const { currency } = ticket;
  const money = (n: number) => `${formatPrice(n)} ${currency}`;

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-3",
        className,
      )}
      data-testid="f3-trade-plan-risk-first"
    >
      <p className="text-[11px] font-medium">
        Trade plan · {ticket.sideLabel}
        {ticket.actionLabel ? ` · ${ticket.actionLabel}` : ""}
      </p>

      <Section title="Riesgo (primero)">
        <Row label="Stop" value={stop != null ? formatPrice(stop) : "—"} />
        <Row
          label="Pérdida máx. (est.)"
          value={money(Math.abs(ticket.cashImpact))}
        />
        {riskPct != null ? (
          <Row label="% cartera" value={`${riskPct.toFixed(2)}%`} />
        ) : null}
      </Section>

      <Section title="Entrada">
        <Row
          label="Precio"
          value={`${ticket.quantity} × ${formatPrice(ticket.price)}`}
        />
        <Row label="Notional" value={money(ticket.notional)} />
      </Section>

      <Section title="Objetivo">
        <Row label="TP1" value={target1 != null ? formatPrice(target1) : "—"} />
      </Section>

      {inputsStale ? (
        <p
          className="text-[11px] text-amber-800 dark:text-amber-300"
          data-testid="f3-trade-plan-inputs-stale"
        >
          Cantidad o precio modificados respecto al plan — la firma de riesgo se
          recalcula. Si superas el plan, escribe un motivo antes de ejecutar.
        </p>
      ) : null}
      <p className="text-[10px] text-muted-foreground border-t border-border/60 pt-2">
        PLAN → PROPUESTA → EJECUTADO. Modificar cantidad invalida el riesgo
        calculado — recalcular antes de firmar.
      </p>
    </div>
  );
}
