/**
 * V1.38 — Resumen operativo de entrada («¿qué está pasando?» pre-posición).
 * Fase + frase + trigger + sizing. Niveles en OperationalPlanView.
 */

import type {
  DecisionJournalStudyViewV1,
  EntryOperatingTruthV1,
} from "@bolsa/shared";
import {
  buildEntryOperatingTruth,
  formatEntryOperatingAsOf,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";

function formatMoney(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return formatPrice(value);
}

function formatR(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `${value.toFixed(2)}R`;
}

function formatRR(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `${value.toFixed(1)}:1`;
}

export function EntryOperatingSummary({
  truth: truthProp,
  study,
  inConfirmQueue,
  orderPendingFill,
  entriesBlocked,
  gateStatus,
  className,
}: {
  truth?: EntryOperatingTruthV1 | null;
  study?: DecisionJournalStudyViewV1 | null;
  inConfirmQueue?: boolean;
  orderPendingFill?: boolean;
  entriesBlocked?: boolean;
  gateStatus?: string | null;
  className?: string;
}) {
  const truth =
    truthProp ??
    (study
      ? buildEntryOperatingTruth({
          study,
          inConfirmQueue,
          orderPendingFill,
          entriesBlocked,
          gateStatus,
        })
      : null);
  if (!truth) return null;

  const { sizing, phaseLabel, primaryCta } = truth;
  const asOfLabel = formatEntryOperatingAsOf(truth.asOf);
  const riskMoney = formatMoney(sizing.riskAmount);
  const riskR = formatR(sizing.riskR);
  const rr = formatRR(sizing.expectedRR);
  const notional = formatMoney(sizing.positionValue);
  const qty =
    sizing.quantity != null && Number.isFinite(sizing.quantity)
      ? `${sizing.quantity} uds`
      : null;

  return (
    <div
      className={cn(
        "space-y-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-2",
        className,
      )}
      data-testid="entry-operating-summary"
      data-phase={truth.phase}
      data-cta={primaryCta.kind}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p
          className="text-[11px] font-semibold uppercase tracking-wide"
          data-testid="entry-operating-phase"
        >
          {phaseLabel}
        </p>
        <p
          className="text-[11px] font-medium text-muted-foreground"
          data-testid="entry-operating-trigger"
        >
          Trigger: {truth.triggerLabel}
        </p>
      </div>
      <p
        className="text-[11px] leading-snug text-foreground"
        data-testid="entry-operating-phrase"
      >
        {truth.phrase}
      </p>
      <dl className="grid gap-1 text-[10px]">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Acción</dt>
          <dd className="font-medium" data-testid="entry-operating-action">
            {primaryCta.label}
          </dd>
        </div>
        {riskMoney ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Riesgo al stop</dt>
            <dd className="font-medium tabular-nums">{riskMoney}</dd>
          </div>
        ) : null}
        {riskR ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">R planificado</dt>
            <dd className="font-medium tabular-nums">{riskR}</dd>
          </div>
        ) : null}
        {rr ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">R/R esperado</dt>
            <dd className="font-medium tabular-nums">{rr}</dd>
          </div>
        ) : null}
        {notional || qty ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Tamaño</dt>
            <dd className="font-medium tabular-nums">
              {[notional, qty].filter(Boolean).join(" · ")}
            </dd>
          </div>
        ) : null}
        {truth.expiryLabel ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Vigencia</dt>
            <dd className="font-medium">{truth.expiryLabel}</dd>
          </div>
        ) : null}
        {asOfLabel ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Datos</dt>
            <dd
              className="font-medium tabular-nums"
              data-testid="entry-operating-asof"
            >
              {asOfLabel}
            </dd>
          </div>
        ) : null}
      </dl>
      <p className="text-[9px] text-muted-foreground">
        Ranking ≠ BUY. Confirm = firma.
      </p>
    </div>
  );
}
