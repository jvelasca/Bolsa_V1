/**
 * Fila de Mis estrategias en Biblioteca: ver, renombrar, duplicar, usar, eliminar.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BACKTEST_STRATEGIES,
  type StrategyDefinitionSummaryDto,
} from "@bolsa/shared";
import { ApiError, api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  formatStrategyScopeBadge,
  MINE_STRATEGY_ORIGIN_LABELS,
} from "@/features/backtests/mine-strategies-filters";
import { PAPER_PATH_LAB } from "@/features/settings/paper-paths-copy";

function duplicateName(base: string, existing: Set<string>): string {
  const trimmed = base.trim();
  let candidate = `${trimmed} (copia)`;
  let index = 2;
  while (existing.has(candidate.toLowerCase())) {
    candidate = `${trimmed} (copia ${index})`;
    index += 1;
  }
  return candidate;
}

type Props = {
  strategy: StrategyDefinitionSummaryDto;
  instrumentSymbolById: Map<string, string>;
  isTop: boolean;
  focused: boolean;
  existingNames: Set<string>;
  onUse: (strategyId: string) => void;
  onDeleted: (strategyId: string) => void;
};

export function BacktestLibraryStrategyRow({
  strategy,
  instrumentSymbolById,
  isTop,
  focused,
  existingNames,
  onUse,
  onDeleted,
}: Props) {
  const queryClient = useQueryClient();
  const rowRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(strategy.name);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!focused) return;
    rowRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focused]);

  const detailQuery = useQuery({
    queryKey: ["strategy", strategy.id],
    queryFn: () => api.getStrategy(strategy.id),
    enabled: expanded,
    staleTime: 30_000,
  });

  const renameMutation = useMutation({
    mutationFn: (name: string) => api.updateStrategy(strategy.id, { name }),
    onSuccess: () => {
      setRenaming(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
      void queryClient.invalidateQueries({
        queryKey: ["strategy", strategy.id],
      });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "No se pudo renombrar");
    },
  });

  const timeframeMutation = useMutation({
    mutationFn: async (timeframe: "1d" | "1wk") => {
      const response = await api.getStrategy(strategy.id);
      const detail = response.data;
      return api.updateStrategy(strategy.id, {
        definition: { ...detail.definition, timeframe },
      });
    },
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
      void queryClient.invalidateQueries({
        queryKey: ["strategy", strategy.id],
      });
    },
    onError: (err) => {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo cambiar el timeframe",
      );
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: async () => {
      const response = await api.getStrategy(strategy.id);
      const detail = response.data;
      const name = duplicateName(detail.name, existingNames);
      return api.createStrategy({ name, definition: detail.definition });
    },
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "No se pudo duplicar");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteStrategy(strategy.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["strategies"] });
      onDeleted(strategy.id);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar");
    },
  });

  const scopeBadge = formatStrategyScopeBadge(
    strategy.instrumentIds,
    instrumentSymbolById,
  );
  const reusable = scopeBadge === "Reutilizable";
  const busy =
    renameMutation.isPending ||
    duplicateMutation.isPending ||
    deleteMutation.isPending ||
    timeframeMutation.isPending;

  function handleDelete() {
    if (
      !window.confirm(
        `¿Eliminar «${strategy.name}»? Esta acción no se puede deshacer.`,
      )
    ) {
      return;
    }
    deleteMutation.mutate();
  }

  function handleSaveRename() {
    const name = renameValue.trim();
    if (!name) return;
    renameMutation.mutate(name);
  }

  const detail = detailQuery.data?.data;

  return (
    <div
      ref={rowRef}
      id={`library-strategy-${strategy.id}`}
      className={cn(
        "border-b border-border/50 py-2.5 text-sm last:border-0",
        focused && "rounded-md bg-primary/10 ring-1 ring-primary/40",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          {renaming ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                className="h-8 min-w-[10rem] rounded-md border border-border bg-background px-2 text-sm"
                aria-label="Nuevo nombre"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveRename();
                  if (e.key === "Escape") {
                    setRenaming(false);
                    setRenameValue(strategy.name);
                  }
                }}
              />
              <Button
                size="sm"
                disabled={!renameValue.trim() || busy}
                onClick={handleSaveRename}
              >
                Guardar
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => {
                  setRenaming(false);
                  setRenameValue(strategy.name);
                }}
              >
                Cancelar
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">{strategy.name}</p>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10px] font-medium",
                  reusable
                    ? "bg-muted text-muted-foreground"
                    : "bg-sky-500/10 text-sky-800 dark:text-sky-200",
                )}
              >
                {scopeBadge}
              </span>
              {isTop ? (
                <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 dark:text-amber-200">
                  TOP
                </span>
              ) : null}
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {strategy.presetKey
              ? BACKTEST_STRATEGIES[strategy.presetKey]?.label
              : strategy.kind}{" "}
            · {strategy.timeframe} ·{" "}
            {MINE_STRATEGY_ORIGIN_LABELS[
              strategy.origin as keyof typeof MINE_STRATEGY_ORIGIN_LABELS
            ] ?? strategy.origin}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button
            size="sm"
            variant="outline"
            title={PAPER_PATH_LAB.libraryHint}
            disabled={busy}
            onClick={() => onUse(strategy.id)}
          >
            Usar
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            {expanded ? "Ocultar" : "Ver"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setRenameValue(strategy.name);
              setRenaming(true);
            }}
          >
            Renombrar
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => duplicateMutation.mutate()}
          >
            {duplicateMutation.isPending ? "…" : "Duplicar"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-destructive"
            disabled={busy}
            onClick={handleDelete}
          >
            Eliminar
          </Button>
        </div>
      </div>

      {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}

      {expanded ? (
        <div className="mt-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
          {detailQuery.isLoading ? (
            <p>Cargando definición…</p>
          ) : detailQuery.isError ? (
            <p className="text-destructive">
              {detailQuery.error instanceof ApiError
                ? detailQuery.error.message
                : "No se pudo cargar el detalle"}
            </p>
          ) : detail ? (
            <div className="space-y-1.5">
              <p>
                <span className="font-medium text-foreground">Kind:</span>{" "}
                {detail.definition.kind}
                {detail.definition.presetKey
                  ? ` · preset ${detail.definition.presetKey}`
                  : ""}
              </p>
              <label className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-foreground">Timeframe:</span>
                <select
                  className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
                  value={
                    detail.definition.timeframe === "1wk" ||
                    strategy.timeframe === "1wk"
                      ? "1wk"
                      : "1d"
                  }
                  disabled={busy || timeframeMutation.isPending}
                  onChange={(e) => {
                    const next = e.target.value === "1wk" ? "1wk" : "1d";
                    timeframeMutation.mutate(next);
                  }}
                  aria-label="Timeframe de la estrategia"
                >
                  <option value="1d">Diario (1d)</option>
                  <option value="1wk">Semanal (1wk)</option>
                </select>
                {timeframeMutation.isPending ? (
                  <span className="text-[10px]">Guardando…</span>
                ) : null}
              </label>
              <p>
                <span className="font-medium text-foreground">
                  Actualizado:
                </span>{" "}
                {new Date(detail.updatedAt).toLocaleString("es-ES")}
              </p>
              <p>
                <span className="font-medium text-foreground">Creado:</span>{" "}
                {new Date(detail.createdAt).toLocaleString("es-ES")}
              </p>
              {detail.instrumentIds.length > 0 ? (
                <p>
                  <span className="font-medium text-foreground">Valores:</span>{" "}
                  {detail.instrumentIds
                    .map((id) => instrumentSymbolById.get(id) ?? id.slice(0, 8))
                    .join(", ")}
                </p>
              ) : (
                <p>Plantilla reutilizable (sin valor fijado).</p>
              )}
              <details className="pt-1">
                <summary className="cursor-pointer text-foreground">
                  Definición JSON
                </summary>
                <pre className="mt-1 max-h-40 overflow-auto rounded bg-background/80 p-2 text-[10px] leading-snug">
                  {JSON.stringify(detail.definition, null, 2)}
                </pre>
              </details>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
