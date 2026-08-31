import { Fragment, useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import type { ProtectPlanV1 } from "@bolsa/shared";
import {
  buildInvestmentPositionAggregate,
  buildOperationalPlanFromPosition,
  buildOperationalTruth,
  formatExecutionHintCopy,
  studiesByInstrumentMap,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

import { formatPct, formatPrice } from "@/features/charts/chart-utils";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { mesaPositionShowsRoute } from "@/features/mesa/mesa-position-row";
import { PositionRoutePanel } from "@/features/mesa/position-route-panel";
import { PositionExitDrawerActions } from "@/features/trading/position-exit-drawer-actions";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";

type OperationsTab = "open" | "pending";

function formatR(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}

/**
 * Operaciones (dock inferior de Mercado / Libro en Hoy).
 *
 * Con `scopeToActiveChart` filtra al valor del gráfico activo (contexto del
 * cockpit) y permite volver a ver la cuenta entera. Reducir / Salir encolan y
 * abren el drawer de Confirm: no se sale de Mercado.
 */
export function OperationsPanel({
  scopeToActiveChart = false,
}: {
  scopeToActiveChart?: boolean;
} = {}) {
  const [tab, setTab] = useState<OperationsTab>("open");
  const [accountWide, setAccountWide] = useState(false);

  const { pendingOrders, removePendingOrder } = usePendingOrders();

  const activeInstrumentId = useWorkspaceStore((s) =>
    scopeToActiveChart
      ? (s.workspace.charts.find(
          (chartTab) => chartTab.id === s.workspace.activeChartId,
        )?.instrumentId ?? null)
      : null,
  );
  const activeSymbol = useWorkspaceStore((s) =>
    scopeToActiveChart
      ? (s.workspace.charts.find(
          (chartTab) => chartTab.id === s.workspace.activeChartId,
        )?.label ?? null)
      : null,
  );
  const scopeInstrumentId =
    scopeToActiveChart && !accountWide ? activeInstrumentId : null;

  const accountScope = useActiveAccountQueryKey();
  const { effectiveAccountId } = useActiveAccount();
  const opsEval = useOpsSelfEval(effectiveAccountId);
  const portfolioReconStatus = portfolioReconStatusFromReport(opsEval.data);

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

  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () => api.getDecisionStudies(effectiveAccountId!, { limit: 200 }),
    enabled: Boolean(effectiveAccountId),
    staleTime: 30_000,
  });

  const studiesMap = useMemo(
    () => studiesByInstrumentMap(studiesQuery.data?.data?.studies ?? []),
    [studiesQuery.data],
  );

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

  const allPositions = useMemo(
    () => portfolioQuery.data?.data.positions ?? [],
    [portfolioQuery.data],
  );
  const positions = useMemo(
    () =>
      scopeInstrumentId
        ? allPositions.filter((p) => p.instrumentId === scopeInstrumentId)
        : allPositions,
    [allPositions, scopeInstrumentId],
  );

  const scopedPending = useMemo(
    () =>
      scopeInstrumentId
        ? pendingOrders.filter((o) => o.instrumentId === scopeInstrumentId)
        : pendingOrders,
    [pendingOrders, scopeInstrumentId],
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="scroll-area flex shrink-0 items-center gap-0.5 overflow-x-auto border-b border-border px-1">
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

            {id === "pending" && scopedPending.length > 0 && (
              <span className="ml-1 opacity-70">({scopedPending.length})</span>
            )}
          </button>
        ))}

        {scopeToActiveChart && activeInstrumentId ? (
          <button
            type="button"
            className="ml-auto shrink-0 rounded-full border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground hover:text-foreground"
            onClick={() => setAccountWide((v) => !v)}
            data-testid="operations-scope-toggle"
            title="Alterna entre el valor del gráfico activo y toda la cuenta"
          >
            {accountWide
              ? "Cuenta entera"
              : `Solo ${activeSymbol ?? "valor activo"}`}
          </button>
        ) : null}
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
              {scopeInstrumentId
                ? `Sin posición abierta en ${activeSymbol ?? "este valor"}`
                : "Sin posiciones abiertas"}
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
                  const study = studiesMap.get(pos.instrumentId) ?? null;
                  const showRoute = mesaPositionShowsRoute(pos, study);
                  const orderPending = pendingOrders.some(
                    (order) => order.instrumentId === pos.instrumentId,
                  );
                  const truth = buildOperationalTruth({
                    position: pos,
                    study,
                    portfolioReconStatus,
                    orderPending,
                  });
                  const aggregate = buildInvestmentPositionAggregate({
                    position: pos,
                    study,
                  });
                  const plan = buildOperationalPlanFromPosition({
                    aggregate,
                    markPrice: pos.lastPrice ?? null,
                  });
                  const actionLabel = truth?.primaryCta.label ?? "—";
                  const executionHintCopy = truth
                    ? formatExecutionHintCopy(truth)
                    : null;

                  return (
                    <Fragment key={pos.id}>
                      <tr className="border-b border-border/50 hover:bg-accent/30">
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
                          {formatR(
                            plan.unrealizedR ?? operational?.unrealizedR,
                          )}
                        </td>

                        <td className="px-2 py-1 text-right tabular-nums">
                          {plan.stopVigente != null
                            ? formatPrice(plan.stopVigente)
                            : "—"}
                        </td>

                        <td className="px-2 py-1 text-right tabular-nums">
                          {plan.target1 != null
                            ? formatPrice(plan.target1)
                            : "—"}
                        </td>

                        <td className="px-2 py-1 text-right tabular-nums">
                          {plan.target2 != null
                            ? formatPrice(plan.target2)
                            : "—"}
                        </td>

                        <td className="px-2 py-1 text-right text-muted-foreground">
                          <div>{actionLabel}</div>
                          {executionHintCopy ? (
                            <div
                              className="text-[10px] font-medium text-amber-800 dark:text-amber-200"
                              data-testid={`ops-execution-hint-${pos.symbol}`}
                            >
                              {executionHintCopy}
                            </div>
                          ) : null}
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
                          <PositionExitDrawerActions
                            position={pos}
                            compact
                            primaryOnly
                            protectPlan={protectPlanByInstrument.get(
                              pos.instrumentId,
                            )}
                            portfolioReconStatus={portfolioReconStatus}
                            className="items-end"
                          />
                        </td>
                      </tr>
                      {showRoute ? (
                        <tr className="border-b border-border/50 bg-muted/10">
                          <td colSpan={9} className="px-2 py-2">
                            <PositionRoutePanel
                              position={pos}
                              study={study}
                              portfolioReconStatus={portfolioReconStatus}
                              orderPending={orderPending}
                            />
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "pending" && (
        <div className="scroll-area min-h-0 flex-1 overflow-auto">
          {scopedPending.length === 0 && (
            <p className="p-4 text-center text-xs text-muted-foreground">
              {scopeInstrumentId
                ? `Sin órdenes pendientes en ${activeSymbol ?? "este valor"}.`
                : "Sin órdenes pendientes — crea una orden pendiente a precio desde el diálogo de operación."}
            </p>
          )}

          {scopedPending.length > 0 && (
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
                {scopedPending.map((order) => (
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
