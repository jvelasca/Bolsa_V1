/**
 * Pestaña Biblioteca (Estrategias): lista first, clonar/IA colapsados.
 * Deep-link: ?tab=strategies&library=mine&strategyId=…
 */

import type {
  BacktestStrategyType,
  InstrumentStrategyTopV1,
} from "@bolsa/shared";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { BacktestAiAssistantPanel } from "@/features/backtests/backtest-ai-assistant-panel";
import { BacktestLibraryStrategyRow } from "@/features/backtests/backtest-library-strategy-row";
import {
  InstrumentStrategyTopPanel,
  type FinalistSlotUse,
} from "@/features/backtests/instrument-strategy-top-panel";
import { StrategyFilterCarousel } from "@/features/backtests/strategy-filter-carousel";
import {
  defaultMineStrategiesFilters,
  isMineStrategiesFilterActive,
  MINE_STRATEGY_ORIGIN_LABELS,
  type MineStrategiesFilterState,
} from "@/features/backtests/mine-strategies-filters";
import { PAPER_PATH_LAB } from "@/features/settings/paper-paths-copy";
import type { StrategyDefinitionSummaryDto } from "@bolsa/shared";
import { useEffect, useMemo, useRef } from "react";

import {
  countLibraryBuckets,
  LIBRARY_FILTER_LABELS,
  LIBRARY_FILTER_TITLES,
  type StrategiesListFilter,
} from "@/features/backtests/library-strategy-buckets";

export type { StrategiesListFilter } from "@/features/backtests/library-strategy-buckets";

type StrategyOption = [
  BacktestStrategyType,
  { label: string; description: string },
];

type Props = {
  strategyOptions: StrategyOption[];
  strategies: StrategyDefinitionSummaryDto[];
  filteredStrategies: StrategyDefinitionSummaryDto[];
  strategiesListFilter: StrategiesListFilter;
  onStrategiesListFilterChange: (id: StrategiesListFilter) => void;
  mineFilters: MineStrategiesFilterState;
  onMineFiltersChange: (next: MineStrategiesFilterState) => void;
  mineFilterTimeframes: string[];
  mineFilterOrigins: string[];
  /** Instrumentos presentes en Mis estrategias (id + symbol) para el filtro. */
  mineFilterInstruments: Array<{ id: string; symbol: string }>;
  instrumentId: string;
  instrumentSymbol?: string | null;
  runTimeframe: string;
  instrumentTop: InstrumentStrategyTopV1 | null;
  topStrategyIds: Set<string>;
  instrumentSymbolById: Map<string, string>;
  /** Enfoque deep-link (strategyId URL). */
  focusStrategyId?: string | null;
  /** Enfoque genérica (preset URL). */
  focusPresetKey?: string | null;
  cloneOpen: boolean;
  onCloneOpenChange: (open: boolean) => void;
  newStrategyName: string;
  onNewStrategyNameChange: (name: string) => void;
  newStrategyPreset: BacktestStrategyType;
  onNewStrategyPresetChange: (preset: BacktestStrategyType) => void;
  createPending: boolean;
  createError: unknown;
  onCreate: () => void;
  onUsePreset: (key: BacktestStrategyType) => void;
  onUseSaved: (strategyId: string) => void;
  onOpenFinalistChecklist?: (slot: FinalistSlotUse) => void;
  onProposeFinalistSupervised?: (slot: FinalistSlotUse) => void;
  proposeFinalistPendingStrategyId?: string | null;
  onDeleted?: (strategyId: string) => void;
  onGoToCoach: () => void;
};

export function BacktestLibraryTab({
  strategyOptions,
  strategies,
  filteredStrategies,
  strategiesListFilter,
  onStrategiesListFilterChange,
  mineFilters,
  onMineFiltersChange,
  mineFilterTimeframes,
  mineFilterOrigins,
  mineFilterInstruments,
  instrumentId,
  instrumentSymbol,
  runTimeframe,
  instrumentTop,
  topStrategyIds,
  instrumentSymbolById,
  focusStrategyId = null,
  focusPresetKey = null,
  cloneOpen,
  onCloneOpenChange,
  newStrategyName,
  onNewStrategyNameChange,
  newStrategyPreset,
  onNewStrategyPresetChange,
  createPending,
  createError,
  onCreate,
  onUsePreset,
  onUseSaved,
  onOpenFinalistChecklist,
  onProposeFinalistSupervised,
  proposeFinalistPendingStrategyId = null,
  onDeleted,
  onGoToCoach,
}: Props) {
  const existingNames = useMemo(
    () => new Set(strategies.map((s) => s.name.trim().toLowerCase())),
    [strategies],
  );
  const presetRefs = useRef<Map<string, HTMLDivElement | null>>(new Map());

  useEffect(() => {
    if (!focusPresetKey) return;
    const el = presetRefs.current.get(focusPresetKey);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusPresetKey, strategiesListFilter]);

  const buckets = useMemo(() => countLibraryBuckets(strategies), [strategies]);

  const description =
    strategiesListFilter === "generics"
      ? `${strategyOptions.length} genéricas del catálogo`
      : strategiesListFilter === "finalists"
        ? `${filteredStrategies.length} finalistas${instrumentSymbol ? ` · ${instrumentSymbol}` : ""}`
        : strategiesListFilter === "optimized"
          ? isMineStrategiesFilterActive(mineFilters)
            ? `${filteredStrategies.length} de ${buckets.optimized} optimizadas`
            : `${buckets.optimized} genéricas optimizadas (Lab / clones)`
          : strategiesListFilter === "mine"
            ? isMineStrategiesFilterActive(mineFilters)
              ? `${filteredStrategies.length} de ${buckets.mine} en Mis estrategias`
              : `${buckets.mine} mis estrategias (autoría)`
            : `${strategyOptions.length} genéricas + ${buckets.optimized} optimizadas + ${
                isMineStrategiesFilterActive(mineFilters)
                  ? `${filteredStrategies.length}/${strategies.length}`
                  : strategies.length
              } guardadas`;

  return (
    <div className="mx-auto min-h-0 w-full max-w-[1100px] flex-1 space-y-4 overflow-auto px-1">
      <div>
        <h3 className="text-lg font-semibold tracking-tight">Biblioteca</h3>
        <p className="text-sm text-muted-foreground">
          Genéricas · Optimizadas · Mis estrategias · Finalistas
          {instrumentSymbol ? ` · ${instrumentSymbol}` : ""}.{" "}
          <span className="text-xs">{PAPER_PATH_LAB.libraryHint}</span>
        </p>
      </div>

      <Card className="border-border/80">
        <CardHeader className="space-y-3 pb-3">
          <div>
            <CardTitle className="text-base">Estrategias</CardTitle>
            <CardDescription>
              {description}
              {instrumentTop && strategiesListFilter === "finalists"
                ? ` · TOP ${instrumentTop.status} (v${instrumentTop.version})`
                : ""}
            </CardDescription>
          </div>
          <StrategyFilterCarousel
            value={strategiesListFilter}
            onChange={(id) =>
              onStrategiesListFilterChange(id as StrategiesListFilter)
            }
            ariaLabel="Filtro de la biblioteca de estrategias"
            chips={[
              {
                id: "all",
                label: LIBRARY_FILTER_LABELS.all,
                count: strategyOptions.length + strategies.length,
                title: LIBRARY_FILTER_TITLES.all,
              },
              {
                id: "generics",
                label: LIBRARY_FILTER_LABELS.generics,
                count: strategyOptions.length,
                title: LIBRARY_FILTER_TITLES.generics,
              },
              {
                id: "optimized",
                label: LIBRARY_FILTER_LABELS.optimized,
                count: buckets.optimized,
                title: LIBRARY_FILTER_TITLES.optimized,
              },
              {
                id: "mine",
                label: LIBRARY_FILTER_LABELS.mine,
                count: buckets.mine,
                title: LIBRARY_FILTER_TITLES.mine,
              },
              {
                id: "finalists",
                label: instrumentSymbol
                  ? `Finalistas · ${instrumentSymbol}`
                  : LIBRARY_FILTER_LABELS.finalists,
                count: topStrategyIds.size,
                disabled: !instrumentId,
                title: instrumentId
                  ? LIBRARY_FILTER_TITLES.finalists
                  : "Elige un valor en Probar estrategia",
              },
            ]}
          />
          {(strategiesListFilter === "mine" ||
            strategiesListFilter === "optimized" ||
            strategiesListFilter === "all" ||
            strategiesListFilter === "finalists") &&
            strategies.length > 0 && (
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
                <input
                  type="search"
                  value={mineFilters.query}
                  onChange={(e) =>
                    onMineFiltersChange({
                      ...mineFilters,
                      query: e.target.value,
                    })
                  }
                  placeholder="Buscar nombre o ticker…"
                  className="h-9 min-w-[12rem] flex-1 rounded-md border border-border bg-background px-2.5 text-sm"
                  aria-label="Buscar en Mis estrategias"
                />
                <select
                  value={mineFilters.instrumentId}
                  onChange={(e) =>
                    onMineFiltersChange({
                      ...mineFilters,
                      instrumentId: e.target.value,
                    })
                  }
                  className="h-9 max-w-[11rem] rounded-md border border-border bg-background px-2 text-xs"
                  aria-label="Instrumento"
                  title="Estrategias ajustadas a este valor"
                >
                  <option value="">Instrumento: todos</option>
                  {instrumentId &&
                    !mineFilterInstruments.some(
                      (i) => i.id === instrumentId,
                    ) && (
                      <option value={instrumentId}>
                        {instrumentSymbol ?? "Valor actual"}
                      </option>
                    )}
                  {mineFilterInstruments.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.symbol}
                    </option>
                  ))}
                </select>
                <select
                  value={mineFilters.scope}
                  onChange={(e) =>
                    onMineFiltersChange({
                      ...mineFilters,
                      scope: e.target
                        .value as MineStrategiesFilterState["scope"],
                    })
                  }
                  className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                  aria-label="Alcance"
                  title="Reutilizable = sin valor fijado; Ajuste = ligada a instrumento(s)"
                >
                  <option value="all">Alcance: todos</option>
                  <option value="reusable">Reutilizables</option>
                  <option value="fitted">Ajuste a valor(es)</option>
                  <option value="fitted_current" disabled={!instrumentId}>
                    {instrumentSymbol
                      ? `Ajuste · ${instrumentSymbol}`
                      : "Ajuste · valor actual (elige en Probar)"}
                  </option>
                </select>
                <select
                  value={mineFilters.timeframe}
                  onChange={(e) =>
                    onMineFiltersChange({
                      ...mineFilters,
                      timeframe: e.target.value,
                    })
                  }
                  className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                  aria-label="Timeframe"
                >
                  <option value="">TF: todos</option>
                  {mineFilterTimeframes.map((tf) => (
                    <option key={tf} value={tf}>
                      {tf}
                    </option>
                  ))}
                </select>
                <select
                  value={mineFilters.origin}
                  onChange={(e) =>
                    onMineFiltersChange({
                      ...mineFilters,
                      origin: e.target.value,
                    })
                  }
                  className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                  aria-label="Origen"
                >
                  <option value="">Origen: todos</option>
                  {mineFilterOrigins.map((o) => (
                    <option key={o} value={o}>
                      {MINE_STRATEGY_ORIGIN_LABELS[
                        o as keyof typeof MINE_STRATEGY_ORIGIN_LABELS
                      ] ?? o}
                    </option>
                  ))}
                </select>
                {isMineStrategiesFilterActive(mineFilters) && (
                  <button
                    type="button"
                    className="h-9 text-xs text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() =>
                      onMineFiltersChange(defaultMineStrategiesFilters())
                    }
                  >
                    Limpiar
                  </button>
                )}
              </div>
            )}
        </CardHeader>
        <CardContent className="space-y-5">
          {strategiesListFilter === "finalists" && instrumentId && (
            <InstrumentStrategyTopPanel
              instrumentId={instrumentId}
              symbol={instrumentSymbol}
              timeframe={runTimeframe}
              top={instrumentTop}
              compact
              onUseStrategy={onUseSaved}
              onOpenChecklist={onOpenFinalistChecklist}
              onProposeSupervised={onProposeFinalistSupervised}
              proposePendingStrategyId={proposeFinalistPendingStrategyId}
              onGoToCoach={onGoToCoach}
            />
          )}

          {(strategiesListFilter === "all" ||
            strategiesListFilter === "generics") && (
            <div className="space-y-0">
              {strategiesListFilter === "all" && (
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Genéricas
                </p>
              )}
              {strategyOptions.map(([key, meta]) => (
                <div
                  key={key}
                  ref={(el) => {
                    presetRefs.current.set(key, el);
                  }}
                  id={`library-preset-${key}`}
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-2 border-b border-border/50 py-2.5 text-sm last:border-0",
                    focusPresetKey === key &&
                      "rounded-md bg-primary/10 ring-1 ring-primary/40",
                  )}
                >
                  <div className="min-w-0">
                    <p className="font-medium">{meta.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {meta.description}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onUsePreset(key)}
                    >
                      Usar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        onNewStrategyPresetChange(key);
                        onNewStrategyNameChange(`Mi ${meta.label}`);
                        onCloneOpenChange(true);
                      }}
                      title="Abre Clonar genérica con este preset"
                    >
                      Clonar
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {(strategiesListFilter === "all" ||
            strategiesListFilter === "mine" ||
            strategiesListFilter === "finalists") && (
            <div className="space-y-0">
              {strategiesListFilter === "all" && (
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Mis estrategias
                </p>
              )}
              {filteredStrategies.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {strategiesListFilter === "finalists"
                    ? instrumentId
                      ? isMineStrategiesFilterActive(mineFilters)
                        ? "Ninguna finalista coincide con los filtros."
                        : topStrategyIds.size > 0
                          ? `TOP de ${instrumentSymbol ?? "este valor"} referencia ${topStrategyIds.size} estrategia(s) que ya no están en Biblioteca (huérfanas tras purga). En Finalistas → Eliminar Finalistas, o vuelve a Play: el ciclo trata el TOP huérfano como vacío y puede grabar candidatas Coach.`
                          : `Aún no hay finalistas ligadas a ${instrumentSymbol ?? "este valor"}. El Coach muestra candidatas ★; solo se graban en BD con «Guardar TOP-3» (semifinal) o ciclo completo Lab → «Guardar Finalistas».`
                      : "Elige un valor en Probar estrategia."
                    : strategies.length === 0
                      ? "Aún no tienes ninguna. Clona una genérica abajo o importa desde el gráfico."
                      : "Ninguna estrategia coincide con los filtros."}
                </p>
              ) : (
                filteredStrategies.map((strategy) => (
                  <BacktestLibraryStrategyRow
                    key={strategy.id}
                    strategy={strategy}
                    instrumentSymbolById={instrumentSymbolById}
                    isTop={topStrategyIds.has(strategy.id)}
                    focused={focusStrategyId === strategy.id}
                    existingNames={existingNames}
                    onUse={onUseSaved}
                    onDeleted={(id) => onDeleted?.(id)}
                  />
                ))
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <details
        className="rounded-lg border border-border/80 bg-muted/10 open:bg-muted/15"
        open={cloneOpen}
        onToggle={(e) =>
          onCloneOpenChange((e.target as HTMLDetailsElement).open)
        }
      >
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium marker:content-none [&::-webkit-details-marker]:hidden">
          Clonar genérica → Optimizadas
          <span className="ml-2 font-normal text-muted-foreground">
            · copia editable del catálogo (origin preset)
          </span>
          <span className="ml-2 font-normal text-muted-foreground">
            · guarda una plantilla en Mis estrategias (reutilizable)
          </span>
        </summary>
        <div className="space-y-3 border-t border-border/60 px-4 py-3">
          <label className="block text-sm">
            Nombre
            <input
              value={newStrategyName}
              onChange={(e) => onNewStrategyNameChange(e.target.value)}
              placeholder="Mi SMA conservadora"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            Basada en preset
            <select
              value={newStrategyPreset}
              onChange={(e) =>
                onNewStrategyPresetChange(
                  e.target.value as BacktestStrategyType,
                )
              }
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2"
            >
              {strategyOptions.map(([key, meta]) => (
                <option key={key} value={key}>
                  {meta.label}
                </option>
              ))}
            </select>
          </label>
          <Button
            disabled={!newStrategyName.trim() || createPending}
            onClick={onCreate}
          >
            {createPending ? "Guardando…" : "Guardar en Optimizadas"}
          </Button>
          {createError != null && (
            <p className="text-sm text-destructive">
              {createError instanceof ApiError
                ? createError.message
                : "Error al guardar"}
            </p>
          )}
        </div>
      </details>

      <details className="rounded-lg border border-border/80 bg-muted/10">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium marker:content-none [&::-webkit-details-marker]:hidden">
          Crear mi estrategia con IA
          <span className="ml-2 font-normal text-muted-foreground">
            · prompt → Mis estrategias (autoría)
          </span>
        </summary>
        <div className="border-t border-border/60 px-2 py-2">
          <BacktestAiAssistantPanel description="Describe tu estrategia en lenguaje natural. Se guarda en Mis estrategias (Prompt IA), no en Optimizadas." />
        </div>
      </details>
    </div>
  );
}
