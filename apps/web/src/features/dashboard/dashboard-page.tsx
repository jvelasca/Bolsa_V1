/**
 * Overview — resumen de la cuenta activa (pregunta: «¿qué tengo y por dónde
 * sigo?»). Tres bloques, cada hecho una sola vez:
 *
 *  1. Cuenta activa + métricas de patrimonio.
 *  2. Accesos rápidos (fila compacta; la navegación completa ya vive en la barra
 *     L1 y en el `AdminRail`, así que aquí no se duplica como catálogo de cards).
 *  3. Últimos movimientos de la cuenta activa.
 *
 * `RT-01`/`R-G1`: ni documentación de arquitectura interna ni tutoriales ocupan
 * el primer nivel; eso vive en Ayuda (Backtesting / Análisis del valor) y en
 * Configuración (Sync / proveedores).
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (§2 RT-01, R-G1, UI5-20)
 */

import type { ComponentType } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  History,
  LineChart,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";
import { formatLedgerEntryLabel, ledgerAmountTone } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  accountTypeShortLabel,
  useActiveAccount,
} from "@/features/accounts/use-active-account";
import { formatPrice } from "@/features/charts/chart-utils";
import { absentDataLabel } from "@/components/absent-data";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-0.5 text-lg font-semibold tabular-nums tracking-tight",
          tone === "positive" && "text-emerald-400",
          tone === "negative" && "text-red-400",
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 text-[10px] text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function ActiveAccountPanel() {
  const { account, effectiveAccountId, accounts, isLoading, isError, refetch } =
    useActiveAccount();
  const openWizard = useUiStore((s) => s.openCreateAccountWizard);

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: async () => {
      if (!effectiveAccountId) return null;
      return (await api.getAccountSummary(effectiveAccountId)).data;
    },
    enabled: Boolean(effectiveAccountId),
    refetchInterval: 60_000,
  });

  const summary = summaryQuery.data;
  const openAccounts = accounts.filter((a) => a.status === "active");
  const otherAccounts = openAccounts.filter((a) => a.id !== effectiveAccountId);

  return (
    <section className="rounded-lg border border-border bg-card/60 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Cuenta activa
          </h2>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Cargando cuentas…</p>
          ) : isError ? (
            <>
              <p role="alert" className="text-sm text-destructive">
                No se pudieron cargar tus cuentas.
              </p>
              <p className="text-sm text-muted-foreground">
                No se puede afirmar que no tengas ninguna: reintenta antes de
                crear otra demo.
              </p>
            </>
          ) : account ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-xl font-semibold tracking-tight">
                  {account.name}
                </p>
                <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {accountTypeShortLabel(account.type)}
                </span>
                <span className="text-sm text-muted-foreground">
                  {account.currency}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                Toda la app opera con esta cuenta. Cambiar de cuenta es en
                Cuentas.
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No hay cuenta activa. Crea una demo para empezar a simular.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/accounts"
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Gestionar cuentas
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
          {isError ? (
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
            >
              Reintentar
            </button>
          ) : (
            <button
              type="button"
              onClick={openWizard}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              Nueva demo
            </button>
          )}
        </div>
      </div>

      {account && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Patrimonio"
            value={
              summary ? formatPrice(summary.totalEquity) : absentDataLabel()
            }
          />
          <Metric
            label="Capital disponible"
            value={summary ? formatPrice(summary.cash) : absentDataLabel()}
          />
          <Metric
            label="Beneficio no realizado"
            value={
              summary
                ? formatPrice(summary.totalUnrealizedPnl)
                : absentDataLabel()
            }
            tone={
              summary
                ? summary.totalUnrealizedPnl >= 0
                  ? "positive"
                  : "negative"
                : undefined
            }
          />
          <Metric
            label="Posiciones abiertas"
            value={summary ? String(summary.positionsCount) : absentDataLabel()}
            hint={
              summary
                ? `Margen libre ${formatPrice(summary.freeMargin)}`
                : undefined
            }
          />
        </div>
      )}

      {otherAccounts.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
          <p className="text-sm text-muted-foreground">
            {otherAccounts.length} otra
            {otherAccounts.length === 1 ? "" : "s"} cuenta
            {otherAccounts.length === 1 ? "" : "s"} activa
            {otherAccounts.length === 1 ? "" : "s"} — cambiar en Cuentas.
          </p>
          <Link
            to="/accounts"
            className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-sm hover:bg-accent"
            data-testid="overview-other-accounts-link"
          >
            Ver cuentas
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
    </section>
  );
}

type QuickLink = {
  to: string;
  label: string;
  hint: string;
  icon: ComponentType<{ className?: string }>;
  primary?: boolean;
};

const QUICK_LINKS: readonly QuickLink[] = [
  {
    to: "/trading",
    label: "Trading",
    hint: "Gráficos, listas y órdenes",
    icon: LineChart,
    primary: true,
  },
  {
    to: "/operations",
    label: "Operaciones",
    hint: "Posiciones y P&L",
    icon: TrendingUp,
  },
  {
    to: "/history",
    label: "Historial",
    hint: "Movimientos y comisiones",
    icon: History,
  },
  {
    to: "/accounts",
    label: "Cuentas",
    hint: "Efectivo y configuración",
    icon: Wallet,
  },
];

function QuickLinks() {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Accesos rápidos
      </h2>
      <nav
        aria-label="Accesos rápidos"
        className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
      >
        {QUICK_LINKS.map(({ to, label, hint, icon: Icon, primary }) => (
          <Link
            key={to}
            to={to}
            className={cn(
              "group flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors hover:bg-accent",
              primary
                ? "border-primary/40 bg-primary/5"
                : "border-border bg-card/60",
            )}
          >
            <Icon className="h-5 w-5 shrink-0 text-primary" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">
                {label}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {hint}
              </span>
            </span>
            <ArrowRight className="ml-auto h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </Link>
        ))}
      </nav>
    </section>
  );
}

function RecentLedgerCard() {
  // U-1 — sin cuenta activa la query del ledger está DESHABILITADA, así que su
  // `isError` sería siempre `false` y un fallo de `/accounts` se leería como «sin
  // movimientos». La causa se toma del hook de cuentas.
  const {
    account,
    effectiveAccountId,
    isError: accountsError,
  } = useActiveAccount();
  const ledgerQuery = useQuery({
    queryKey: ["ledger", effectiveAccountId],
    queryFn: async () => {
      if (!effectiveAccountId) return [];
      return (await api.getAccountLedger(effectiveAccountId, 8)).data;
    },
    enabled: Boolean(effectiveAccountId),
  });

  const entries = ledgerQuery.data ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle level="h2" className="text-base">
              Últimos movimientos
            </CardTitle>
            <CardDescription>
              {account
                ? `Movimientos de «${account.name}» (cuenta activa)`
                : "Movimientos de la cuenta activa"}
            </CardDescription>
          </div>
          <Link to="/history" className="text-xs text-primary hover:underline">
            Ver historial →
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {ledgerQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        )}
        {!ledgerQuery.isLoading && accountsError && (
          <p role="alert" className="text-sm text-destructive">
            No se pudieron cargar los movimientos: no se pudo cargar la cuenta
            activa.
          </p>
        )}
        {!ledgerQuery.isLoading && !accountsError && ledgerQuery.isError && (
          <div role="alert" className="space-y-1 text-sm text-destructive">
            <p>No se pudieron cargar los movimientos.</p>
            <button
              type="button"
              className="text-xs underline"
              onClick={() => void ledgerQuery.refetch()}
            >
              Reintentar
            </button>
          </div>
        )}
        {!ledgerQuery.isLoading &&
          !accountsError &&
          !ledgerQuery.isError &&
          entries.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Sin movimientos. Cuando operes o deposites, aparecerán aquí.
            </p>
          )}
        {!accountsError && !ledgerQuery.isError && entries.length > 0 && (
          <ul className="space-y-2 text-sm">
            {entries.map((entry) => {
              // P1-04 — coste/entrada/neutral por papel del asiento.
              const tone = ledgerAmountTone(entry);
              return (
                <li
                  key={entry.id}
                  className="flex items-center justify-between gap-2 border-b border-border/60 pb-2 last:border-0"
                >
                  <span className="min-w-0 truncate">
                    <span className="font-medium">
                      {formatLedgerEntryLabel(entry)}
                    </span>
                    {entry.symbol ? (
                      <span className="text-muted-foreground">
                        {" "}
                        · {entry.symbol}
                      </span>
                    ) : null}
                  </span>
                  <span
                    data-tone={tone}
                    className={cn(
                      "shrink-0 tabular-nums",
                      tone === "cost" && "text-red-400",
                      tone === "in" && "text-emerald-400",
                      tone === "neutral" && "text-foreground",
                    )}
                  >
                    {formatPrice(entry.amount)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function OverviewPage() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="max-w-2xl space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-muted-foreground">
          Tu cuenta simulada, su patrimonio y los accesos que más usas.
        </p>
        {healthQuery.isError && (
          <p className="mt-2 text-sm text-destructive">
            API no disponible — comprueba que el backend esté en marcha.
          </p>
        )}
      </div>

      <ActiveAccountPanel />

      <QuickLinks />

      <RecentLedgerCard />
    </div>
  );
}
