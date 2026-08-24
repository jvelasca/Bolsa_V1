/**
 * U6 — bloque compacto de preview de ticket (Confirm página + drawer).
 * Informativo: no dispara execute ni bypass de firma.
 */

import { formatPrice } from "@/features/charts/chart-utils";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import type { F3TicketPreviewView } from "@/features/trading/f3-ticket-preview";
import { cn } from "@/lib/utils";

type F3TicketPreviewBlockProps = {
  ticket: F3TicketPreviewView;
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

export function F3TicketPreviewBlock({
  ticket,
  className,
}: F3TicketPreviewBlockProps) {
  const { fees, currency } = ticket;
  const money = (n: number) => `${formatPrice(n)} ${currency}`;

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-2 text-xs",
        className,
      )}
      data-testid="f3-ticket-preview"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="text-[11px] font-medium text-foreground">
          Preview ticket
          {ticket.actionLabel ? ` · ${ticket.actionLabel}` : ""}
          {" · "}
          {ticket.sideLabel}
        </p>
        <MesaTipButton tip="confirm-ticket-preview" />
      </div>
      <p className="text-[11px] text-muted-foreground">
        {ticket.quantity} × {formatPrice(ticket.price)} · solo estimación; la
        firma sigue en Confirmar.
      </p>
      <div className="space-y-0.5">
        <Row label="Importe (notional)" value={money(ticket.notional)} />
        {fees.commission > 0 ? (
          <Row label="Comisión" value={money(fees.commission)} />
        ) : (
          <Row label="Comisión" value={`${formatPrice(0)} ${currency}`} />
        )}
        {fees.vatOnCommission > 0 ? (
          <Row label="IVA comisión" value={money(fees.vatOnCommission)} />
        ) : null}
        {fees.stampDuty > 0 ? (
          <Row label="Transmisiones" value={money(fees.stampDuty)} />
        ) : null}
        {fees.fxConversion > 0 ? (
          <Row label="Conversión FX" value={money(fees.fxConversion)} />
        ) : null}
        <Row
          label={ticket.cashImpactLabel}
          value={money(ticket.cashImpact)}
          emphasis
        />
      </div>
      <div className="space-y-0.5 border-t border-border/60 pt-1.5">
        {ticket.marginRequired != null ? (
          <Row
            label="Margen orden (est.)"
            value={money(ticket.marginRequired)}
          />
        ) : null}
        {ticket.freeMargin != null ? (
          <Row label="Margen libre (cuenta)" value={money(ticket.freeMargin)} />
        ) : null}
        {ticket.freeMarginAfter != null ? (
          <Row
            label="Margen libre tras (est.)"
            value={money(ticket.freeMarginAfter)}
            emphasis
          />
        ) : null}
        {ticket.marginUsed != null ? (
          <Row label="Margen usado (cuenta)" value={money(ticket.marginUsed)} />
        ) : null}
      </div>
      <p className="text-[10px] text-muted-foreground">
        Perfil: {ticket.commissionProfileLabel} · no ejecuta desde preview
      </p>
    </div>
  );
}
