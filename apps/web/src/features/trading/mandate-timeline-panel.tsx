/**
 * Timeline de mandato operativo (ADR-020) — rail Coach / Checklist.
 */

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  MANDATE_ACTOR_LABELS,
  MANDATE_REASON_LABELS,
  formatMandateTenureRange,
  getMandateStoreSnapshot,
  listMandateTenures,
  listTradeLinksForMandate,
  subscribeMandateStore,
  summarizeMandateChurn,
  countTradeLinksForInstrument,
  type MandateTenure,
} from "@/features/platform/operating-mandate";
import { ensureMandateHydrated } from "@/features/platform/operating-mandate-sync";
import {
  buildMandatePnlReport,
  formatMandateCashflow,
  type MandateTenureCashflow,
} from "@/features/platform/mandate-tenure-pnl";
import { cn } from "@/lib/utils";

function useMandateRevision(): number {
  return useSyncExternalStore(
    subscribeMandateStore,
    getMandateStoreSnapshot,
    () => 0,
  );
}

function TenureRow({
  t,
  cashflow,
}: {
  t: MandateTenure;
  cashflow?: MandateTenureCashflow | null;
}) {
  const open = t.effectiveTo == null;
  const tradeCount =
    cashflow?.tradeCount ?? listTradeLinksForMandate(t.id).length;
  return (
    <li
      className={cn(
        "rounded border px-1.5 py-1",
        open
          ? "border-sky-600/40 bg-sky-500/10"
          : "border-border/60 bg-background/50 text-muted-foreground",
      )}
    >
      <p className="font-medium text-foreground">
        {t.strategyLabelSnapshot ?? t.strategyDefinitionId?.slice(0, 8) ?? "—"}
        {open ? " · vigente" : ""}
      </p>
      <p>{formatMandateTenureRange(t)}</p>
      <p>
        {MANDATE_ACTOR_LABELS[t.actor]} · {MANDATE_REASON_LABELS[t.reason]}
        {tradeCount > 0 ? ` · ${tradeCount} trade(s)` : ""}
      </p>
      {cashflow && cashflow.tradeCount > 0 ? (
        <p className="text-foreground">
          Flujo enlazado{" "}
          <span
            className={
              cashflow.netCashFlow >= 0
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-rose-700 dark:text-rose-400"
            }
          >
            {formatMandateCashflow(cashflow.netCashFlow)}
          </span>
        </p>
      ) : null}
    </li>
  );
}

export function MandateTimelinePanel({
  instrumentId,
  accountId,
  compact = false,
  className,
}: {
  instrumentId: string;
  accountId: string | null | undefined;
  compact?: boolean;
  className?: string;
}) {
  useMandateRevision();
  useEffect(() => {
    if (accountId) void ensureMandateHydrated(accountId);
  }, [accountId]);

  const txQuery = useQuery({
    queryKey: ["transactions", "mandate-pnl", accountId, instrumentId],
    queryFn: () => api.getTransactions(200),
    enabled: Boolean(accountId && instrumentId),
    staleTime: 30_000,
  });

  const pnl = useMemo(() => {
    if (!accountId) return null;
    const txs = (txQuery.data?.data ?? []).filter(
      (t) => t.instrumentId === instrumentId,
    );
    return buildMandatePnlReport({
      instrumentId,
      accountId,
      transactions: txs,
    });
  }, [accountId, instrumentId, txQuery.data]);

  if (!accountId) {
    return (
      <p className={cn("text-[11px] text-muted-foreground", className)}>
        Elige cuenta activa para ver el mandato.
      </p>
    );
  }

  const tenures = listMandateTenures(instrumentId, accountId);
  const churn = summarizeMandateChurn({ instrumentId, accountId });
  const tradeTotal = countTradeLinksForInstrument(instrumentId, accountId);
  const recent = compact ? tenures.slice(-4).reverse() : [...tenures].reverse();
  const cashById = new Map(pnl?.rows.map((r) => [r.tenureId, r]) ?? []);

  return (
    <div
      className={cn("space-y-1.5 text-[11px]", className)}
      data-testid="mandate-timeline"
    >
      <p className="font-semibold text-foreground">Mandato operativo</p>
      {tenures.length === 0 ? (
        <p className="text-muted-foreground">
          Sin historial. Al <strong className="text-foreground">Adoptar</strong>{" "}
          un Finalista (Checklist) se abre el mandato vigente.
        </p>
      ) : (
        <ul className="space-y-1">
          {recent.map((t) => (
            <TenureRow key={t.id} t={t} cashflow={cashById.get(t.id)} />
          ))}
        </ul>
      )}
      {pnl && pnl.totalLinkedTrades > 0 ? (
        <p className="text-muted-foreground">
          Flujo neto mandato:{" "}
          <span className="font-medium text-foreground">
            {formatMandateCashflow(pnl.totalNetCashFlow)}
          </span>{" "}
          · {pnl.totalLinkedTrades} fill(s) enlazados
        </p>
      ) : null}
      {churn.totalChanges > 0 && (
        <p className="text-muted-foreground">
          Cambios: {churn.totalChanges}
          {churn.byActor.user ? ` · usuario ${churn.byActor.user}` : ""}
          {churn.byActor.coach ? ` · coach ${churn.byActor.coach}` : ""}
          {churn.byActor.core_r ? ` · CORE-R ${churn.byActor.core_r}` : ""}
          {tradeTotal ? ` · trades enlazados ${tradeTotal}` : ""}
        </p>
      )}
    </div>
  );
}
