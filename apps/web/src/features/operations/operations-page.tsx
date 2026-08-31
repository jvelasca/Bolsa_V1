import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, History } from "lucide-react";
import { MESA_PATH } from "@/features/confirm/daily-nav";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { formatPrice } from "@/features/charts/chart-utils";
import { OperationsPanel } from "@/features/trading/operations-panel";
import { MesaOperationalBar } from "@/features/operations/mesa-operational-bar";
import { MesaEntryQueuePanel } from "@/features/operations/mesa-entry-queue-panel";
import { NoTradeSessionButton } from "@/features/operations/no-trade-session-button";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

export function OperationsPage() {
  const accountScope = useActiveAccountQueryKey();
  const { account } = useActiveAccount();

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
  });

  const { entriesBlocked } = useMesaEntriesBlocked();

  const summary = portfolioQuery.data?.data;
  const positionsCount = summary?.positions.length ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">
            Libro · Operaciones
          </h2>
          <p className="text-sm text-muted-foreground">
            Posiciones primero — plan persistido, desriesgo vía Confirmar
            {account ? ` · ${account.name}` : ""}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <NoTradeSessionButton />
          <Link
            to="/trading"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            Ir a Trading
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/history"
            className="inline-flex items-center gap-1 text-muted-foreground hover:text-primary"
          >
            <History className="h-4 w-4" />
            Libro · Historial
          </Link>
        </div>
      </div>

      <MesaOperationalBar positionsCount={positionsCount} />

      {summary && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Posiciones abiertas</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {positionsCount}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Patrimonio</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {formatPrice(summary.totalEquity)}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>P&amp;L no realizado</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {formatPrice(summary.totalUnrealizedPnl)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Posiciones</CardTitle>
            <CardDescription>
              Plan persistido + advisory ExitPlan. CTAs encolan Confirm — no
              ejecutan solos.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="h-[min(480px,60vh)] min-h-[280px]">
              <OperationsPanel />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Entradas</CardTitle>
            <CardDescription>
              Proyección Decision Board ·{" "}
              <Link to={MESA_PATH} className="text-primary hover:underline">
                Abrir Mesa · Oportunidades
              </Link>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MesaEntryQueuePanel entriesBlocked={entriesBlocked} />
          </CardContent>
        </Card>
      </div>

      <p className="text-xs text-muted-foreground">
        <Link to="/overview" className="text-primary hover:underline">
          ← Volver al Overview
        </Link>
      </p>
    </div>
  );
}
