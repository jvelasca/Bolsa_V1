/**
 * Pasarela LIVE VIRTUAL híbrida dentro de Confirm (resumen de la orden + por qué).
 * No mesa nueva · no chat social · no inventa una ejecución real.
 * @see docs/engineering/design-live-virtual-order-gateway-ui-2026-09-07.md
 */

import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";
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

/** Etiqueta de usuario para el tipo de orden (sin tokens ingleses en el DOM). */
const ORDER_TYPE_LABEL: Record<"LIMIT" | "MARKET", string> = {
  LIMIT: "Límite",
  MARKET: "Mercado",
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
  const primary: LiveVirtualLadderStep[] = ["preparada", "firmada", "enviada"];
  const terminal =
    step === "completada" ||
    step === "rechazada" ||
    step === "no_cableado" ||
    step === "desconocida";

  return (
    <div className="space-y-1.5" data-testid="live-virtual-ladder">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Estado (escalera)
      </p>
      <ol className="space-y-0.5 text-[11px]">
        {primary.map((rung) => {
          const active = step === rung || (rung === "enviada" && terminal);
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
              <span>{LIVE_VIRTUAL_LADDER_COPY[rung]}</span>
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
            {terminal
              ? LIVE_VIRTUAL_LADDER_COPY[step]
              : `${LIVE_VIRTUAL_LADDER_COPY.completada} | ${LIVE_VIRTUAL_LADDER_COPY.rechazada} | ${LIVE_VIRTUAL_LADDER_COPY.no_cableado}`}
          </span>
        </li>
      </ol>
      <p className="text-[10px] text-muted-foreground">
        *respuesta simulada · enviada no es una ejecución real
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
  const sideLabel = ticket
    ? ticket.side === "buy"
      ? "Compra"
      : "Venta"
    : ABSENT_DATA_NOT_MEASURED;
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
      {/* `compact` evita la línea de nivel 2 del banner; la honestidad VIRTUAL se
          mantiene aquí abajo en lenguaje de resultado. */}
      <LiveVirtualBanner compact />

      <div className="grid gap-3 sm:grid-cols-2">
        <div
          className="space-y-2 rounded-md border border-border/80 bg-background/60 px-3 py-2"
          data-testid="live-virtual-telegram"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-foreground">
            Orden propuesta
          </p>
          <div className="space-y-0.5">
            <TelegramRow label="Desde" value="Mesa Bolsa" />
            <TelegramRow label="Para" value="Broker (VIRTUAL)" />
            <TelegramRow label="Referencia" value={proposalRef} mono />
          </div>
          <p className="pt-1 text-sm font-semibold tabular-nums text-foreground">
            {sideLabel} {symbol}
            {qty != null ? ` ${qty}` : ""}
            {price != null ? ` @ ${formatPrice(price)}` : ""}
          </p>
          <div className="space-y-0.5">
            {orderTypeHint ? (
              <TelegramRow
                label="Tipo"
                value={ORDER_TYPE_LABEL[orderTypeHint]}
              />
            ) : (
              <TelegramRow label="Tipo" value={ABSENT_DATA_NOT_MEASURED} />
            )}
            {stop != null && Number.isFinite(stop) ? (
              <TelegramRow label="Stop previsto" value={formatPrice(stop)} />
            ) : (
              <TelegramRow
                label="Stop previsto"
                value={ABSENT_DATA_NOT_MEASURED}
              />
            )}
            {ticket ? (
              <>
                <TelegramRow
                  label="Importe aprox."
                  value={money(ticket.notional)}
                />
                <TelegramRow
                  label="Comisiones aprox."
                  value={money(ticket.fees.total)}
                />
              </>
            ) : (
              <p className="text-[10px] text-muted-foreground">
                Falta el cálculo de la orden.
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
            Por qué se propone
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
            Fuentes: tu plan de operación y el análisis de esta propuesta.
          </p>
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Nada se envía sin tu firma. Usa el botón de abajo para autorizar.
      </p>
    </section>
  );
}
