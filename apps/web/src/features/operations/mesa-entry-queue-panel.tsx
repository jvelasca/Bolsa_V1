/**
 * P4 — cola de entradas read-only con filtros (Vigilar…Descartado).
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  buildMesaEntryQueue,
  enrichMesaCandidates,
  filterMesaEntryQueue,
  groupMesaEntryQueue,
  mapCandidateNextAction,
  MESA_ENTRY_GROUP_ORDER,
  MESA_ENTRY_STATUS_LABEL,
  type MesaCandidateRowV1,
  type MesaEntryGateFilter,
  type TradePlanStatusV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";

const GATE_CLASS: Record<string, string> = {
  VETO: "text-rose-600 dark:text-rose-300",
  PASS: "text-emerald-700 dark:text-emerald-300",
  DEFERRED: "text-amber-800 dark:text-amber-200",
};

const GATE_FILTERS: MesaEntryGateFilter[] = ["ALL", "PASS", "VETO", "DEFERRED"];

type MesaEntryQueuePanelProps = {
  className?: string;
  /** Oculta entradas cuando hay veto/kill — copy only; datos siguen visibles. */
  entriesBlocked?: boolean;
};

export function MesaEntryQueuePanel({
  className,
  entriesBlocked = false,
}: MesaEntryQueuePanelProps) {
  const { effectiveAccountId } = useActiveAccount();
  const [symbolQuery, setSymbolQuery] = useState("");
  const [gateFilter, setGateFilter] = useState<MesaEntryGateFilter>("ALL");
  const [statusFilter, setStatusFilter] = useState<Set<TradePlanStatusV1>>(
    () => new Set(MESA_ENTRY_GROUP_ORDER),
  );
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const { pendingOrders } = usePendingOrders();
  const confirmInstrumentIds = useMemo(
    () =>
      new Set(queueItems.map((i) => i.payload.instrumentId).filter(Boolean)),
    [queueItems],
  );
  const pendingFillIds = useMemo(
    () => new Set(pendingOrders.map((o) => o.instrumentId).filter(Boolean)),
    [pendingOrders],
  );

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId],
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });

  const groups = useMemo(() => {
    const board = boardQuery.data?.data;
    if (!board) return [];
    const rows = enrichMesaCandidates(
      filterMesaEntryQueue(buildMesaEntryQueue(board), {
        statuses: [...statusFilter],
        gate: gateFilter,
        symbolQuery,
      }),
      board,
      new Map(),
    );
    return groupMesaEntryQueue(rows).map((group) => ({
      ...group,
      items: group.items as MesaCandidateRowV1[],
    }));
  }, [boardQuery.data, statusFilter, gateFilter, symbolQuery]);

  function toggleStatus(status: TradePlanStatusV1) {
    setStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  return (
    <div
      className={cn("space-y-3 text-xs", className)}
      data-testid="mesa-entry-queue"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium text-foreground">Cola de entradas</h3>
        <span className="text-[10px] text-muted-foreground">Solo lectura</span>
      </div>
      <div
        className="flex flex-wrap items-center gap-2"
        data-testid="mesa-entry-queue-filters"
      >
        <input
          type="search"
          className="min-w-[88px] flex-1 rounded border border-border bg-background px-2 py-1 text-[11px]"
          placeholder="Símbolo…"
          value={symbolQuery}
          onChange={(e) => setSymbolQuery(e.target.value)}
          data-testid="mesa-entry-queue-symbol"
        />
        <select
          className="rounded border border-border bg-background px-2 py-1 text-[11px]"
          value={gateFilter}
          onChange={(e) => setGateFilter(e.target.value as MesaEntryGateFilter)}
          data-testid="mesa-entry-queue-gate"
        >
          {GATE_FILTERS.map((g) => (
            <option key={g} value={g}>
              Gate {g === "ALL" ? "todos" : g}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap gap-1">
        {MESA_ENTRY_GROUP_ORDER.map((status) => {
          const active = statusFilter.has(status);
          return (
            <button
              key={status}
              type="button"
              className={cn(
                "rounded border px-1.5 py-0.5 text-[10px]",
                active
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground opacity-60",
              )}
              onClick={() => toggleStatus(status)}
              data-testid={`mesa-entry-filter-${status}`}
            >
              {MESA_ENTRY_STATUS_LABEL[status]}
            </button>
          );
        })}
      </div>
      {entriesBlocked && (
        <p className="text-[10px] text-amber-800 dark:text-amber-200">
          Veto/kill switch activo: nuevas entradas bloqueadas. Desriesgo en
          posiciones sigue disponible.
        </p>
      )}
      {boardQuery.isLoading && (
        <p className="text-muted-foreground">Cargando cola…</p>
      )}
      {boardQuery.isError && (
        <p className="text-destructive">No se pudo cargar el Decision Board.</p>
      )}
      {!boardQuery.isLoading && groups.length === 0 && (
        <p
          className="text-muted-foreground"
          data-testid="mesa-entry-queue-empty"
        >
          Sin candidatos con estos filtros — puede ser un día excelente.
        </p>
      )}
      {groups.map((group) => (
        <div key={group.status}>
          <div className="mb-1 font-medium text-muted-foreground">
            {group.label}{" "}
            <span className="font-normal opacity-70">
              ({group.items.length})
            </span>
          </div>
          <ul className="space-y-0.5">
            {group.items.map((row) => {
              const next = mapCandidateNextAction(
                {
                  ...row,
                  inConfirmQueue: confirmInstrumentIds.has(
                    row.instrumentId ?? "",
                  ),
                  orderPendingFill: pendingFillIds.has(row.instrumentId ?? ""),
                },
                entriesBlocked,
              );
              return (
                <li
                  key={`${group.status}-${row.symbol}`}
                  className="flex items-center justify-between gap-2 rounded px-1 py-0.5 hover:bg-accent/30"
                >
                  <span className="font-medium">{row.symbol}</span>
                  <span className="flex items-center gap-2">
                    <span
                      className={cn(
                        "text-[10px]",
                        next.kind === "none"
                          ? "font-medium text-rose-700 dark:text-rose-300"
                          : "text-muted-foreground",
                      )}
                      data-testid={`mesa-entry-action-${row.symbol}`}
                    >
                      {next.label}
                    </span>
                    <span
                      className={cn(
                        "text-[10px] uppercase tracking-wide",
                        GATE_CLASS[row.gate.toUpperCase()] ??
                          "text-muted-foreground",
                      )}
                    >
                      {row.gate}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
