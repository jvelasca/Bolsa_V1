import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, History } from "lucide-react";
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
import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

export function OperationsPage() {
  const accountScope = useActiveAccountQueryKey();
  const { account } = useActiveAccount();

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
  });

  const summary = portfolioQuery.data?.data;
  const positionsCount = summary?.positions.length ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">
            Mis operaciones
          </h2>
          <p className="text-sm text-muted-foreground">
            Posiciones abiertas y órdenes pendientes
            {account ? ` · ${account.name}` : ""}.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
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
            Historial
          </Link>
        </div>
      </div>

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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Panel de operaciones</CardTitle>
          <CardDescription>
            Misma vista que en Trading — posiciones en cartera y órdenes
            stop/limitadas.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="h-[min(480px,60vh)] min-h-[280px]">
            <OperationsPanel />
          </div>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        <Link to="/overview" className="text-primary hover:underline">
          ← Volver al Overview
        </Link>
      </p>
    </div>
  );
}
