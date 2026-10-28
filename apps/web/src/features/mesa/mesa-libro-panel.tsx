/**
 * Posiciones absorbidas en Mesa — posiciones + pendientes + NoTrade (V1.19).
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
import { formatPriceOrAbsent } from "@/features/charts/chart-utils";
import { OperationsPanel } from "@/features/trading/operations-panel";
import { NoTradeSessionButton } from "@/features/operations/no-trade-session-button";
import type { MesaProtectionKpiV1, PortfolioSummaryDto } from "@bolsa/shared";
import { MesaProteccionKpi } from "@/features/mesa/mesa-proteccion-kpi";
import type { CollectionReadState } from "@/components/query-absence";

export function MesaLibroPanel({
  summary,
  accountName,
  protectionKpi,
  protectionState,
}: {
  summary: PortfolioSummaryDto | null | undefined;
  accountName?: string | null;
  protectionKpi?: MesaProtectionKpiV1 | null;
  /** P1-06 — estado de lectura de la cartera para el KPI de protección. */
  protectionState?: CollectionReadState;
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
          {/* `UI5-04` — la vista `?view=posiciones` ya tiene su `h2 «Posiciones»`
              (resumen con una acción por posición); este bloque es el nivel de detalle
              (protección · cifras · pendientes), así que no repite el mismo rótulo. */}
          <h2 className="text-base font-semibold">Plan y pendientes</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Protección, cifras y órdenes pendientes · CTAs encolan Confirm
            {accountName ? ` · ${accountName}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {protectionKpi ? (
            <MesaProteccionKpi
              kpi={protectionKpi}
              compact
              absenceState={protectionState}
            />
          ) : null}
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
                {formatPriceOrAbsent(summary.totalEquity)}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>P&amp;L no realizado</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {formatPriceOrAbsent(summary.totalUnrealizedPnl)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Posiciones y pendientes</CardTitle>
          <CardDescription>
            Misma superficie que el Historial — Confirm es la firma.
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
