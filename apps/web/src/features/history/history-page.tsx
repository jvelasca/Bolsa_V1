import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { LedgerEntryDto, TransactionDto } from "@bolsa/shared";
import { formatLedgerEntryLabel, ledgerAmountTone } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { AccountScopeSelector } from "@/features/accounts/account-scope-selector";
import { formatPrice } from "@/features/charts/chart-utils";
import { api } from "@/lib/api";
import { absentDataLabel } from "@/components/absent-data";
import { CollectionAbsence } from "@/components/collection-absence";
import {
  isCollectionAbsent,
  queryCollectionState,
} from "@/components/query-absence";
import { formatDateTimeCompact } from "@/lib/format";
import { cn } from "@/lib/utils";

type HistoryTab = "movements" | "trades";

function formatDateTime(iso: string) {
  return formatDateTimeCompact(iso);
}

function movementTypeLabel(entry: LedgerEntryDto): string {
  return formatLedgerEntryLabel(entry);
}

function MovementsTable({ entries }: { entries: LedgerEntryDto[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin movimientos contables.
      </p>
    );
  }

  return (
    // `scrollable-region-focusable` (axe): en móvil (390×844) la tabla desborda y hace scroll;
    // la región debe ser alcanzable por teclado y estar nombrada (mismo criterio que
    // `journal-studies-table`, `/backtests` y las tablas fiscales).
    <div
      role="region"
      aria-label="Movimientos contables"
      tabIndex={0}
      className="overflow-x-auto"
    >
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
          {entries.map((entry) => {
            // P1-04 — el tono declara el papel del movimiento (coste / entrada /
            // neutral); el importe conserva su signo, el color no lo recalcula.
            const tone = ledgerAmountTone(entry);
            return (
              <tr
                key={entry.id}
                className="border-b border-border/50 hover:bg-accent/20"
              >
                <td className="px-2 py-2 whitespace-nowrap text-xs text-muted-foreground">
                  {formatDateTime(entry.executedAt)}
                </td>
                <td className="px-2 py-2">
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase">
                    {movementTypeLabel(entry)}
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
                  data-tone={tone}
                  className={cn(
                    "px-2 py-2 text-right tabular-nums",
                    tone === "cost" && "text-red-400",
                    tone === "in" && "text-emerald-400",
                    tone === "neutral" && "text-foreground",
                  )}
                >
                  {formatPrice(entry.amount)} {entry.currency}
                </td>
                <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">
                  {formatPrice(entry.balanceAfter)}
                </td>
              </tr>
            );
          })}
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
    // `scrollable-region-focusable` (axe): misma razón que en `MovementsTable`.
    <div
      role="region"
      aria-label="Operaciones ejecutadas"
      tabIndex={0}
      className="overflow-x-auto"
    >
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
  const [tab, setTab] = useState<HistoryTab>("movements");
  const { account, effectiveAccountId } = useActiveAccount();

  const movementsQuery = useQuery({
    queryKey: ["movimientos", effectiveAccountId],
    queryFn: async () => {
      if (!effectiveAccountId) return null;
      // P1-03 — se guarda la respuesta completa: `tradeFeesTotal` es un agregado
      // del servidor que la página de movimientos no puede reconstruir.
      return await api.getAccountLedger(effectiveAccountId, 100);
    },
    enabled: Boolean(effectiveAccountId),
  });

  const transactionsQuery = useQuery({
    queryKey: ["transactions", effectiveAccountId],
    queryFn: () => api.getTransactions(100),
    enabled: Boolean(effectiveAccountId),
  });

  const movements = movementsQuery.data?.data ?? [];
  const transactions = transactionsQuery.data?.data ?? [];
  // P1-01 — el error de la API no es una colección vacía (`UI5-14`).
  const movementsState = queryCollectionState({
    isError: movementsQuery.isError,
    isLoading: movementsQuery.isLoading,
    count: movementsQuery.data?.data?.length,
  });
  const transactionsState = queryCollectionState({
    isError: transactionsQuery.isError,
    isLoading: transactionsQuery.isLoading,
    count: transactionsQuery.data?.data?.length,
  });
  const feeTotal = movementsQuery.data?.tradeFeesTotal ?? null;
  /**
   * P1-03 — «Comisiones acumuladas» se calculaba sumando las filas `fee` de la
   * página (100 movimientos), así que con más histórico la cifra estaba
   * subestimada y aun así se presentaba como el total. El agregado lo da el
   * servidor (`tradeFeesTotal`, todo el histórico, sin custodia) y la tarjeta
   * declara el hueco cuando la consulta no se ha leído.
   */
  const feeTotalLabel =
    feeTotal != null
      ? formatPrice(feeTotal, movements[0]?.currency ?? null)
      : absentDataLabel(
          movementsState === "error" ? "not_available" : "not_measured",
        );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Historial</h1>
          <p className="text-sm text-muted-foreground">
            Movimientos y ejecuciones de tu cuenta
            {account ? ` · ${account.name}` : ""}.
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
          <h2 className="text-base font-semibold tracking-tight">Cuenta</h2>
          <CardDescription>
            {account?.settings?.commission.label ?? "Perfil de comisiones"} ·
            fiscal {account?.settings?.tax.jurisdiction ?? absentDataLabel()}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <AccountScopeSelector />
          <div className="text-sm" data-testid="history-trade-fees-total">
            <p className="text-xs text-muted-foreground">
              Comisiones de operaciones (histórico)
            </p>
            <p
              className="font-medium tabular-nums"
              data-fees-state={feeTotal != null ? "measured" : "absent"}
              title="Suma de todas las comisiones de operaciones de la cuenta; la custodia se contabiliza aparte."
            >
              {feeTotalLabel}
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-1 border-b border-border">
        {(
          [
            ["movements", "Movimientos contables"],
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
            {id === "movements" && movements.length > 0 && (
              <span className="ml-1 text-xs opacity-70">
                ({movements.length})
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
          {tab === "movements" && (
            <>
              <CollectionAbsence
                state={movementsState}
                subject="el historial de movimientos"
                testId="history-movements-absence"
              />
              {!isCollectionAbsent(movementsState) && (
                <MovementsTable entries={movements} />
              )}
            </>
          )}
          {tab === "trades" && (
            <>
              <CollectionAbsence
                state={transactionsState}
                subject="el historial de operaciones"
                testId="history-trades-absence"
              />
              {!isCollectionAbsent(transactionsState) && (
                <TradesTable transactions={transactions} />
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
