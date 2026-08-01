import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Bell,
  ExternalLink,
  GripVertical,
  LineChart,
  MoreHorizontal,
  Star,
} from 'lucide-react';
import {
  SIGNAL_KIND_LABELS,
  type ScanHitDto,
  type ScanRunResultDto,
  type TechnicalRatingBreakdownV1,
} from '@bolsa/shared';
import { api } from '@/lib/api';
import { formatPrice } from '@/features/charts/chart-utils';
import { Button, buttonVariants } from '@/components/ui/button';
import { OpaqueMenuLabel, OpaqueMenuPanel } from '@/components/ui/opaque-menu-panel';
import { cn } from '@/lib/utils';
import { openHitInTrading } from '@/features/screeners/open-hit-in-trading';
import type { ScanRunnerConfig } from '@/features/screeners/scan-runner-form';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { useScreenerPreferencesStore } from '@/stores/screener-preferences-store';
import {
  SCAN_RESULTS_COLUMN_LABELS,
  buildScanResultsGridTemplate,
  cycleScanResultsSort,
  normalizeScanResultsLayout,
  qualityFromScore,
  reorderScanResultsColumns,
  resizeScanResultsColumn,
  scanResultsColumnAlign,
  sortScanHits,
  toggleScanResultsColumn,
  toggleScanResultsFavoriteColumn,
  visibleScanResultsColumns,
  type ScanResultsColumnId,
  type ScanResultsColumnLayoutItem,
} from '@/lib/scan-results-column-layout';

interface ScanResultsTableProps {
  result: ScanRunResultDto;
  scanConfig: ScanRunnerConfig;
  full?: boolean;
  onSubscribeSuccess?: () => void;
  onSubscribeError?: (message: string) => void;
}

function ColumnResizeHandle({
  columnId,
  width,
  onResize,
}: {
  columnId: ScanResultsColumnId;
  width: number;
  onResize: (columnId: ScanResultsColumnId, width: number) => void;
}) {
  const startRef = useRef({ x: 0, width });

  function onMouseDown(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    startRef.current = { x: event.clientX, width };

    function onMouseMove(moveEvent: MouseEvent) {
      onResize(columnId, startRef.current.width + (moveEvent.clientX - startRef.current.x));
    }

    function onMouseUp() {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  return (
    <button
      type="button"
      aria-label={`Redimensionar ${SCAN_RESULTS_COLUMN_LABELS[columnId]}`}
      className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

function BreakdownBars({ breakdown }: { breakdown: TechnicalRatingBreakdownV1 }) {
  const items = [
    { label: 'T', value: breakdown.trend },
    { label: 'M', value: breakdown.momentum },
    { label: 'V', value: breakdown.volatility },
    { label: 'R', value: breakdown.meanReversion },
    ...(breakdown.pattern != null ? [{ label: 'P', value: breakdown.pattern }] : []),
  ];
  return (
    <div className="mt-1 flex flex-wrap justify-center gap-0.5" title="Tendencia · Momentum · Vol · Rev · Patrón">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex min-w-[1.25rem] flex-col items-center rounded bg-muted/60 px-0.5 py-0.5 text-[9px] leading-none"
        >
          <span className="text-muted-foreground">{item.label}</span>
          <span className="font-medium tabular-nums text-foreground">{Math.round(item.value)}</span>
        </span>
      ))}
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <span
      className={cn(
        'rounded px-1.5 py-0.5 text-xs font-medium tabular-nums',
        score >= 70 && 'bg-emerald-500/15 text-emerald-600',
        score >= 55 && score < 70 && 'bg-sky-500/15 text-sky-700',
        score < 55 && 'bg-muted text-muted-foreground',
      )}
    >
      {Math.round(score)}
    </span>
  );
}

function RatingCell({ hit }: { hit: ScanHitDto }) {
  if (hit.aiScore == null) return <span className="text-muted-foreground">—</span>;
  return <ScoreBadge score={hit.aiScore} />;
}

function DataQualityCell({ hit }: { hit: ScanHitDto }) {
  if (hit.dataQualityScore == null) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="min-w-0">
      <ScoreBadge score={hit.dataQualityScore} />
      {hit.dataQualityBreakdown && (
        <p
          className="mt-0.5 text-[9px] text-muted-foreground"
          title="Frescura · Barras · Sync · Gaps · Fundamentales"
        >
          F{Math.round(hit.dataQualityBreakdown.freshness)} · B
          {Math.round(hit.dataQualityBreakdown.barDepth)} · S
          {Math.round(hit.dataQualityBreakdown.sync)}
        </p>
      )}
    </div>
  );
}

function GlobalScoreCell({ hit }: { hit: ScanHitDto }) {
  if (hit.globalScore == null) return <span className="text-muted-foreground">—</span>;
  const quality = qualityFromScore(hit.globalScore);
  return (
    <div className="min-w-0">
      <ScoreBadge score={hit.globalScore} />
      <span className={cn('mt-0.5 block rounded px-1 py-0.5 text-[9px] font-medium', quality.className)}>
        {quality.label}
      </span>
    </div>
  );
}

function QualityCell({ hit }: { hit: ScanHitDto }) {
  if (hit.aiScore == null) return <span className="text-muted-foreground">—</span>;
  const quality = qualityFromScore(hit.aiScore);
  return (
    <div className="min-w-0">
      <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', quality.className)}>
        {quality.label}
      </span>
      {hit.ratingBreakdown && <BreakdownBars breakdown={hit.ratingBreakdown} />}
    </div>
  );
}

function SubScoreCell({ value }: { value?: number }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  return <span className="tabular-nums">{Math.round(value)}</span>;
}

export function ScanResultsTable({
  result,
  scanConfig,
  full = false,
  onSubscribeSuccess,
  onSubscribeError,
}: ScanResultsTableProps) {
  const navigate = useNavigate();
  const openChartTab = useWorkspaceStore((state) => state.openChartTab);
  const updateChartTimeframe = useWorkspaceStore((state) => state.updateChartTimeframe);
  const focusInstrumentFromList = useWorkspaceStore((state) => state.focusInstrumentFromList);

  const storedLayout = useScreenerPreferencesStore((state) => state.scanResultsTable.columnLayout);
  const sortState = useScreenerPreferencesStore((state) => state.scanResultsTable.sort);
  const favoriteColumnIds = useScreenerPreferencesStore(
    (state) => state.scanResultsTable.favoriteColumnIds,
  );
  const setColumnLayout = useScreenerPreferencesStore((state) => state.setScanResultsColumnLayout);
  const setSortState = useScreenerPreferencesStore((state) => state.setScanResultsSort);
  const setFavoriteColumnIds = useScreenerPreferencesStore(
    (state) => state.setScanResultsFavoriteColumnIds,
  );

  const favoriteIds = new Set(favoriteColumnIds);

  const hasRating = result.hits.some((hit) => hit.aiScore != null);
  const hasBreakdown = result.hits.some((hit) => hit.ratingBreakdown != null);
  const hasDataQuality = result.hits.some((hit) => hit.dataQualityScore != null);

  const layout = useMemo(() => {
    const normalized = normalizeScanResultsLayout(storedLayout, {
      full,
      hasRating,
      hasBreakdown,
      hasDataQuality,
    });
    if (full) return normalized;

    const favorites = new Set(favoriteColumnIds);
    return normalized.map((column) => {
      if (column.id === 'actions' || column.id === 'name') {
        return { ...column, visible: false };
      }
      const isFavorite = favorites.has(column.id);
      const isCore = column.id === 'symbol' || column.id === 'signal';
      if (!isFavorite && !isCore) return { ...column, visible: false };
      if ((column.id === 'rating' || column.id === 'quality') && !hasRating) {
        return { ...column, visible: false };
      }
      if ((column.id === 'dataQuality' || column.id === 'globalScore') && !hasDataQuality) {
        return { ...column, visible: false };
      }
      if (
        (column.id === 'trend' ||
          column.id === 'momentum' ||
          column.id === 'volatility' ||
          column.id === 'meanReversion' ||
          column.id === 'pattern') &&
        !hasBreakdown
      ) {
        return { ...column, visible: false };
      }
      return { ...column, visible: isFavorite || isCore };
    });
  }, [storedLayout, full, hasRating, hasBreakdown, hasDataQuality, favoriteColumnIds]);

  const visibleColumns = visibleScanResultsColumns(layout);
  const gridTemplate = buildScanResultsGridTemplate(visibleColumns);
  const sortedHits = useMemo(
    () => sortScanHits(result.hits, sortState),
    [result.hits, sortState],
  );

  const [dragId, setDragId] = useState<ScanResultsColumnId | null>(null);
  const [dropTargetId, setDropTargetId] = useState<ScanResultsColumnId | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  const subscribeMutation = useMutation({
    mutationFn: (hit: ScanHitDto) =>
      api.createSignalAlert({
        instrumentId: hit.instrumentId,
        signalKinds: [hit.signal.kind],
        ...(scanConfig.scanSource === 'saved'
          ? { strategyDefinitionId: scanConfig.savedStrategyId }
          : { presetKey: scanConfig.presetKey }),
        timeframe: scanConfig.timeframe,
        note: `Desde rastreo ${result.scanId.slice(0, 8)}`,
      }),
    onSuccess: () => onSubscribeSuccess?.(),
    onError: (error) =>
      onSubscribeError?.(error instanceof Error ? error.message : 'Error al crear alerta'),
  });

  function handleOpenChart(hit: ScanHitDto) {
    openHitInTrading(
      navigate,
      { openChartTab, updateChartTimeframe, focusInstrumentFromList },
      hit,
      { timeframe: result.timeframe, listId: scanConfig.listId },
    );
  }

  function persistLayout(next: ScanResultsColumnLayoutItem[]) {
    setColumnLayout(next);
  }

  function renderCell(columnId: ScanResultsColumnId, hit: ScanHitDto) {
    switch (columnId) {
      case 'symbol':
        return (
          <button
            type="button"
            className="truncate font-medium hover:text-primary text-left"
            title="Abrir en Trading"
            onClick={() => handleOpenChart(hit)}
          >
            {hit.symbol}
          </button>
        );
      case 'name':
        return (
          <div className="min-w-0 truncate text-xs text-muted-foreground">
            {hit.name}
            {full && (
              <>
                {' · '}
                <Link to={`/instruments/${hit.instrumentId}`} className="hover:text-primary">
                  ficha
                </Link>
              </>
            )}
          </div>
        );
      case 'signal':
        return (
          <span
            className={cn(
              'rounded px-1.5 py-0.5 text-xs',
              hit.signal.kind === 'entry_long' && 'bg-emerald-500/15 text-emerald-600',
              hit.signal.kind === 'exit' && 'bg-amber-500/15 text-amber-600',
            )}
          >
            {SIGNAL_KIND_LABELS[hit.signal.kind]}
          </span>
        );
      case 'rating':
        return <RatingCell hit={hit} />;
      case 'quality':
        return <QualityCell hit={hit} />;
      case 'dataQuality':
        return <DataQualityCell hit={hit} />;
      case 'globalScore':
        return <GlobalScoreCell hit={hit} />;
      case 'trend':
        return <SubScoreCell value={hit.ratingBreakdown?.trend} />;
      case 'momentum':
        return <SubScoreCell value={hit.ratingBreakdown?.momentum} />;
      case 'volatility':
        return <SubScoreCell value={hit.ratingBreakdown?.volatility} />;
      case 'meanReversion':
        return <SubScoreCell value={hit.ratingBreakdown?.meanReversion} />;
      case 'pattern':
        return <SubScoreCell value={hit.ratingBreakdown?.pattern} />;
      case 'price':
        return <span className="tabular-nums">{formatPrice(hit.signal.price)}</span>;
      case 'bar':
        return <span className="text-xs text-muted-foreground">{hit.signal.timestamp}</span>;
      case 'actions':
        return full ? (
          <div className="flex justify-end gap-1">
            <Button type="button" size="sm" variant="outline" onClick={() => handleOpenChart(hit)}>
              <LineChart className="mr-1 h-3.5 w-3.5" />
              Gráfico
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={subscribeMutation.isPending}
              onClick={() => subscribeMutation.mutate(hit)}
            >
              <Bell className="mr-1 h-3.5 w-3.5" />
              Alerta
            </Button>
            <Link
              to={`/backtests?tab=run&instrumentId=${hit.instrumentId}`}
              className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'px-2')}
              title="Backtest"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
        ) : null;
      default:
        return null;
    }
  }

  return (
    <div className={cn('overflow-x-auto', full && 'rounded-lg border border-border')}>
      <div className="sticky top-0 z-10 border-b border-border bg-card px-2 py-1">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] text-muted-foreground">
            Clic en cabecera para ordenar · arrastra para mover · borde derecho para ancho
          </p>
          <div className="relative" ref={menuRef}>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
            {menuOpen && (
              <OpaqueMenuPanel className="min-w-[200px] p-2">
                <OpaqueMenuLabel>Columnas visibles</OpaqueMenuLabel>
                {layout
                  .filter((column) => column.id !== 'actions')
                  .map((column) => (
                    <label
                      key={column.id}
                      className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-accent"
                    >
                      <input
                        type="checkbox"
                        checked={column.visible}
                        onChange={() => persistLayout(toggleScanResultsColumn(layout, column.id))}
                      />
                      <span className="flex-1">{SCAN_RESULTS_COLUMN_LABELS[column.id]}</span>
                      <button
                        type="button"
                        title={
                          favoriteIds.has(column.id)
                            ? 'Quitar de favoritas'
                            : 'Marcar como favorita'
                        }
                        className={cn(
                          'rounded p-0.5',
                          favoriteIds.has(column.id)
                            ? 'text-amber-500'
                            : 'text-muted-foreground/50 hover:text-muted-foreground',
                        )}
                        onClick={(event) => {
                          event.preventDefault();
                          setFavoriteColumnIds(
                            toggleScanResultsFavoriteColumn(favoriteColumnIds, column.id),
                          );
                        }}
                      >
                        <Star
                          className="h-3 w-3"
                          fill={favoriteIds.has(column.id) ? 'currentColor' : 'none'}
                        />
                      </button>
                    </label>
                  ))}
                <p className="mt-2 border-t border-border px-2 pt-2 text-[10px] text-muted-foreground">
                  ★ Favoritas = columnas clave en vista compacta
                </p>
              </OpaqueMenuPanel>
            )}
          </div>
        </div>
        <div className="grid min-w-0 items-center" style={{ gridTemplateColumns: gridTemplate }}>
          {visibleColumns.map((column) => {
            const align = scanResultsColumnAlign(column.id);
            const isSorted = sortState?.columnId === column.id;
            const sortable = column.id !== 'actions';
            return (
              <div
                key={column.id}
                draggable={column.id !== 'actions'}
                onDragStart={() => setDragId(column.id)}
                onDragEnd={() => {
                  setDragId(null);
                  setDropTargetId(null);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  if (dragId && dragId !== column.id) setDropTargetId(column.id);
                }}
                onDragLeave={() => {
                  if (dropTargetId === column.id) setDropTargetId(null);
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  if (dragId && dragId !== column.id) {
                    persistLayout(reorderScanResultsColumns(layout, dragId, column.id));
                  }
                  setDragId(null);
                  setDropTargetId(null);
                }}
                className={cn(
                  'relative min-w-0 py-1',
                  dragId === column.id && 'opacity-40',
                  dropTargetId === column.id && 'bg-primary/15 ring-1 ring-primary/40',
                )}
              >
                <div
                  className={cn(
                    'flex min-w-0 items-center gap-0.5 px-2 text-[10px] font-medium text-muted-foreground',
                    align === 'left' && 'justify-start',
                    align === 'center' && 'justify-center',
                    align === 'right' && 'justify-end',
                    sortable && 'cursor-pointer select-none hover:text-foreground',
                  )}
                  onClick={() => {
                    if (!sortable) return;
                    setSortState(cycleScanResultsSort(sortState, column.id));
                  }}
                >
                  {column.id !== 'actions' && (
                    <GripVertical className="h-3 w-3 shrink-0 cursor-grab opacity-40" />
                  )}
                  <span className="truncate">{SCAN_RESULTS_COLUMN_LABELS[column.id]}</span>
                  {sortable && (
                    <span className="shrink-0">
                      {!isSorted && <ArrowUpDown className="h-3 w-3 opacity-50" />}
                      {isSorted && sortState?.direction === 'asc' && <ArrowUp className="h-3 w-3" />}
                      {isSorted && sortState?.direction === 'desc' && (
                        <ArrowDown className="h-3 w-3" />
                      )}
                    </span>
                  )}
                </div>
                {column.id !== 'actions' && (
                  <ColumnResizeHandle
                    columnId={column.id}
                    width={column.width}
                    onResize={(columnId, width) =>
                      persistLayout(resizeScanResultsColumn(layout, columnId, width))
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="divide-y divide-border/60 text-sm">
        {sortedHits.map((hit) => (
          <div
            key={`${hit.instrumentId}-${hit.signal.id}`}
            className="grid min-w-0 items-center py-1.5 hover:bg-muted/20"
            style={{ gridTemplateColumns: gridTemplate }}
          >
            {visibleColumns.map((column) => {
              const align = scanResultsColumnAlign(column.id);
              return (
                <div
                  key={column.id}
                  className={cn(
                    'min-w-0 px-2',
                    align === 'left' && 'text-left',
                    align === 'center' && 'text-center',
                    align === 'right' && 'text-right tabular-nums',
                  )}
                >
                  {renderCell(column.id, hit)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
