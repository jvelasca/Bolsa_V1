/**
 * Panel detalle del hub Instrumentos — colapsable; secciones apiladas (acordeón).
 */

import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ChevronDown, PanelRightClose, X } from 'lucide-react';
import { DEFAULT_CHART_CONFIG, type InstrumentWithMetaDto } from '@bolsa/shared';
import { api } from '@/lib/api';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { OhlcvChart } from '@/features/charts/ohlcv-chart';
import { InstrumentStrategyTopPanel } from '@/features/backtests/instrument-strategy-top-panel';
import { InstrumentAnalysisSummary } from '@/features/trading/instrument-analysis-summary';
import { IconButton } from '@/components/ui/icon-button';
import { KeyValueList, KeyValueRow } from '@/components/ui/key-value-list';
import { cn } from '@/lib/utils';

export type InstrumentsHubDetailSectionId = 'resumen' | 'grafico' | 'analisis' | 'coach';

export const INSTRUMENTS_HUB_DETAIL_SECTIONS: Array<{
  id: InstrumentsHubDetailSectionId;
  label: string;
}> = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'grafico', label: 'Gráfico' },
  { id: 'analisis', label: 'Análisis' },
  { id: 'coach', label: 'Coach' },
];

export const DEFAULT_INSTRUMENTS_HUB_DETAIL_SECTIONS: Record<
  InstrumentsHubDetailSectionId,
  boolean
> = {
  resumen: true,
  grafico: true,
  analisis: false,
  coach: false,
};

function DetailSection({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-md border border-border/70 bg-card">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-2.5 py-2 text-left hover:bg-muted/40"
        aria-expanded={open}
        onClick={onToggle}
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
            !open && '-rotate-90',
          )}
        />
        <span className="text-[11px] font-semibold text-foreground">{title}</span>
      </button>
      {open ? (
        <div className="border-t border-border/60 px-2.5 py-2.5">{children}</div>
      ) : null}
    </section>
  );
}

export function InstrumentsHubDetailPanel({
  instrument,
  sectionsOpen,
  onToggleSection,
  onCollapse,
  onClose,
  className,
}: {
  instrument: InstrumentWithMetaDto;
  sectionsOpen: Record<InstrumentsHubDetailSectionId, boolean>;
  onToggleSection: (id: InstrumentsHubDetailSectionId) => void;
  onCollapse: () => void;
  onClose: () => void;
  className?: string;
}) {
  const chartOpen = sectionsOpen.grafico;
  const ohlcvQuery = useQuery({
    queryKey: ['ohlcv', instrument.id, 'hub-detail'],
    queryFn: () => api.getOhlcv(instrument.id, 180),
    enabled: chartOpen,
    staleTime: 60_000,
  });

  const indicatorsQuery = useQuery({
    queryKey: ['indicators', instrument.id, 'hub-detail'],
    queryFn: () => api.getIndicators(instrument.id, 180),
    enabled: chartOpen,
    staleTime: 60_000,
  });

  return (
    <div className={cn('flex h-full min-h-0 flex-col overflow-hidden', className)}>
      <div className="flex shrink-0 items-start justify-between gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{instrument.symbol}</p>
          <p className="truncate text-[11px] text-muted-foreground">{instrument.name}</p>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <Link
            to={`/instruments/${instrument.id}`}
            className="rounded px-1.5 py-0.5 text-[10px] font-medium text-primary hover:underline"
          >
            Ficha
          </Link>
          <IconButton
            icon={PanelRightClose}
            title="Colapsar panel de detalle"
            onClick={onCollapse}
          />
          <IconButton icon={X} title="Cerrar detalle" onClick={onClose} />
        </div>
      </div>

      <div className="scroll-area min-h-0 flex-1 overflow-x-hidden overflow-y-scroll overscroll-contain px-2.5 py-2.5">
        <div className="flex flex-col gap-2 pb-3">
          <DetailSection
            title="Resumen"
            open={sectionsOpen.resumen}
            onToggle={() => onToggleSection('resumen')}
          >
            <KeyValueList>
              <KeyValueRow label="Precio">
                {instrument.meta.lastClose != null
                  ? formatPrice(instrument.meta.lastClose)
                  : '—'}
              </KeyValueRow>
              <KeyValueRow
                label="Δ%"
                valueClassName={cn(
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
              </KeyValueRow>
              <KeyValueRow label="Exchange">{instrument.exchange}</KeyValueRow>
              <KeyValueRow label="Yahoo" valueClassName="font-mono text-[10px]">
                {instrument.yahooSymbol}
              </KeyValueRow>
              <KeyValueRow label="Sector">{instrument.sector ?? '—'}</KeyValueRow>
              <KeyValueRow label="ISIN" valueClassName="font-mono text-[10px]">
                {instrument.isin?.trim() || '—'}
              </KeyValueRow>
              <KeyValueRow label="Barras">{instrument.meta.barCount}</KeyValueRow>
              <KeyValueRow label="Últ. vela">
                {instrument.meta.lastBarDate ?? '—'}
              </KeyValueRow>
            </KeyValueList>
          </DetailSection>

          <DetailSection
            title="Gráfico"
            open={sectionsOpen.grafico}
            onToggle={() => onToggleSection('grafico')}
          >
            <div className="flex h-[min(240px,32vh)] min-h-[140px] flex-col">
              {ohlcvQuery.isLoading ? (
                <p className="text-[11px] text-muted-foreground">Cargando gráfico…</p>
              ) : (
                <OhlcvChart
                  bars={ohlcvQuery.data?.data ?? []}
                  indicators={indicatorsQuery.data?.data}
                  config={DEFAULT_CHART_CONFIG}
                  instrumentId={instrument.id}
                  symbol={instrument.symbol}
                  fillContainer
                  isLoading={ohlcvQuery.isLoading}
                />
              )}
            </div>
          </DetailSection>

          <DetailSection
            title="Análisis"
            open={sectionsOpen.analisis}
            onToggle={() => onToggleSection('analisis')}
          >
            <InstrumentAnalysisSummary
              instrumentId={instrument.id}
              symbol={instrument.symbol}
            />
          </DetailSection>

          <DetailSection
            title="Coach"
            open={sectionsOpen.coach}
            onToggle={() => onToggleSection('coach')}
          >
            <InstrumentStrategyTopPanel
              instrumentId={instrument.id}
              symbol={instrument.symbol}
              compact
            />
          </DetailSection>
        </div>
      </div>
    </div>
  );
}

/** Rail estrecho cuando el detalle está colapsado pero hay selección. */
export function InstrumentsHubDetailCollapsedRail({
  symbol,
  isWide,
  onExpand,
  onClose,
}: {
  symbol: string;
  isWide: boolean;
  onExpand: () => void;
  onClose: () => void;
}) {
  if (!isWide) {
    return (
      <div className="flex h-full min-h-0 w-full items-center gap-2 bg-muted/30 px-2">
        <IconButton icon={X} title="Quitar selección" onClick={onClose} />
        <button
          type="button"
          className="min-w-0 flex-1 truncate text-left text-[11px] font-semibold text-muted-foreground hover:text-foreground"
          title={`Mostrar detalle · ${symbol}`}
          onClick={onExpand}
        >
          Detalle · {symbol}
        </button>
        <button
          type="button"
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          title="Desplegar detalle"
          onClick={onExpand}
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col items-center gap-2 border-l border-border/60 bg-muted/30 py-2">
      <IconButton icon={X} title="Quitar selección" onClick={onClose} />
      <button
        type="button"
        className="flex flex-1 items-center justify-center px-1 text-[10px] font-semibold tracking-wide text-muted-foreground hover:text-foreground"
        style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
        title={`Mostrar detalle · ${symbol}`}
        onClick={onExpand}
      >
        {symbol}
      </button>
      <button
        type="button"
        className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        title="Desplegar detalle"
        onClick={onExpand}
      >
        <ChevronDown className="h-3.5 w-3.5 rotate-90" />
      </button>
    </div>
  );
}
