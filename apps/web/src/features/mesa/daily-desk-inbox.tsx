/**
 * V1.42 F6 — Daily Desk four buckets (§B.7). Sin ranking/KPI chrome.
 * V1.42 F7 — CTA posición: enqueue → Confirm (nunca ejecuta sin firma).
 */

import { useMemo, useState } from "react";
import type {
  DailyDeskBucketV1,
  DailyDeskInboxV1,
  DailyDeskItemV1,
  PositionDto,
  ProtectPlanV1,
} from "@bolsa/shared";
import {
  DAILY_DESK_BUCKET_LABEL,
  PAPER_AUTO_ARMED_EXEC_OFF,
  PAPER_AUTO_ARMED_EXEC_ON,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import {
  buildPositionExitPayload,
  type PositionExitIntent,
} from "@/features/operations/propose-position-exit";
import {
  mesaJournalTesisHref,
  mesaOperationsHref,
  mesaOperationalConsoleHref,
} from "@/features/mesa/mesa-nav-links";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { Link } from "react-router-dom";

function bucketTone(id: DailyDeskBucketV1["id"]): string {
  switch (id) {
    case "requiere_accion":
      return "border-rose-600/40";
    case "proteger":
      return "border-orange-500/40";
    case "posiciones":
      return "border-sky-600/35";
    case "oportunidades":
      return "border-emerald-600/35";
    case "no_operar":
      return "border-border/60";
    default:
      return "border-border/60";
  }
}

function bucketMarker(id: DailyDeskBucketV1["id"]): string {
  switch (id) {
    case "requiere_accion":
      return "🔴";
    case "proteger":
      return "🟠";
    case "posiciones":
      return "🟢";
    case "oportunidades":
      return "🔵";
    case "no_operar":
      return "⚪";
    default:
      return "⚪";
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

function ctaKindToExitIntent(
  kind: DailyDeskItemV1["ctaKind"],
): PositionExitIntent | null {
  switch (kind) {
    case "reduce":
      return "reduce";
    case "exit":
      return "exit_hint";
    case "protect":
      return "protect";
    case "review":
      return "review";
    default:
      return null;
  }
}

function isPaperAutoEntryLabel(label: string): boolean {
  return (
    label === PAPER_AUTO_ARMED_EXEC_OFF ||
    label === PAPER_AUTO_ARMED_EXEC_ON ||
    /AUTO armado/i.test(label)
  );
}

function isOperacionesCtaLabel(label: string): boolean {
  return /operaciones/i.test(label);
}

export function DailyDeskInbox({
  inbox,
  positions,
  protectPlanByInstrument,
  className,
}: {
  inbox: DailyDeskInboxV1;
  /** F7 — lookup para enqueue salida → Confirm. */
  positions?: readonly PositionDto[];
  protectPlanByInstrument?: Map<string, ProtectPlanV1> | null;
  className?: string;
}) {
  const positionsById = useMemo(() => {
    const map = new Map<string, PositionDto>();
    for (const p of positions ?? []) map.set(p.id, p);
    return map;
  }, [positions]);

  const buckets = inbox.buckets?.length
    ? inbox.buckets
    : ([
        {
          id: "requiere_accion" as const,
          label: DAILY_DESK_BUCKET_LABEL.requiere_accion,
          items: inbox.items,
          count: inbox.count,
          emptyLabel: inbox.emptyLabel,
        },
      ] satisfies DailyDeskBucketV1[]);

  return (
    <section
      className={cn("space-y-4", className)}
      data-testid="daily-desk-inbox"
      data-count={inbox.count}
      aria-labelledby="daily-desk-inbox-title"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-1.5">
        <div className="flex items-baseline gap-2">
          <h2 id="daily-desk-inbox-title" className="text-sm font-semibold">
            Hoy
          </h2>
          {inbox.count > 0 ? (
            <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-medium tabular-nums text-primary">
              {inbox.count}
            </span>
          ) : null}
        </div>
      </header>
      <p className="text-xs text-muted-foreground">
        Cuatro cubos · misma CTA/frase que Mercado · Ranking ≠ BUY · Confirm =
        firma. No es Mercado.
      </p>
      <div
        className="grid gap-3 md:grid-cols-2"
        data-testid="daily-desk-buckets"
      >
        {buckets.map((bucket) => (
          <DailyDeskBucket
            key={bucket.id}
            bucket={bucket}
            positionsById={positionsById}
            protectPlanByInstrument={protectPlanByInstrument}
          />
        ))}
      </div>
    </section>
  );
}

function DailyDeskBucket({
  bucket,
  positionsById,
  protectPlanByInstrument,
}: {
  bucket: DailyDeskBucketV1;
  positionsById: Map<string, PositionDto>;
  protectPlanByInstrument?: Map<string, ProtectPlanV1> | null;
}) {
  return (
    <section
      className={cn(
        "rounded-md border bg-background/40 px-3 py-2.5",
        bucketTone(bucket.id),
      )}
      data-testid={`daily-desk-bucket-${bucket.id}`}
      data-count={bucket.count}
      aria-labelledby={`daily-desk-bucket-title-${bucket.id}`}
    >
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3
          id={`daily-desk-bucket-title-${bucket.id}`}
          className="text-xs font-semibold uppercase tracking-wide"
        >
          <span aria-hidden="true" className="mr-1">
            {bucketMarker(bucket.id)}
          </span>
          {bucket.label}
        </h3>
        {bucket.count > 0 ? (
          <span className="text-[11px] tabular-nums text-muted-foreground">
            {bucket.count}
          </span>
        ) : null}
      </header>
      {bucket.count === 0 ? (
        <p
          className="rounded border border-dashed border-border/50 px-2 py-3 text-xs text-muted-foreground"
          data-testid={`daily-desk-empty-${bucket.id}`}
        >
          {bucket.emptyLabel}
        </p>
      ) : (
        <ul className="space-y-2" data-testid={`daily-desk-items-${bucket.id}`}>
          {bucket.items.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-start justify-between gap-2 rounded border border-border/50 bg-muted/10 px-2.5 py-2"
              data-testid={`daily-desk-item-${item.id}`}
              data-kind={item.kind}
              data-bucket={item.bucket}
              data-attention={item.attention}
              data-reason-code={item.reasonCode ?? undefined}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.symbol}</span>
                  {item.phaseLabel ? (
                    <span className="text-[10px] font-medium text-foreground/80">
                      {item.phaseLabel}
                    </span>
                  ) : (
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {attentionLabel(item.attention)}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {item.phrase || item.reason}
                </p>
              </div>
              <DailyDeskCta
                item={item}
                positionsById={positionsById}
                protectPlanByInstrument={protectPlanByInstrument}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DailyDeskCta({
  item,
  positionsById,
  protectPlanByInstrument,
}: {
  item: DailyDeskItemV1;
  positionsById: Map<string, PositionDto>;
  protectPlanByInstrument?: Map<string, ProtectPlanV1> | null;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);
  const [error, setError] = useState<string | null>(null);

  if (/comprar/i.test(item.ctaLabel)) {
    return (
      <span
        className="rounded border border-border/60 px-2 py-1 text-[11px] text-muted-foreground"
        data-testid={`daily-desk-cta-${item.symbol}`}
      >
        Ranking ≠ BUY
      </span>
    );
  }

  if (item.kind === "incident" && item.ctaKind === "review") {
    return (
      <Link
        to={mesaOperationalConsoleHref()}
        className="rounded border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
        data-testid={`daily-desk-cta-${item.symbol}`}
      >
        {item.ctaLabel}
      </Link>
    );
  }

  if (
    item.ctaKind === "review" &&
    isOperacionesCtaLabel(item.ctaLabel) &&
    item.kind !== "incident"
  ) {
    return (
      <Link
        to={mesaOperationsHref()}
        className="rounded border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
        data-testid={`daily-desk-cta-${item.symbol}`}
      >
        {item.ctaLabel}
      </Link>
    );
  }

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

  const exitIntent = ctaKindToExitIntent(item.ctaKind);
  if (
    item.kind === "position" &&
    exitIntent &&
    item.positionId &&
    positionsById.has(item.positionId)
  ) {
    const position = positionsById.get(item.positionId)!;
    const protectPlan =
      protectPlanByInstrument?.get(position.instrumentId) ?? null;

    return (
      <div className="flex flex-col items-end gap-0.5">
        <button
          type="button"
          className="rounded border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
          onClick={() => {
            setError(null);
            if (!effectiveAccountId) {
              setError("Sin cuenta activa");
              return;
            }
            try {
              const payload = buildPositionExitPayload({
                position,
                accountId: effectiveAccountId,
                intent: exitIntent,
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
          }}
          data-testid={`daily-desk-cta-${item.symbol}`}
          title="Encolar → Confirm (firma SEMI)"
        >
          {item.ctaLabel}
        </button>
        {error ? (
          <span className="max-w-[140px] text-right text-[9px] text-destructive">
            {error}
          </span>
        ) : null}
      </div>
    );
  }

  if (
    item.ctaKind === "review_proposal" ||
    item.ctaKind === "pending_confirm"
  ) {
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

  if (
    (item.ctaKind === "view_thesis" || item.ctaKind === "watch") &&
    item.instrumentId
  ) {
    const href =
      item.kind === "entry" && isOperacionesCtaLabel(item.ctaLabel)
        ? mesaOperationsHref()
        : mesaJournalTesisHref(item.instrumentId, { ficha: true });
    return (
      <Link
        to={href}
        className="rounded border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
        data-testid={`daily-desk-cta-${item.symbol}`}
      >
        {item.ctaLabel}
      </Link>
    );
  }

  if (item.ctaKind === "maintain" || item.ctaKind === "none") {
    if (item.kind === "entry" && isPaperAutoEntryLabel(item.ctaLabel)) {
      return (
        <span
          className="rounded border border-sky-700/35 bg-sky-500/10 px-2 py-1 text-[11px] font-medium text-foreground"
          data-testid={`daily-desk-cta-${item.symbol}`}
          title="PAPER AUTO · Ranking ≠ BUY · arm ≠ execute"
        >
          {item.ctaLabel}
        </span>
      );
    }
    return (
      <span
        className="rounded border border-border/60 px-2 py-1 text-[11px] text-muted-foreground"
        data-testid={`daily-desk-cta-${item.symbol}`}
      >
        {item.ctaLabel}
      </span>
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
