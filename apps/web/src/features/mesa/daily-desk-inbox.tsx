/**
 * V1.41 — Daily Desk inbox (attention-ordered). Sin paneles de ranking/KPI.
 */

import type { DailyDeskInboxV1, DailyDeskItemV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { Link } from "react-router-dom";

function attentionTone(attention: DailyDeskItemV1["attention"]): string {
  switch (attention) {
    case "BLOCKED":
      return "border-rose-600/45 bg-rose-500/5";
    case "URGENT":
      return "border-amber-600/45 bg-amber-500/5";
    case "ATTENTION":
      return "border-amber-500/30 bg-amber-500/5";
    default:
      return "border-border/60 bg-background/40";
  }
}

function attentionLabel(attention: DailyDeskItemV1["attention"]): string {
  switch (attention) {
    case "BLOCKED":
      return "Bloqueado";
    case "URGENT":
      return "Urgente";
    case "ATTENTION":
      return "Atención";
    default:
      return "Normal";
  }
}

export function DailyDeskInbox({
  inbox,
  className,
}: {
  inbox: DailyDeskInboxV1;
  className?: string;
}) {
  return (
    <section
      className={cn("space-y-3", className)}
      data-testid="daily-desk-inbox"
      data-count={inbox.count}
      aria-labelledby="daily-desk-inbox-title"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-1.5">
        <div className="flex items-baseline gap-2">
          <h2 id="daily-desk-inbox-title" className="text-sm font-semibold">
            Requiere atención
          </h2>
          {inbox.count > 0 ? (
            <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-medium tabular-nums text-primary">
              {inbox.count}
            </span>
          ) : null}
        </div>
      </header>
      <p className="text-xs text-muted-foreground">
        Inbox por attention · Ranking ≠ BUY · Confirm = firma. No es Mercado.
      </p>
      {inbox.count === 0 ? (
        <p
          className="rounded-md border border-border/60 bg-muted/15 px-3 py-4 text-sm text-muted-foreground"
          data-testid="daily-desk-empty"
        >
          {inbox.emptyLabel}
        </p>
      ) : (
        <ul className="space-y-2" data-testid="daily-desk-items">
          {inbox.items.map((item) => (
            <li
              key={item.id}
              className={cn(
                "flex flex-wrap items-start justify-between gap-2 rounded-md border px-3 py-2",
                attentionTone(item.attention),
              )}
              data-testid={`daily-desk-item-${item.id}`}
              data-kind={item.kind}
              data-attention={item.attention}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.symbol}</span>
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {attentionLabel(item.attention)}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {item.reason}
                </p>
              </div>
              <DailyDeskCta item={item} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DailyDeskCta({ item }: { item: DailyDeskItemV1 }) {
  if (item.kind === "pending_confirm") {
    return (
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border border-amber-700/35 bg-amber-500/10 px-2 py-1 text-[11px] font-medium hover:bg-amber-500/20"
          onClick={() => openConfirmDrawer()}
          data-testid="daily-desk-cta-confirm"
        >
          {item.ctaLabel}
        </button>
        <Link
          to={CONFIRM_PATH}
          className="rounded border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
        >
          Ir a /confirm
        </Link>
      </div>
    );
  }

  return (
    <button
      type="button"
      className="rounded border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
      onClick={() => openConfirmDrawer()}
      data-testid={`daily-desk-cta-${item.symbol}`}
    >
      {item.ctaLabel}
    </button>
  );
}
