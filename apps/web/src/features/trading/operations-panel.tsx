import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import type { ProtectPlanV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";

import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

import { formatPct, formatPrice } from "@/features/charts/chart-utils";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { MesaPositionExitActions } from "@/features/mesa/mesa-position-row";

type OperationsTab = "open" | "pending";

const EXIT_ACTION_LABEL: Record<string, string> = {
  protect: "proteger",
  reduce: "reducir",
  full_exit: "salir",
};

function exitPlanLabel(
  operational: { exitPlan?: { suggestedAction?: string | null } | null } | null,
): string {
  const action = operational?.exitPlan?.suggestedAction;
  if (!action || action === "hold") return "—";
  return EXIT_ACTION_LABEL[action] ?? action;
}

function formatR(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}

export function OperationsPanel() {
  const [tab, setTab] = useState<OperationsTab>("open");

  const { pendingOrders, removePendingOrder } = usePendingOrders();

  const accountScope = useActiveAccountQueryKey();
  const { effectiveAccountId } = useActiveAccount();

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],

    queryFn: api.getPortfolio,

    staleTime: 15_000,
  });

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId],
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });

  const protectPlanByInstrument = useMemo(() => {
    const map = new Map<string, ProtectPlanV1>();
    for (const session of boardQuery.data?.data?.decisionSessions ?? []) {
      const plan = session.protectPlan as ProtectPlanV1 | undefined;
      if (plan?.status === "protect_hint" && session.instrumentId) {
        map.set(session.instrumentId, plan);
      }
    }
    return map;
  }, [boardQuery.data]);

  const positions = portfolioQuery.data?.data.positions ?? [];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="scroll-area flex shrink-0 gap-0.5 overflow-x-auto border-b border-border px-1">
        {(
          [
            ["open", "Operaciones abiertas"],

            ["pending", "Operaciones pendientes"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "px-2 py-1 text-[11px] font-medium",

              tab === id
                ? "border-b-2 border-primary text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}

            {id === "open" && positions.length > 0 && (
              <span className="ml-1 opacity-70">({positions.length})</span>
            )}

            {id === "pending" && pendingOrders.length > 0 && (
              <span className="ml-1 opacity-70">({pendingOrders.length})</span>
            )}
          </button>
        ))}
      </div>

      {tab === "open" && (
        <div className="scroll-area min-h-0 flex-1 overflow-auto">
          {portfolioQuery.isLoading && (
            <p className="p-3 text-xs text-muted-foreground">
              Cargando cartera…
            </p>
          )}

          {portfolioQuery.isError && (
            <p className="p-3 text-xs text-destructive">
              No se pudo cargar la cartera
            </p>
          )}

          {!portfolioQuery.isLoading && positions.length === 0 && (
            <p className="p-4 text-center text-xs text-muted-foreground">
              Sin posiciones abiertas
            </p>
          )}

          {positions.length > 0 && (
            <table className="w-full text-[11px]">
              <thead className="sticky top-0 bg-card/95 text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-2 py-1 text-left font-medium">Símbolo</th>

                  <th className="px-2 py-1 text-right font-medium">Qty</th>

                  <th className="px-2 py-1 text-right font-medium">R</th>

                  <th className="px-2 py-1 text-right font-medium">Stop</th>

                  <th className="px-2 py-1 text-right font-medium">T1</th>

                  <th className="px-2 py-1 text-right font-medium">T2</th>

                  <th className="px-2 py-1 text-right font-medium">Salida</th>

                  <th className="px-2 py-1 text-right font-medium">P&amp;L</th>

                  <th className="px-2 py-1 text-right font-medium">Acciones</th>
                </tr>
              </thead>

              <tbody>
                {positions.map((pos) => {
                  const pnlUp = (pos.unrealizedPnl ?? 0) >= 0;
                  const operational = pos.operational ?? null;

                  return (
                    <tr
                      key={pos.id}
                      className="border-b border-border/50 hover:bg-accent/30"
                    >
                      <td className="px-2 py-1">
                        <div className="font-medium">{pos.symbol}</div>

                        <div className="truncate text-[10px] text-muted-foreground">
                          {operational
                            ? operational.status
                            : "sin plan persistido"}
                        </div>
                      </td>

                      <td className="px-2 py-1 text-right tabular-nums">
                        {pos.quantity}
                      </td>

                      <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">
                        {formatR(operational?.unrealizedR)}
                      </td>

                      <td className="px-2 py-1 text-right tabular-nums">
                        {operational?.currentStop != null
                          ? formatPrice(operational.currentStop)
                          : "—"}
                      </td>

                      <td className="px-2 py-1 text-right tabular-nums">
                        {operational?.target1 != null
                          ? formatPrice(operational.target1)
                          : "—"}
                      </td>

                      <td className="px-2 py-1 text-right tabular-nums">
                        {operational?.target2 != null
                          ? formatPrice(operational.target2)
                          : "—"}
                      </td>

                      <td className="px-2 py-1 text-right text-muted-foreground">
                        {exitPlanLabel(operational)}
                      </td>

                      <td
                        className={cn(
                          "px-2 py-1 text-right tabular-nums",

                          pnlUp ? "text-emerald-400" : "text-red-400",
                        )}
                      >
                        {pos.unrealizedPnl != null
                          ? formatPrice(pos.unrealizedPnl)
                          : "—"}

                        {pos.unrealizedPnlPct != null && (
                          <span className="ml-1 text-[10px] opacity-80">
                            ({formatPct(pos.unrealizedPnlPct)})
                          </span>
                        )}
                      </td>

                      <td className="px-2 py-1">
                        <MesaPositionExitActions
                          position={pos}
                          protectPlan={protectPlanByInstrument.get(
                            pos.instrumentId,
                          )}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "pending" && (
        <div className="scroll-area min-h-0 flex-1 overflow-auto">
          {pendingOrders.length === 0 && (
            <p className="p-4 text-center text-xs text-muted-foreground">
              Sin órdenes pendientes — crea una orden pendiente a precio desde
              el diálogo de operación.
            </p>
          )}

          {pendingOrders.length > 0 && (
            <table className="w-full text-[11px]">
              <thead className="sticky top-0 bg-card/95 text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-2 py-1 text-left font-medium">Símbolo</th>

                  <th className="px-2 py-1 text-left font-medium">Tipo</th>

                  <th className="px-2 py-1 text-right font-medium">Qty</th>

                  <th className="px-2 py-1 text-right font-medium">Precio</th>

                  <th className="px-2 py-1 text-right font-medium"></th>
                </tr>
              </thead>

              <tbody>
                {pendingOrders.map((order) => (
                  <tr
                    key={order.id}
                    className="border-b border-border/50 hover:bg-accent/30"
                  >
                    <td className="px-2 py-1 font-medium">{order.symbol}</td>

                    <td className="px-2 py-1 capitalize">
                      {order.side === "buy" ? "Compra" : "Venta"} a precio
                    </td>

                    <td className="px-2 py-1 text-right tabular-nums">
                      {order.quantity}
                    </td>

                    <td className="px-2 py-1 text-right tabular-nums">
                      {formatPrice(order.limitPrice)}
                    </td>

                    <td className="px-2 py-1 text-right">
                      <button
                        type="button"
                        className="text-[10px] text-muted-foreground hover:text-destructive"
                        onClick={() => void removePendingOrder(order.id)}
                      >
                        Cancelar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
