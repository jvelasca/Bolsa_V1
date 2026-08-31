/**
 * V1.37 — Resumen operativo diario («¿qué está pasando?»).
 * Próximo evento ≠ protección; frase humana ≠ permiso.
 * Números de plan (entrada/stop/T1/T2) viven en OperationalPlanView.
 */

import type { OperationalTruthV1, PositionDto } from "@bolsa/shared";
import {
  RECON_HEALTH_COPY,
  buildOperationalTruth,
  formatExecutionHintCopy,
  formatNextEventLabel,
  formatOperationalAsOf,
  formatPositionDecisionPhrase,
  formatProtectionLabel,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

function formatPctSigned(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatRSigned(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}

export function PositionOperatingSummary({
  truth: truthProp,
  position,
  portfolioReconStatus,
  orderPending,
  className,
}: {
  truth?: OperationalTruthV1 | null;
  position?: PositionDto;
  portfolioReconStatus?: string | null;
  orderPending?: boolean;
  className?: string;
}) {
  const truth =
    truthProp ??
    (position
      ? buildOperationalTruth({
          position,
          portfolioReconStatus,
          orderPending,
        })
      : null);
  if (!truth) return null;

  const { decision, reconHealth, pnl, primaryCta } = truth;
  const asOfLabel = formatOperationalAsOf(truth.asOf);
  const executionCopy = formatExecutionHintCopy(truth);
  const reconConsequence =
    reconHealth === "CRITICAL"
      ? "Existe una discrepancia de cartera. Reconciliación necesaria antes de abrir nuevas posiciones."
      : null;

  return (
    <div
      className={cn(
        "space-y-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-2",
        className,
      )}
      data-testid="position-operating-summary"
      data-action={decision.action}
      data-cta={primaryCta.kind}
      data-next-event={decision.nextEvent}
      data-protection={decision.protection}
      data-recon={reconHealth}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p
          className="text-[11px] font-semibold uppercase tracking-wide"
          data-testid="position-operating-action"
        >
          {primaryCta.label}
        </p>
        {pnl.unrealizedPnlPct != null ? (
          <p
            className={cn(
              "text-[11px] font-medium tabular-nums",
              pnl.unrealizedPnlPct >= 0
                ? "text-emerald-800 dark:text-emerald-200"
                : "text-rose-800 dark:text-rose-200",
            )}
            data-testid="position-operating-pnl"
          >
            {formatPctSigned(pnl.unrealizedPnlPct)}
            {pnl.unrealizedR != null
              ? ` · ${formatRSigned(pnl.unrealizedR)}`
              : ""}
          </p>
        ) : pnl.unrealizedR != null ? (
          <p
            className="text-[11px] font-medium tabular-nums"
            data-testid="position-operating-pnl"
          >
            {formatRSigned(pnl.unrealizedR)}
          </p>
        ) : null}
      </div>
      <p
        className="text-[11px] leading-snug text-foreground"
        data-testid="position-operating-phrase"
      >
        {formatPositionDecisionPhrase(decision)}
      </p>
      <dl className="grid gap-1 text-[10px]">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Próximo evento</dt>
          <dd
            className="font-medium tabular-nums"
            data-testid="position-operating-next-event"
          >
            {formatNextEventLabel(decision.nextEvent)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Protección</dt>
          <dd
            className={cn(
              "font-medium",
              decision.protection === "ACTIVE"
                ? "text-emerald-800 dark:text-emerald-200"
                : "text-amber-800 dark:text-amber-200",
            )}
            data-testid="position-operating-protection"
          >
            {formatProtectionLabel(decision.protection)}
          </dd>
        </div>
        {reconHealth === "CRITICAL" ? (
          <div className="space-y-0.5">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Reconciliación</dt>
              <dd
                className="font-medium text-rose-800 dark:text-rose-200"
                data-testid="position-operating-recon"
              >
                {RECON_HEALTH_COPY.CRITICAL}
              </dd>
            </div>
            {reconConsequence ? (
              <p
                className="text-[10px] leading-snug text-rose-800/90 dark:text-rose-200/90"
                data-testid="position-operating-recon-detail"
              >
                {reconConsequence}
              </p>
            ) : null}
          </div>
        ) : reconHealth === "ATTENTION" ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Reconciliación</dt>
            <dd
              className="font-medium text-amber-800 dark:text-amber-200"
              data-testid="position-operating-recon"
            >
              Revisar
            </dd>
          </div>
        ) : null}
        {asOfLabel ? (
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Datos</dt>
            <dd
              className="font-medium tabular-nums"
              data-testid="position-operating-asof"
            >
              {asOfLabel}
            </dd>
          </div>
        ) : null}
      </dl>
      {executionCopy ? (
        <p
          className="text-[10px] font-medium text-amber-800 dark:text-amber-200"
          data-testid="position-operating-execution"
        >
          {executionCopy}
        </p>
      ) : null}
      <p className="text-[9px] text-muted-foreground">
        Stop operativo registrado ≠ orden stop de broker. Confirm = firma.
      </p>
    </div>
  );
}
