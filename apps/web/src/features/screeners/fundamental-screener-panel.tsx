/**
 * F4 — Screener FA (lista blanca). Gate only; sin timing técnico.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Filter, ListPlus } from "lucide-react";
import { useMemo, useState } from "react";
import {
  buildFundamentalGate,
  type FundamentalScreenerRunResultV1,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  listId: string;
  lists: Array<{ id: string; name: string; itemCount: number }>;
  onListIdChange: (listId: string) => void;
  className?: string;
};

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

export function FundamentalScreenerPanel({
  listId,
  lists,
  onListIdChange,
  className,
}: Props) {
  const queryClient = useQueryClient();
  const [maxPe, setMaxPe] = useState<string>("25");
  const [minRoe, setMinRoe] = useState<string>("10");
  const [minPiotroski, setMinPiotroski] = useState<string>("6");
  const [useSectorBands, setUseSectorBands] = useState(true);
  const [persist, setPersist] = useState(false);
  const [result, setResult] = useState<FundamentalScreenerRunResultV1 | null>(
    null,
  );

  const gate = useMemo(() => {
    const pe = maxPe.trim() === "" ? null : Number(maxPe);
    const roePct = minRoe.trim() === "" ? null : Number(minRoe);
    const piot = minPiotroski.trim() === "" ? null : Number(minPiotroski);
    return buildFundamentalGate({
      maxTrailingPe: pe != null && Number.isFinite(pe) ? pe : null,
      minRoe: roePct != null && Number.isFinite(roePct) ? roePct / 100 : null,
      minPiotroski: piot != null && Number.isFinite(piot) ? piot : null,
      useSectorBands,
    });
  }, [maxPe, minRoe, minPiotroski, useSectorBands]);

  const runMutation = useMutation({
    mutationFn: (withPersist: boolean) => {
      if (!gate) throw new Error("Define al menos un filtro FA");
      return api.runFundamentalScreener({
        universe: { listId },
        fundamentalGate: gate,
        refreshStale: true,
        maxResults: 100,
        persist: withPersist ? { name: undefined } : null,
      });
    },
    onSuccess: async (res, withPersist) => {
      setResult(res.data);
      if (withPersist && res.data.persistedListId) {
        await queryClient.invalidateQueries({ queryKey: ["lists"] });
      }
    },
  });

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Universo</span>
          <select
            className="h-8 min-w-[10rem] rounded-md border border-border/60 bg-background px-2 text-xs"
            value={listId}
            onChange={(e) => onListIdChange(e.target.value)}
          >
            {lists.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name} ({l.itemCount})
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">PE máx</span>
          <input
            className="h-8 w-20 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={maxPe}
            onChange={(e) => setMaxPe(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">ROE mín %</span>
          <input
            className="h-8 w-20 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={minRoe}
            onChange={(e) => setMinRoe(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Piotroski mín</span>
          <input
            className="h-8 w-20 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={minPiotroski}
            onChange={(e) => setMinPiotroski(e.target.value)}
          />
        </label>
        <label className="flex h-8 items-center gap-1.5 text-[11px] text-muted-foreground">
          <input
            type="checkbox"
            checked={useSectorBands}
            onChange={(e) => setUseSectorBands(e.target.checked)}
          />
          Bandas sector
        </label>
        <label className="flex h-8 items-center gap-1.5 text-[11px] text-muted-foreground">
          <input
            type="checkbox"
            checked={persist}
            onChange={(e) => setPersist(e.target.checked)}
          />
          Guardar lista
        </label>
        <Button
          type="button"
          size="sm"
          className="h-8 gap-1.5"
          disabled={!listId || !gate || runMutation.isPending}
          onClick={() => runMutation.mutate(persist)}
        >
          <Filter
            className={cn(
              "h-3.5 w-3.5",
              runMutation.isPending && "animate-pulse",
            )}
          />
          {runMutation.isPending ? "Filtrando…" : "Correr FA"}
        </Button>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Solo filtro fundamental (sin OHLCV / technical_rating). Opcional:
        materializa hits como lista snapshot semanal.
      </p>

      {runMutation.isError ? (
        <p className="text-[11px] text-destructive">
          {(runMutation.error as Error)?.message || "Error en screener FA"}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {result.weekKey} · escaneados {result.scannedCount} · hits{" "}
            {result.hitCount} · rechazados {result.skippedCount}
            {result.fundamentalsRefreshedCount
              ? ` · refresh ${result.fundamentalsRefreshedCount}`
              : ""}
            {result.persistedListId ? (
              <span className="ml-1 inline-flex items-center gap-1 text-foreground">
                <ListPlus className="h-3 w-3" />
                lista {result.persistedListId}
              </span>
            ) : null}
          </p>
          {result.hits.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">
              Ningún título pasó el gate.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-border/50">
              <table className="w-full text-left text-[11px]">
                <thead className="bg-muted/40 text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1.5 font-medium">Ticker</th>
                    <th className="px-2 py-1.5 font-medium">FUND</th>
                    <th className="px-2 py-1.5 font-medium">PE</th>
                    <th className="px-2 py-1.5 font-medium">ROE</th>
                    <th className="px-2 py-1.5 font-medium">F</th>
                    <th className="px-2 py-1.5 font-medium">DCF</th>
                  </tr>
                </thead>
                <tbody>
                  {result.hits.map((h) => (
                    <tr
                      key={h.instrumentId}
                      className="border-t border-border/40"
                    >
                      <td className="px-2 py-1 font-medium">{h.symbol}</td>
                      <td className="px-2 py-1 tabular-nums">
                        {h.scoreDisplay100 ?? "—"}
                      </td>
                      <td className="px-2 py-1 tabular-nums">
                        {h.trailingPe != null ? h.trailingPe.toFixed(1) : "—"}
                      </td>
                      <td className="px-2 py-1 tabular-nums">
                        {fmtPct(h.roe)}
                      </td>
                      <td className="px-2 py-1 tabular-nums">
                        {h.piotroski != null ? `${h.piotroski}/9` : "—"}
                      </td>
                      <td className="px-2 py-1 tabular-nums">
                        {fmtPct(h.dcfUpside)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
