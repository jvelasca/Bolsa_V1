import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { LedgerEntryDto, TransactionDto } from "@bolsa/shared";
import { formatLedgerEntryLabel } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { AccountScopeSelector } from "@/features/accounts/account-scope-selector";
import { formatPrice } from "@/features/charts/chart-utils";
import { api } from "@/lib/api";
import { formatDateTimeCompact } from "@/lib/format";
import { cn } from "@/lib/utils";

type HistoryTab = "ledger" | "trades";

function formatDateTime(iso: string) {
  return formatDateTimeCompact(iso);
}

function ledgerTypeLabel(entry: LedgerEntryDto): string {
  return formatLedgerEntryLabel(entry);
}

function LedgerTable({ entries }: { entries: LedgerEntryDto[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin movimientos en el ledger.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">Fecha</th>
            <th className="px-2 py-2 font-medium">Tipo</th>
            <th className="px-2 py-2 font-medium">Detalle</th>
            <th className="px-2 py-2 text-right font-medium">Importe</th>
            <th className="px-2 py-2 text-right font-medium">Saldo</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr
              key={entry.id}
              className="border-b border-border/50 hover:bg-accent/20"
            >
              <td className="px-2 py-2 whitespace-nowrap text-xs text-muted-foreground">
                {formatDateTime(entry.executedAt)}
              </td>
              <td className="px-2 py-2">
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase">
                  {ledgerTypeLabel(entry)}
                </span>
              </td>
              <td className="px-2 py-2 text-xs">
                {entry.symbol && (
                  <span className="font-medium">{entry.symbol}</span>
                )}
                {entry.quantity != null && entry.price != null && (
                  <span className="ml-1 text-muted-foreground">
                    {entry.quantity} × {formatPrice(entry.price)}
                  </span>
                )}
                {entry.description && (
                  <p className="text-muted-foreground">{entry.description}</p>
                )}
              </td>
              <td
                className={cn(
                  "px-2 py-2 text-right tabular-nums",
                  entry.amount >= 0 ? "text-emerald-400" : "text-red-400",
                )}
              >
                {formatPrice(entry.amount)} {entry.currency}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">
                {formatPrice(entry.balanceAfter)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradesTable({ transactions }: { transactions: TransactionDto[] }) {
  if (transactions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin operaciones ejecutadas.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">Fecha</th>
            <th className="px-2 py-2 font-medium">Tipo</th>
            <th className="px-2 py-2 font-medium">Símbolo</th>
            <th className="px-2 py-2 text-right font-medium">Qty</th>
            <th className="px-2 py-2 text-right font-medium">Precio</th>
            <th className="px-2 py-2 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr
              key={tx.id}
              className="border-b border-border/50 hover:bg-accent/20"
            >
              <td className="px-2 py-2 whitespace-nowrap text-xs text-muted-foreground">
                {formatDateTime(tx.executedAt)}
              </td>
              <td className="px-2 py-2 capitalize">
                {tx.type === "buy" ? "Compra" : "Venta"}
              </td>
              <td className="px-2 py-2 font-medium">{tx.symbol}</td>
              <td className="px-2 py-2 text-right tabular-nums">
                {tx.quantity}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {formatPrice(tx.price)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {formatPrice(tx.total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function HistoryPage() {
  const [tab, setTab] = useState<HistoryTab>("ledger");
  const { account, effectiveAccountId } = useActiveAccount();

  const ledgerQuery = useQuery({
    queryKey: ["ledger", effectiveAccountId],
    queryFn: async () => {
      if (!effectiveAccountId) return [];
      return (await api.getAccountLedger(effectiveAccountId, 100)).data;
    },
    enabled: Boolean(effectiveAccountId),
  });

  const transactionsQuery = useQuery({
    queryKey: ["transactions", effectiveAccountId],
    queryFn: () => api.getTransactions(100),
    enabled: Boolean(effectiveAccountId),
  });

  const ledgerEntries = ledgerQuery.data ?? [];
  const transactions = transactionsQuery.data?.data ?? [];
  const feeTotal = ledgerEntries
    .filter((e) => e.type === "fee")
    .reduce((sum, e) => sum + Math.abs(e.amount), 0);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Historial</h2>
          <p className="text-sm text-muted-foreground">
            Ledger contable y operaciones ejecutadas de la cuenta activa.
          </p>
        </div>
        <Link to="/overview" className="text-sm text-primary hover:underline">
          ← Overview
        </Link>
        <Link
          to="/fiscal"
          className="text-sm text-muted-foreground hover:text-primary"
        >
          Informe fiscal →
        </Link>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Cuenta</CardTitle>
          <CardDescription>
            {account?.settings?.commission.label ?? "Perfil de comisiones"} ·
            fiscal {account?.settings?.tax.jurisdiction ?? "—"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <AccountScopeSelector />
          {feeTotal > 0 && (
            <div className="text-sm">
              <p className="text-xs text-muted-foreground">
                Comisiones acumuladas (ledger)
              </p>
              <p className="font-medium tabular-nums">
                {formatPrice(feeTotal)}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-1 border-b border-border">
        {(
          [
            ["ledger", "Ledger contable"],
            ["trades", "Operaciones"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              tab === id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
            {id === "ledger" && ledgerEntries.length > 0 && (
              <span className="ml-1 text-xs opacity-70">
                ({ledgerEntries.length})
              </span>
            )}
            {id === "trades" && transactions.length > 0 && (
              <span className="ml-1 text-xs opacity-70">
                ({transactions.length})
              </span>
            )}
          </button>
        ))}
      </div>

      <Card>
        <CardContent className="pt-4">
          {(ledgerQuery.isLoading || transactionsQuery.isLoading) && (
            <p className="text-sm text-muted-foreground">Cargando historial…</p>
          )}
          {tab === "ledger" && !ledgerQuery.isLoading && (
            <LedgerTable entries={ledgerEntries} />
          )}
          {tab === "trades" && !transactionsQuery.isLoading && (
            <TradesTable transactions={transactions} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
