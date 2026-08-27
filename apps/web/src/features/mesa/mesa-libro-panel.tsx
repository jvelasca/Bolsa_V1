/**
 * Libro absorbido en Mesa — posiciones + pendientes + NoTrade (V1.19).
 */

import { Link } from "react-router-dom";
import { History } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatPrice } from "@/features/charts/chart-utils";
import { OperationsPanel } from "@/features/trading/operations-panel";
import { NoTradeSessionButton } from "@/features/operations/no-trade-session-button";
import type { PortfolioSummaryDto } from "@bolsa/shared";

export function MesaLibroPanel({
  summary,
  accountName,
}: {
  summary: PortfolioSummaryDto | null | undefined;
  accountName?: string | null;
}) {
  const positionsCount = summary?.positions.length ?? 0;

  return (
    <div
      className="space-y-4"
      data-testid="mesa-libro-panel"
      id="mesa-focus-libro"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Libro · Posiciones</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Plan persistido y pendientes — CTAs encolan Confirm
            {accountName ? ` · ${accountName}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <NoTradeSessionButton />
          <Link
            to="/history"
            className="inline-flex items-center gap-1 text-muted-foreground hover:text-primary"
          >
            <History className="h-4 w-4" />
            Historial
          </Link>
        </div>
      </div>

      {summary ? (
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
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Posiciones y pendientes</CardTitle>
          <CardDescription>
            Misma superficie que el Libro histórico — Confirm es la firma.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="h-[min(480px,60vh)] min-h-[280px]">
            <OperationsPanel />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
