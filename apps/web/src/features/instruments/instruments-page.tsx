/**
 * Hub Instrumentos (I0–I5) — catálogo + listas + cartera + Estudio + IO + Seguimiento.
 * Tabla configurable: anchos · orden · visibilidad · favoritas (persistente).
 *
 * @see docs/engineering/instruments-hub-2026-07-31.md
 * @see docs/engineering/instruments-hub-narrative-2026-08-04.md
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CandlestickChart,
  FlaskConical,
  GripVertical,
  Info,
  Loader2,
  MoreHorizontal,
  Radar,
  Search,
  Star,
} from 'lucide-react';
import type { InstrumentWithMetaDto, PositionDto } from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { getApiBaseUrl } from '@/stores/auth-store';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import {
  InstrumentStrategyTopBadge,
  instrumentTopBacktestsHref,
} from '@/features/backtests/instrument-strategy-top-panel';
import { openHitInTrading } from '@/features/screeners/open-hit-in-trading';
import { filterAndSortInstrumentsHub } from '@/features/instruments/instruments-hub-model';
import {
  InstrumentsHubFilterBar,
  toggleFavoriteBuiltinFilter,
  toggleFavoriteListId,
} from '@/features/instruments/instruments-hub-filter-bar';
import { computeIndiceOperativo } from '@/features/trading/operativa-index';
import { useEstudioMembershipStore } from '@/stores/estudio-membership-store';
import {
  pickListChips,
  type HubListMembership,
} from '@/features/instruments/instruments-hub-enrichment';
import { useInstrumentsHubEnrichment } from '@/features/instruments/use-instruments-hub-enrichment';
import { useInstrumentsHubScores } from '@/features/instruments/use-instruments-hub-scores';
import { useInstrumentsHubTrackers } from '@/features/instruments/use-instruments-hub-trackers';
import { useActivateInstrumentTracking } from '@/features/instruments/use-activate-instrument-tracking';
import {
  hubTrackerChipLabel,
  hubTrackerChipTitle,
  pickTrackerChips,
  type HubTrackerChip,
} from '@/features/instruments/instruments-hub-trackers';
import {
  INSTRUMENTS_HUB_COLUMN_LABELS,
  buildInstrumentsHubGridTemplate,
  cycleInstrumentsHubColumnSort,
  formatInstrumentLastBarLabel,
  instrumentsHubColumnAlign,
  instrumentsHubGridMinWidth,
  instrumentsHubSortKeyFromColumn,
  isSortableInstrumentsHubColumn,
  normalizeInstrumentsHubColumnLayout,
  reorderInstrumentsHubColumns,
  resizeInstrumentsHubColumn,
  fitInstrumentsHubColumnsToContent,
  toggleInstrumentsHubColumn,
  toggleInstrumentsHubFavoriteColumn,
  visibleInstrumentsHubColumns,
  type InstrumentsHubColumnId,
  type InstrumentsHubColumnLayoutItem,
} from '@/features/instruments/instruments-hub-column-layout';
import {
  InstrumentsHubDetailCollapsedRail,
  InstrumentsHubDetailPanel,
} from '@/features/instruments/instruments-hub-detail-panel';
import { InstrumentsHubSplitLayout } from '@/features/instruments/instruments-hub-split-layout';
import { useMediaQuery } from '@/lib/use-media-query';
import { screenersHrefAfterTrackerCreate } from '@/features/backtests/promote-finalist-to-tracker';
import { PAPER_PATH_RADAR } from '@/features/settings/paper-paths-copy';
import { useInstrumentsHubPreferencesStore } from '@/stores/instruments-hub-preferences-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { IconButton } from '@/components/ui/icon-button';
import { OpaqueMenuLabel, OpaqueMenuPanel } from '@/components/ui/opaque-menu-panel';
import { cn } from '@/lib/utils';
import { useTradingUiStore } from '@/stores/trading-ui-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

function SyncBadge({ barCount, status }: { barCount: number; status: string | null }) {
  if (barCount === 0) {
    return (
      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
        Sin datos
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="rounded bg-destructive/15 px-1.5 py-0.5 text-[10px] text-destructive">
        Sync fallida
      </span>
    );
  }
  return (
    <span className="rounded bg-success/15 px-1.5 py-0.5 text-[10px] tabular-nums text-success">
      {barCount.toLocaleString()} barras
    </span>
  );
}

function ColumnResizeHandle({
  columnId,
  width,
  onResize,
}: {
  columnId: InstrumentsHubColumnId;
  width: number;
  onResize: (columnId: InstrumentsHubColumnId, width: number) => void;
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
      aria-label={`Redimensionar ${INSTRUMENTS_HUB_COLUMN_LABELS[columnId]}`}
      className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize touch-none opacity-0 hover:bg-primary/30 hover:opacity-100"
      onMouseDown={onMouseDown}
    />
  );
}

function ListsCell({
  memberships,
  instrument,
  loading,
}: {
  memberships: HubListMembership[];
  instrument: InstrumentWithMetaDto;
  loading: boolean;
}) {
  const navigate = useNavigate();
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const updateChartTimeframe = useWorkspaceStore((s) => s.updateChartTimeframe);
  const focusInstrumentFromList = useWorkspaceStore((s) => s.focusInstrumentFromList);

  if (loading) {
    return <span className="text-[10px] text-muted-foreground">…</span>;
  }
  if (memberships.length === 0) {
    return <span className="text-[10px] text-muted-foreground">—</span>;
  }

  const { visible, overflow } = pickListChips(memberships, 2);
  const title = memberships.map((m) => m.listName).join(', ');

  return (
    <div className="flex max-w-full flex-wrap items-center gap-0.5" title={title}>
      <span className="mr-0.5 tabular-nums text-[10px] text-muted-foreground">
        {memberships.length}
      </span>
      {visible.map((m) => (
        <button
          key={m.listId}
          type="button"
          className={cn(
            'max-w-[4.5rem] truncate rounded px-1 py-0.5 text-[9px] hover:ring-1 hover:ring-border',
            m.source === 'custom'
              ? 'bg-primary/10 text-foreground'
              : 'bg-muted text-muted-foreground',
          )}
          title={`Abrir ${m.listName} en Trading`}
          onClick={() =>
            openHitInTrading(
              navigate,
              { openChartTab, updateChartTimeframe, focusInstrumentFromList },
              { instrumentId: instrument.id, symbol: instrument.symbol },
              { listId: m.listId },
            )
          }
        >
          {m.listName}
        </button>
      ))}
      {overflow > 0 ? (
        <span className="text-[9px] text-muted-foreground">+{overflow}</span>
      ) : null}
    </div>
  );
}

function ScoreCell({
  value,
  loading,
  title,
  warn,
}: {
  value: number | null | undefined;
  loading: boolean;
  title?: string;
  warn?: boolean;
}) {
  if (loading) {
    return <span className="text-[10px] text-muted-foreground">…</span>;
  }
  if (value == null || !Number.isFinite(value)) {
    return <span className="text-[10px] text-muted-foreground">—</span>;
  }
  const tone =
    value >= 60 ? 'text-success' : value <= 40 ? 'text-destructive' : 'text-foreground';
  return (
    <span
      className={cn('tabular-nums font-medium', tone, warn && 'opacity-70')}
      title={title}
    >
      {Math.round(value)}
      {warn ? <span className="ml-0.5 text-[9px] font-normal text-amber-700">·</span> : null}
    </span>
  );
}

function SeguimientoCell({
  chips,
  instrument,
  loading,
  onActivate,
  activatePending,
}: {
  chips: HubTrackerChip[];
  instrument: InstrumentWithMetaDto;
  loading: boolean;
  onActivate: () => void;
  activatePending: boolean;
}) {
  if (loading) {
    return <span className="text-[10px] text-muted-foreground">…</span>;
  }

  if (chips.length === 0) {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-6 gap-0.5 px-1.5 text-[10px]"
        disabled={activatePending}
        title={PAPER_PATH_RADAR.finalistsHint}
        onClick={onActivate}
      >
        {activatePending ? (
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        ) : (
          <Radar className="h-3 w-3" aria-hidden />
        )}
        Activar
      </Button>
    );
  }

  const { visible, overflow } = pickTrackerChips(chips, 3);
  return (
    <div className="flex max-w-full flex-wrap items-center gap-0.5">
      <span className="mr-0.5 tabular-nums text-[10px] text-muted-foreground">
        {chips.length}
      </span>
      {visible.map((chip) => (
        <Link
          key={chip.trackerId}
          to={screenersHrefAfterTrackerCreate(chip.trackerId)}
          title={hubTrackerChipTitle(chip)}
          className={cn(
            'max-w-[5rem] truncate rounded px-1 py-0.5 text-[9px] hover:ring-1 hover:ring-border',
            chip.enabled
              ? 'bg-emerald-500/15 text-emerald-900 dark:text-emerald-200'
              : 'bg-muted text-muted-foreground line-through decoration-muted-foreground/50',
          )}
        >
          {hubTrackerChipLabel(chip)}
          <span className="ml-0.5 opacity-70">{chip.modeShort}</span>
        </Link>
      ))}
      {overflow > 0 ? (
        <Link
          to={screenersHrefAfterTrackerCreate(visible[0]?.trackerId)}
          className="text-[9px] text-muted-foreground hover:underline"
          title={`${overflow} más en Radar`}
        >
          +{overflow}
        </Link>
      ) : null}
      <span className="sr-only">
        {instrument.symbol} · {chips.length} seguimiento(s)
      </span>
    </div>
  );
}

function PortfolioCell({
  position,
  loading,
}: {
  position: PositionDto | null;
  loading: boolean;
}) {
  if (loading) {
    return <span className="text-[10px] text-muted-foreground">…</span>;
  }
  if (!position) {
    return <span className="text-[10px] text-muted-foreground">—</span>;
  }
  const pnl = position.unrealizedPnl;
  const pnlPct = position.unrealizedPnlPct;
  return (
    <div
      className="text-right leading-tight"
      title={`Qty ${position.quantity} · medio ${formatPrice(position.avgCost)}`}
    >
      <p className="tabular-nums text-[10px] text-foreground">
        {position.quantity.toLocaleString()} ud
      </p>
      <p
        className={cn(
          'tabular-nums text-[10px]',
          pnl == null
            ? 'text-muted-foreground'
            : pnl >= 0
              ? 'text-success'
              : 'text-destructive',
        )}
      >
        {pnl != null ? formatPrice(pnl) : '—'}
        {pnlPct != null ? (
          <span className="ml-0.5 opacity-80">({formatPct(pnlPct)})</span>
        ) : null}
      </p>
    </div>
  );
}

function InstrumentRowActions({ instrument }: { instrument: InstrumentWithMetaDto }) {
  const navigate = useNavigate();
  const openInfoDialog = useTradingUiStore((s) => s.openInfoDialog);
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const updateChartTimeframe = useWorkspaceStore((s) => s.updateChartTimeframe);
  const focusInstrumentFromList = useWorkspaceStore((s) => s.focusInstrumentFromList);

  return (
    <div className="flex items-center justify-center gap-0.5">
      <IconButton
        icon={CandlestickChart}
        title="Abrir en Trading"
        onClick={() =>
          openHitInTrading(
            navigate,
            { openChartTab, updateChartTimeframe, focusInstrumentFromList },
            { instrumentId: instrument.id, symbol: instrument.symbol },
          )
        }
      />
      <IconButton
        icon={Info}
        title="Información del valor"
        onClick={() => openInfoDialog(instrument)}
      />
      <Link
        to={instrumentTopBacktestsHref(instrument.id)}
        title="Backtesting · Finalistas"
        className="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <FlaskConical className="h-3.5 w-3.5" />
      </Link>
      <Link
        to={`/instruments/${instrument.id}`}
        title="Ficha del instrumento"
        className="rounded px-1.5 py-0.5 text-[10px] font-medium text-primary hover:underline"
      >
        Ficha
      </Link>
    </div>
  );
}

export function InstrumentsPage() {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dragId, setDragId] = useState<InstrumentsHubColumnId | null>(null);
  const [dropTargetId, setDropTargetId] = useState<InstrumentsHubColumnId | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const isWide = useMediaQuery('(min-width: 1024px)');

  const storedLayout = useInstrumentsHubPreferencesStore((s) => s.columnLayout);
  const sortState = useInstrumentsHubPreferencesStore((s) => s.sort);
  const favoriteColumnIds = useInstrumentsHubPreferencesStore((s) => s.favoriteColumnIds);
  const autoFitColumns = useInstrumentsHubPreferencesStore((s) => s.autoFitColumns);
  const scopeFilter = useInstrumentsHubPreferencesStore((s) => s.scopeFilter);
  const scopeListId = useInstrumentsHubPreferencesStore((s) => s.scopeListId);
  const favoriteBuiltinFilters = useInstrumentsHubPreferencesStore(
    (s) => s.favoriteBuiltinFilters,
  );
  const favoriteListIds = useInstrumentsHubPreferencesStore((s) => s.favoriteListIds);
  const listWidthPct = useInstrumentsHubPreferencesStore((s) => s.wideSplit.listWidthPct);
  const stackHeightPct = useInstrumentsHubPreferencesStore((s) => s.stackSplit.stackHeightPct);
  const wideDetailOpen = useInstrumentsHubPreferencesStore((s) => s.wideSplit.detailPanelOpen);
  const stackDetailOpen = useInstrumentsHubPreferencesStore((s) => s.stackSplit.detailPanelOpen);
  const detailSectionsOpen = useInstrumentsHubPreferencesStore((s) => s.detailSectionsOpen);
  const setColumnLayout = useInstrumentsHubPreferencesStore((s) => s.setColumnLayout);
  const setSort = useInstrumentsHubPreferencesStore((s) => s.setSort);
  const setFavoriteColumnIds = useInstrumentsHubPreferencesStore((s) => s.setFavoriteColumnIds);
  const setAutoFitColumns = useInstrumentsHubPreferencesStore((s) => s.setAutoFitColumns);
  const setScopeFilter = useInstrumentsHubPreferencesStore((s) => s.setScopeFilter);
  const setScopeListId = useInstrumentsHubPreferencesStore((s) => s.setScopeListId);
  const setFavoriteBuiltinFilters = useInstrumentsHubPreferencesStore(
    (s) => s.setFavoriteBuiltinFilters,
  );
  const setFavoriteListIds = useInstrumentsHubPreferencesStore((s) => s.setFavoriteListIds);
  const setListWidthPct = useInstrumentsHubPreferencesStore((s) => s.setListWidthPct);
  const setStackHeightPct = useInstrumentsHubPreferencesStore((s) => s.setStackHeightPct);
  const setDetailPanelOpen = useInstrumentsHubPreferencesStore((s) => s.setDetailPanelOpen);
  const toggleDetailSection = useInstrumentsHubPreferencesStore((s) => s.toggleDetailSection);
  const layoutMode = isWide ? 'wide' : 'stack';
  const detailPanelOpen = isWide ? wideDetailOpen : stackDetailOpen;
  const favoriteIds = useMemo(() => new Set(favoriteColumnIds), [favoriteColumnIds]);

  const layout = useMemo(
    () => normalizeInstrumentsHubColumnLayout(storedLayout),
    [storedLayout],
  );
  const visibleColumns = visibleInstrumentsHubColumns(layout);
  const gridTemplate = buildInstrumentsHubGridTemplate(visibleColumns);
  const gridMinWidth = instrumentsHubGridMinWidth(visibleColumns);

  const instrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: api.getInstruments,
  });

  const instruments = instrumentsQuery.data?.data ?? [];

  const {
    membershipsByInstrument,
    positionsByInstrument,
    apiLists,
    listsLoading,
    portfolioLoading,
  } = useInstrumentsHubEnrichment();

  const estudioEntries = useEstudioMembershipStore((s) => s.members);
  const estudioIds = useMemo(
    () => new Set(estudioEntries.map((e) => e.instrumentId)),
    [estudioEntries],
  );

  const instrumentIds = useMemo(() => instruments.map((i) => i.id), [instruments]);
  const { faByInstrument, taByInstrument, scoresLoading } =
    useInstrumentsHubScores(instrumentIds);

  const { trackersByInstrument, trackersLoading } =
    useInstrumentsHubTrackers(membershipsByInstrument);

  const activateTracking = useActivateInstrumentTracking();

  const ioByInstrument = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const id of instrumentIds) {
      const fa = faByInstrument.get(id);
      const ta = taByInstrument.get(id);
      map.set(
        id,
        computeIndiceOperativo({
          compositeDisplay100: ta?.compositeDisplay100,
          distress: fa?.distress,
        }),
      );
    }
    return map;
  }, [instrumentIds, faByInstrument, taByInstrument]);

  const enrichment = useMemo(
    () => ({
      membershipsByInstrument,
      positionsByInstrument,
      faByInstrument,
      taByInstrument,
      ioByInstrument,
      trackersByInstrument,
    }),
    [
      membershipsByInstrument,
      positionsByInstrument,
      faByInstrument,
      taByInstrument,
      ioByInstrument,
      trackersByInstrument,
    ],
  );

  const sortKey =
    (sortState && instrumentsHubSortKeyFromColumn(sortState.columnId)) || 'symbol';
  const sortDir = sortState?.direction ?? 'asc';

  const rows = useMemo(
    () =>
      filterAndSortInstrumentsHub(instruments, {
        query,
        sortKey,
        sortDir,
        scopeFilter,
        listId: scopeListId,
        estudioIds,
        enrichment,
      }),
    [
      instruments,
      query,
      sortKey,
      sortDir,
      scopeFilter,
      scopeListId,
      estudioIds,
      enrichment,
    ],
  );

  const selectedInstrument = useMemo(
    () => rows.find((r) => r.id === selectedId) ?? instruments.find((r) => r.id === selectedId) ?? null,
    [rows, instruments, selectedId],
  );

  useEffect(() => {
    if (selectedId && !instruments.some((i) => i.id === selectedId)) {
      setSelectedId(null);
    }
  }, [instruments, selectedId]);

  const contentSamples = useMemo(() => {
    const samples: Partial<Record<InstrumentsHubColumnId, string[]>> = {
      symbol: [INSTRUMENTS_HUB_COLUMN_LABELS.symbol],
      price: [INSTRUMENTS_HUB_COLUMN_LABELS.price],
      changePct: [INSTRUMENTS_HUB_COLUMN_LABELS.changePct],
      lists: [INSTRUMENTS_HUB_COLUMN_LABELS.lists],
      portfolio: [INSTRUMENTS_HUB_COLUMN_LABELS.portfolio],
      scoreFa: [INSTRUMENTS_HUB_COLUMN_LABELS.scoreFa],
      scoreTa: [INSTRUMENTS_HUB_COLUMN_LABELS.scoreTa],
      scoreIo: [INSTRUMENTS_HUB_COLUMN_LABELS.scoreIo],
      tracking: [INSTRUMENTS_HUB_COLUMN_LABELS.tracking],
      lastBar: [INSTRUMENTS_HUB_COLUMN_LABELS.lastBar],
      data: [INSTRUMENTS_HUB_COLUMN_LABELS.data],
      coach: [INSTRUMENTS_HUB_COLUMN_LABELS.coach, 'TOP 3 · active'],
      actions: [INSTRUMENTS_HUB_COLUMN_LABELS.actions, 'Trading (i) Ficha'],
    };
    const limit = Math.min(rows.length, 80);
    for (let i = 0; i < limit; i++) {
      const instrument = rows[i]!;
      samples.symbol!.push(`${instrument.symbol} ${instrument.name}`);
      if (instrument.meta.lastClose != null) {
        samples.price!.push(formatPrice(instrument.meta.lastClose));
      }
      if (instrument.meta.changePct != null) {
        samples.changePct!.push(formatPct(instrument.meta.changePct));
      }
      const memberships = membershipsByInstrument.get(instrument.id) ?? [];
      if (memberships.length > 0) {
        const { visible, overflow } = pickListChips(memberships, 2);
        samples.lists!.push(
          `${memberships.length} ${visible.map((m) => m.listName).join(' ')}${overflow ? ` +${overflow}` : ''}`,
        );
      }
      const position = positionsByInstrument.get(instrument.id);
      if (position) {
        samples.portfolio!.push(
          `${position.quantity} ud ${position.unrealizedPnl != null ? formatPrice(position.unrealizedPnl) : ''}`,
        );
      }
      const fa = faByInstrument.get(instrument.id)?.scoreDisplay100;
      if (fa != null) samples.scoreFa!.push(String(Math.round(fa)));
      const ta = taByInstrument.get(instrument.id)?.technicalDisplay100;
      if (ta != null) samples.scoreTa!.push(String(Math.round(ta)));
      const io = ioByInstrument.get(instrument.id);
      if (io != null) samples.scoreIo!.push(String(Math.round(io)));
      const trackers = trackersByInstrument.get(instrument.id) ?? [];
      if (trackers.length > 0) {
        const { visible, overflow } = pickTrackerChips(trackers, 3);
        samples.tracking!.push(
          `${trackers.length} ${visible.map((c) => `${hubTrackerChipLabel(c)} ${c.modeShort}`).join(' ')}${overflow ? ` +${overflow}` : ''}`,
        );
      } else {
        samples.tracking!.push('Activar');
      }
      samples.lastBar!.push(
        formatInstrumentLastBarLabel({
          lastBarDate: instrument.meta.lastBarDate,
          lastSyncAt: instrument.meta.lastSync?.syncedAt,
        }).primary,
      );
      samples.data!.push(
        instrument.meta.barCount === 0
          ? 'Sin datos'
          : `${instrument.meta.barCount.toLocaleString()} barras`,
      );
    }
    return samples;
  }, [
    rows,
    membershipsByInstrument,
    positionsByInstrument,
    faByInstrument,
    taByInstrument,
    ioByInstrument,
    trackersByInstrument,
  ]);

  useEffect(() => {
    if (!autoFitColumns || rows.length === 0) return;
    const base = normalizeInstrumentsHubColumnLayout(storedLayout);
    const next = fitInstrumentsHubColumnsToContent(base, contentSamples);
    const changed = next.some((col, i) => col.width !== base[i]?.width);
    if (changed) setColumnLayout(next);
  }, [autoFitColumns, contentSamples, storedLayout, rows.length, setColumnLayout]);

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

  const errorMessage =
    instrumentsQuery.error instanceof ApiError
      ? instrumentsQuery.error.message
      : instrumentsQuery.error instanceof Error
        ? instrumentsQuery.error.message
        : 'Error desconocido';
  const apiUnreachable =
    instrumentsQuery.error instanceof TypeError ||
    (instrumentsQuery.error instanceof Error &&
      /fetch|network|failed|conectar|timeout/i.test(instrumentsQuery.error.message));

  function persistLayout(next: InstrumentsHubColumnLayoutItem[]) {
    setColumnLayout(next);
  }

  function renderCell(columnId: InstrumentsHubColumnId, instrument: InstrumentWithMetaDto) {
    const memberships = membershipsByInstrument.get(instrument.id) ?? [];
    const position = positionsByInstrument.get(instrument.id) ?? null;
    const fa = faByInstrument.get(instrument.id);
    const ta = taByInstrument.get(instrument.id);
    const io = ioByInstrument.get(instrument.id);
    const trackers = trackersByInstrument.get(instrument.id) ?? [];

    switch (columnId) {
      case 'symbol':
        return (
          <button
            type="button"
            className="group block w-full min-w-0 text-left"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedId(instrument.id);
            }}
          >
            <p className="truncate font-medium text-foreground group-hover:underline">
              {instrument.symbol}
            </p>
            <p className="truncate text-[10px] text-muted-foreground">
              {instrument.name}
              {instrument.sector ? (
                <span className="ml-1 opacity-70">· {instrument.sector}</span>
              ) : null}
            </p>
          </button>
        );
      case 'price':
        return (
          <span className="tabular-nums">
            {instrument.meta.lastClose != null
              ? formatPrice(instrument.meta.lastClose)
              : '—'}
          </span>
        );
      case 'changePct':
        return (
          <span
            className={cn(
              'tabular-nums',
              instrument.meta.changePct == null
                ? 'text-muted-foreground'
                : instrument.meta.changePct >= 0
                  ? 'text-success'
                  : 'text-destructive',
            )}
          >
            {instrument.meta.changePct != null
              ? formatPct(instrument.meta.changePct)
              : '—'}
          </span>
        );
      case 'lists':
        return (
          <ListsCell
            memberships={memberships}
            instrument={instrument}
            loading={listsLoading}
          />
        );
      case 'portfolio':
        return <PortfolioCell position={position} loading={portfolioLoading} />;
      case 'scoreIo':
        return (
          <ScoreCell
            value={io}
            loading={scoresLoading}
            warn={fa?.distress}
            title={
              io != null
                ? `Recomendación (IO)${fa?.distress ? ' · FA distress ≤40' : ''} · mismo criterio que Operativa`
                : 'Recomendación (Índice Operativo)'
            }
          />
        );
      case 'scoreFa':
        return (
          <ScoreCell
            value={fa?.scoreDisplay100}
            loading={scoresLoading}
            warn={fa?.isStale || fa?.distress}
            title={
              fa
                ? `Score_FUND${fa.isStale ? ' · stale' : ''}${fa.distress ? ' · distress' : ''}`
                : 'Score_FUND'
            }
          />
        );
      case 'scoreTa':
        return (
          <ScoreCell
            value={ta?.technicalDisplay100}
            loading={scoresLoading}
            title={
              ta?.compositeDisplay100 != null
                ? `TA · Composite ${Math.round(ta.compositeDisplay100)}`
                : 'Pierna técnica (Composite)'
            }
          />
        );
      case 'tracking':
        return (
          <SeguimientoCell
            chips={trackers}
            instrument={instrument}
            loading={trackersLoading}
            activatePending={
              activateTracking.isPending &&
              activateTracking.variables?.instrumentId === instrument.id
            }
            onActivate={() =>
              activateTracking.mutate({
                instrumentId: instrument.id,
                symbol: instrument.symbol,
              })
            }
          />
        );
      case 'lastBar': {
        const label = formatInstrumentLastBarLabel({
          lastBarDate: instrument.meta.lastBarDate,
          lastSyncAt: instrument.meta.lastSync?.syncedAt,
        });
        return (
          <div className="min-w-0 text-right leading-tight" title={label.secondary}>
            <p className="truncate tabular-nums text-[10px] text-foreground">{label.primary}</p>
          </div>
        );
      }
      case 'data':
        return (
          <SyncBadge
            barCount={instrument.meta.barCount}
            status={instrument.meta.lastSync?.status ?? null}
          />
        );
      case 'coach':
        return <InstrumentStrategyTopBadge instrumentId={instrument.id} />;
      case 'actions':
        return <InstrumentRowActions instrument={instrument} />;
      default:
        return null;
    }
  }

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-[480px] flex-col gap-3 overflow-hidden p-4 md:p-6">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Instrumentos</h2>
          <p className="text-xs text-muted-foreground">
            Lista + detalle colapsable · secciones apiladas · layout persistente por navegador
          </p>
        </div>
        {instrumentsQuery.isSuccess ? (
          <p className="text-[11px] tabular-nums text-muted-foreground">
            {rows.length === instruments.length
              ? `${instruments.length} en catálogo`
              : `${rows.length} / ${instruments.length}`}
          </p>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <div className="relative min-w-[12rem] max-w-sm flex-1">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar símbolo, nombre, ISIN, lista…"
            className="w-full rounded-md border border-border bg-background py-1.5 pl-7 pr-2 text-xs outline-none ring-primary focus:ring-1"
            autoComplete="off"
            aria-label="Buscar instrumentos"
          />
        </div>
        <InstrumentsHubFilterBar
          scopeFilter={scopeFilter}
          scopeListId={scopeListId}
          favoriteBuiltinFilters={favoriteBuiltinFilters}
          favoriteListIds={favoriteListIds}
          apiLists={apiLists}
          estudioCount={estudioIds.size}
          onSelectBuiltin={(id) => {
            setScopeFilter(id);
            setScopeListId(null);
            if (id === 'estudio') {
              setSort({ columnId: 'scoreIo', direction: 'desc' });
            }
          }}
          onSelectList={(listId) => {
            setScopeListId(listId);
            setScopeFilter('list');
          }}
          onToggleBuiltinFavorite={(id) => {
            const next = toggleFavoriteBuiltinFilter(favoriteBuiltinFilters, id);
            setFavoriteBuiltinFilters(
              next.length > 0 || favoriteListIds.length > 0
                ? next
                : favoriteBuiltinFilters,
            );
            if (
              scopeFilter === id &&
              !next.includes(id) &&
              next.includes('all')
            ) {
              setScopeFilter('all');
              setScopeListId(null);
            }
          }}
          onToggleListFavorite={(listId) => {
            const next = toggleFavoriteListId(favoriteListIds, listId);
            setFavoriteListIds(next);
            if (scopeFilter === 'list' && scopeListId === listId && !next.includes(listId)) {
              setScopeFilter('all');
              setScopeListId(null);
            }
          }}
        />
      </div>

      {instrumentsQuery.isLoading && (
        <p className="text-sm text-muted-foreground">Cargando catálogo…</p>
      )}

      {instrumentsQuery.isError && (
        <Card>
          <CardContent className="space-y-2 pt-6 text-sm text-destructive">
            {apiUnreachable ? (
              <>
                <p>No se pudo conectar con la API en {getApiBaseUrl()}.</p>
                <p className="text-muted-foreground">
                  Arranca el stack:{' '}
                  <code className="text-xs text-foreground">pnpm dev</code>
                </p>
              </>
            ) : (
              <>
                <p>No se pudo cargar el catálogo: {errorMessage}</p>
                <p className="text-muted-foreground">
                  Si la BD no está lista:{' '}
                  <code className="text-xs text-foreground">node scripts/db-ensure.mjs</code>
                </p>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {instrumentsQuery.isSuccess && rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {instruments.length === 0
            ? 'Catálogo vacío. Importa valores desde Trading → Listas.'
            : scopeFilter === 'portfolio'
              ? 'Ninguna posición abierta en la cuenta activa.'
              : scopeFilter === 'estudio'
                ? 'Estudio vacío. Añade valores desde Trading (abrir gráfico o Pasar a Estudio).'
                : scopeFilter === 'list'
                  ? 'Ningún instrumento en la lista seleccionada.'
                  : 'Ningún instrumento coincide con la búsqueda.'}
        </p>
      ) : null}

      {instrumentsQuery.isSuccess && rows.length > 0 ? (
        <InstrumentsHubSplitLayout
          className="min-h-0 flex-1"
          isWide={isWide}
          showDetail={Boolean(selectedInstrument)}
          detailCollapsed={Boolean(selectedInstrument) && !detailPanelOpen}
          listWidthPct={listWidthPct}
          stackHeightPct={stackHeightPct}
          onListWidthPctChange={setListWidthPct}
          onStackHeightPctChange={setStackHeightPct}
          list={
            <div className="flex h-full min-h-0 flex-col">
              <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border/60 bg-muted/40 px-2 py-1">
                <p className="text-[10px] text-muted-foreground">
                  Clic fila = abrir detalle · arrastra el divisor lista/detalle · anchos y
                  secciones se recuerdan en este navegador
                </p>
                <div className="flex items-center gap-2">
                  <label
                    className="flex cursor-pointer items-center gap-1.5 text-[10px] text-muted-foreground"
                    title="Ancho según cabeceras y contenido de las filas"
                  >
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={autoFitColumns}
                      onChange={(e) => {
                        const on = e.target.checked;
                        setAutoFitColumns(on);
                        if (on) {
                          setColumnLayout(
                            fitInstrumentsHubColumnsToContent(layout, contentSamples),
                          );
                        }
                      }}
                    />
                    Ajustar al contenido
                  </label>
                  <div className="relative" ref={menuRef}>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2"
                      title="Configurar columnas"
                      onClick={() => setMenuOpen((v) => !v)}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                    {menuOpen ? (
                      <OpaqueMenuPanel className="min-w-[220px] p-2">
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
                                disabled={column.id === 'symbol'}
                                onChange={() =>
                                  persistLayout(toggleInstrumentsHubColumn(layout, column.id))
                                }
                              />
                              <span className="flex-1">
                                {INSTRUMENTS_HUB_COLUMN_LABELS[column.id]}
                              </span>
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
                                    toggleInstrumentsHubFavoriteColumn(
                                      favoriteColumnIds,
                                      column.id,
                                    ),
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
                          ★ Favoritas en menú. Columnas, split (desktop/móvil) y secciones del
                          detalle persisten en este navegador.
                        </p>
                      </OpaqueMenuPanel>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-auto">
                <div
                  className="sticky top-0 z-[1] border-b border-border bg-muted/80 backdrop-blur-sm"
                  style={{ minWidth: gridMinWidth }}
                >
                  <div
                    className="grid items-center"
                    style={{ gridTemplateColumns: gridTemplate, width: gridMinWidth }}
                  >
                    {visibleColumns.map((column) => {
                      const align = instrumentsHubColumnAlign(column.id);
                      const sortable = isSortableInstrumentsHubColumn(column.id);
                      const isSorted = sortState?.columnId === column.id;
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
                              persistLayout(
                                reorderInstrumentsHubColumns(layout, dragId, column.id),
                              );
                            }
                            setDragId(null);
                            setDropTargetId(null);
                          }}
                          className={cn(
                            'relative box-border py-1',
                            dragId === column.id && 'opacity-40',
                            dropTargetId === column.id && 'bg-primary/15 ring-1 ring-primary/40',
                          )}
                        >
                          <div
                            className={cn(
                              'flex h-full min-w-0 items-center gap-0.5 px-2 text-[10px] font-medium text-muted-foreground',
                              align === 'left' && 'justify-start',
                              align === 'center' && 'justify-center',
                              align === 'right' && 'justify-end',
                              sortable && 'cursor-pointer select-none hover:text-foreground',
                            )}
                            onClick={() => {
                              if (!sortable) return;
                              setSort(cycleInstrumentsHubColumnSort(sortState, column.id));
                            }}
                          >
                            {column.id !== 'actions' ? (
                              <GripVertical className="h-3 w-3 shrink-0 cursor-grab opacity-40" />
                            ) : null}
                            <span className="truncate">
                              {INSTRUMENTS_HUB_COLUMN_LABELS[column.id]}
                            </span>
                            {sortable ? (
                              <span className="shrink-0">
                                {!isSorted && <ArrowUpDown className="h-3 w-3 opacity-50" />}
                                {isSorted && sortState?.direction === 'asc' ? (
                                  <ArrowUp className="h-3 w-3" />
                                ) : null}
                                {isSorted && sortState?.direction === 'desc' ? (
                                  <ArrowDown className="h-3 w-3" />
                                ) : null}
                              </span>
                            ) : null}
                          </div>
                          {column.id !== 'actions' ? (
                            <ColumnResizeHandle
                              columnId={column.id}
                              width={column.width}
                              onResize={(columnId, width) => {
                                if (autoFitColumns) setAutoFitColumns(false);
                                persistLayout(
                                  resizeInstrumentsHubColumn(layout, columnId, width),
                                );
                              }}
                            />
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="divide-y divide-border/40 text-[11px]" style={{ minWidth: gridMinWidth }}>
                  {rows.map((instrument) => (
                    <div
                      key={instrument.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        setSelectedId(instrument.id);
                        setDetailPanelOpen(layoutMode, true);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedId(instrument.id);
                          setDetailPanelOpen(layoutMode, true);
                        }
                      }}
                      className={cn(
                        'grid cursor-pointer items-center py-1.5 hover:bg-muted/30',
                        selectedId === instrument.id && 'bg-primary/10',
                      )}
                      style={{ gridTemplateColumns: gridTemplate, width: gridMinWidth }}
                    >
                      {visibleColumns.map((column) => {
                        const align = instrumentsHubColumnAlign(column.id);
                        return (
                          <div
                            key={column.id}
                            className={cn(
                              'box-border min-w-0 px-2',
                              align === 'left' && 'text-left',
                              align === 'center' && 'text-center',
                              align === 'right' && 'text-right',
                            )}
                            onClick={
                              column.id === 'actions' || column.id === 'lists' || column.id === 'tracking'
                                ? (e) => e.stopPropagation()
                                : undefined
                            }
                          >
                            {renderCell(column.id, instrument)}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          }
          detail={
            selectedInstrument ? (
              detailPanelOpen ? (
                <InstrumentsHubDetailPanel
                  instrument={selectedInstrument}
                  sectionsOpen={detailSectionsOpen}
                  onToggleSection={toggleDetailSection}
                  onCollapse={() => setDetailPanelOpen(layoutMode, false)}
                  onClose={() => {
                    setSelectedId(null);
                    setDetailPanelOpen(layoutMode, false);
                  }}
                />
              ) : (
                <InstrumentsHubDetailCollapsedRail
                  symbol={selectedInstrument.symbol}
                  isWide={isWide}
                  onExpand={() => setDetailPanelOpen(layoutMode, true)}
                  onClose={() => {
                    setSelectedId(null);
                    setDetailPanelOpen(layoutMode, false);
                  }}
                />
              )
            ) : (
              <div className="flex h-full items-center justify-center p-4 text-[11px] text-muted-foreground">
                Selecciona un valor en la lista
              </div>
            )
          }
        />
      ) : null}
    </div>
  );
}
