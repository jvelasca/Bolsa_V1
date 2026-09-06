/**
 * Pasarela LIVE VIRTUAL híbrida dentro de Confirm (telegrama + por qué).
 * No mesa nueva · no chat social · no inventa fill real.
 * @see docs/engineering/design-live-virtual-order-gateway-ui-2026-09-07.md
 */

import { formatPrice } from "@/features/charts/chart-utils";
import {
  LIVE_VIRTUAL_LADDER_COPY,
  LIVE_VIRTUAL_LADDER_ORDER,
  type LiveVirtualLadderStep,
} from "@/features/confirm/live-virtual-ladder";
import { LiveVirtualBanner } from "@/features/confirm/live-virtual-banner";
import type { LiveVirtualWhyBlock } from "@/features/confirm/live-virtual-why";
import type { F3TicketPreviewView } from "@/features/trading/f3-ticket-preview";
import { cn } from "@/lib/utils";

type LiveVirtualOrderGatewayProps = {
  symbol: string;
  proposalRef: string;
  ticket: F3TicketPreviewView | null;
  stop?: number | null;
  orderTypeHint?: "LIMIT" | "MARKET" | null;
  ladderStep: LiveVirtualLadderStep;
  whyBlocks: LiveVirtualWhyBlock[];
  className?: string;
};

function TelegramRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2 text-[11px]">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          "text-right text-foreground",
          mono && "font-mono tabular-nums text-[10px]",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function LadderVisual({ step }: { step: LiveVirtualLadderStep }) {
  const primary: LiveVirtualLadderStep[] = ["proposed", "signed", "submitted"];
  const terminal =
    step === "filled" ||
    step === "rejected" ||
    step === "not_wired" ||
    step === "unknown";

  return (
    <div className="space-y-1.5" data-testid="live-virtual-ladder">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Estado (escalera)
      </p>
      <ol className="space-y-0.5 text-[11px]">
        {primary.map((rung) => {
          const active = step === rung || (rung === "submitted" && terminal);
          const past =
            LIVE_VIRTUAL_LADDER_ORDER.indexOf(step) >
            LIVE_VIRTUAL_LADDER_ORDER.indexOf(rung);
          return (
            <li
              key={rung}
              className={cn(
                "flex gap-1.5",
                active || past ? "text-foreground" : "text-muted-foreground/70",
              )}
              data-testid={`live-virtual-ladder-${rung}`}
              data-active={step === rung ? "true" : "false"}
            >
              <span aria-hidden>{step === rung ? "→" : past ? "✓" : "·"}</span>
              <span>
                {rung}
                {step === rung ? ` · ${LIVE_VIRTUAL_LADDER_COPY[rung]}` : ""}
              </span>
            </li>
          );
        })}
        <li
          className={cn(
            "flex gap-1.5",
            terminal ? "text-foreground" : "text-muted-foreground/70",
          )}
          data-testid={`live-virtual-ladder-terminal`}
          data-step={terminal ? step : ""}
        >
          <span aria-hidden>{terminal ? "→" : "·"}</span>
          <span>
            filled* | rejected | not_wired
            {terminal ? ` · ${LIVE_VIRTUAL_LADDER_COPY[step]}` : ""}
          </span>
        </li>
      </ol>
      <p className="text-[10px] text-muted-foreground">
        *respuesta SIMULADA · submitted ≠ fill real
      </p>
    </div>
  );
}

export function LiveVirtualOrderGateway({
  symbol,
  proposalRef,
  ticket,
  stop,
  orderTypeHint,
  ladderStep,
  whyBlocks,
  className,
}: LiveVirtualOrderGatewayProps) {
  const sideLabel = ticket ? (ticket.side === "buy" ? "BUY" : "SELL") : "—";
  const qty = ticket?.quantity;
  const price = ticket?.price;
  const money = (n: number) =>
    ticket ? `${formatPrice(n)} ${ticket.currency}` : String(n);

  return (
    <section
      className={cn(
        "space-y-3 rounded-md border border-sky-500/35 bg-sky-500/[0.04] p-3",
        className,
      )}
      data-testid="live-virtual-order-gateway"
    >
      <LiveVirtualBanner />

      <div className="grid gap-3 sm:grid-cols-2">
        <div
          className="space-y-2 rounded-md border border-border/80 bg-background/60 px-3 py-2"
          data-testid="live-virtual-telegram"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-foreground">
            Telegrama al broker
          </p>
          <div className="space-y-0.5">
            <TelegramRow label="DE" value="Mesa Bolsa" />
            <TelegramRow label="A" value="Broker (VIRTUAL)" />
            <TelegramRow label="REF" value={proposalRef} mono />
          </div>
          <p className="pt-1 text-sm font-semibold tabular-nums text-foreground">
            {sideLabel} {symbol}
            {qty != null ? ` ${qty}` : ""}
            {price != null ? ` @ ${formatPrice(price)}` : ""}
          </p>
          <div className="space-y-0.5">
            {orderTypeHint ? (
              <TelegramRow label="Tipo" value={orderTypeHint} />
            ) : (
              <TelegramRow label="Tipo" value="sin dato" />
            )}
            {stop != null && Number.isFinite(stop) ? (
              <TelegramRow label="STOP plan" value={formatPrice(stop)} />
            ) : (
              <TelegramRow label="STOP plan" value="—" />
            )}
            {ticket ? (
              <>
                <TelegramRow
                  label="Notional ~"
                  value={money(ticket.notional)}
                />
                <TelegramRow label="Fees ~" value={money(ticket.fees.total)} />
              </>
            ) : (
              <p className="text-[10px] text-muted-foreground">
                Sin ticket preview resoluble.
              </p>
            )}
          </div>
          <LadderVisual step={ladderStep} />
        </div>

        <div
          className="space-y-3 rounded-md border border-border/80 bg-background/60 px-3 py-2"
          data-testid="live-virtual-why"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-foreground">
            Para ti (por qué)
          </p>
          {whyBlocks.map((block) => (
            <div key={block.id} data-testid={`live-virtual-why-${block.id}`}>
              <p className="text-[11px] font-medium text-foreground">
                {block.title}
              </p>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">
                {block.bullets.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
          <p className="text-[10px] text-muted-foreground">
            Fuentes: TradePlan · DECISIÓN · risk / ticket Confirm (existentes).
          </p>
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Confirm = firma humana · nunca se envía sola · CTA abajo.
      </p>
    </section>
  );
}
