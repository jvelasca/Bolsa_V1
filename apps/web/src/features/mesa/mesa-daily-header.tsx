/**
 * KPIs de cuenta para Mesa · Hoy (NIVEL 2).
 */

import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatPrice } from "@/features/charts/chart-utils";
import { mesaOperationsHref } from "@/features/mesa/mesa-nav-links";

type MesaDailyHeaderProps = {
  cash: number | null;
  equity: number | null;
  unrealizedPnl: number | null;
  positionsCount: number;
  alertCount: number;
  criticalAlerts?: number;
};

export function MesaDailyHeader({
  cash,
  equity,
  unrealizedPnl,
  positionsCount,
  alertCount,
  criticalAlerts = 0,
}: MesaDailyHeaderProps) {
  const pnlUp = (unrealizedPnl ?? 0) >= 0;

  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid="mesa-daily-header">
      <Card>
        <CardHeader className="pb-1">
          <CardDescription>Cuenta</CardDescription>
          <CardTitle className="text-xl tabular-nums">
            {equity != null ? formatPrice(equity) : "—"}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Caja {cash != null ? formatPrice(cash) : "—"}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-1">
          <CardDescription>Cartera</CardDescription>
          <CardTitle className="text-xl tabular-nums">
            {equity != null ? formatPrice(equity) : "—"}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          <span className={pnlUp ? "text-emerald-600" : "text-red-500"}>
            {unrealizedPnl != null ? formatPrice(unrealizedPnl) : "—"}
          </span>
          {" · "}
          <Link
            to={mesaOperationsHref()}
            className="text-primary hover:underline"
          >
            {positionsCount} posición{positionsCount === 1 ? "" : "es"}
          </Link>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-1">
          <CardDescription>Alertas</CardDescription>
          <CardTitle className="text-xl tabular-nums">{alertCount}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          {criticalAlerts > 0
            ? `${criticalAlerts} crítica${criticalAlerts === 1 ? "" : "s"}`
            : "Sin alertas críticas"}
        </CardContent>
      </Card>
    </div>
  );
}
