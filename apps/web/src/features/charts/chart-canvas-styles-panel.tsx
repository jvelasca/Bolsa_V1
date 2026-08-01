import type { ChartInstanceConfig } from '@bolsa/shared';
import { Magnet } from 'lucide-react';

import { checkboxClassName, inputClassName } from '@/components/ui/dialog';
import { requestChartReflow } from '@/features/charts/chart-utils';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace-store';

function ChartColorInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const pickerValue = value.startsWith('#') ? value : '#22c55e';
  return (
    <div className="flex items-center gap-2">
      <input
        type="color"
        value={pickerValue}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-10 shrink-0 cursor-pointer rounded border border-border bg-background"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClassName}
      />
    </div>
  );
}

function SectionTitle({ children }: { children: string }) {
  return (
    <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h3>
  );
}

/** Estilos del canvas: rejilla, cursor, márgenes, colores e indicadores legacy. */
export function ChartCanvasStylesPanel({
  chartId,
  config,
  showFixedHeight = false,
}: {
  chartId: string;
  config: ChartInstanceConfig;
  /** Altura fija (p. ej. vista detalle de instrumento). */
  showFixedHeight?: boolean;
}) {
  const updateChartConfig = useWorkspaceStore((s) => s.updateChartConfig);
  const resetChartConfig = useWorkspaceStore((s) => s.resetChartConfig);

  function patch(partial: {
    grid?: Partial<ChartInstanceConfig['grid']>;
    cursor?: Partial<ChartInstanceConfig['cursor']>;
    colors?: Partial<ChartInstanceConfig['colors']>;
    display?: Partial<ChartInstanceConfig['display']>;
  }) {
    updateChartConfig({
      chartId,
      ...partial,
    });
    requestChartReflow();
  }

  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <SectionTitle>Rejilla</SectionTitle>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            className={checkboxClassName}
            checked={config.grid.showHorizontal}
            onChange={(e) => patch({ grid: { showHorizontal: e.target.checked } })}
          />
          Líneas horizontales
        </label>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            className={checkboxClassName}
            checked={config.grid.showVertical}
            onChange={(e) => patch({ grid: { showVertical: e.target.checked } })}
          />
          Líneas verticales
        </label>
      </section>

      <section className="space-y-2">
        <SectionTitle>Cursor del gráfico</SectionTitle>
        <div className="flex items-center gap-2">
          <button
            type="button"
            title={config.cursor.mode === 'magnet' ? 'Imán activo' : 'Imán desactivado'}
            onClick={() =>
              patch({
                cursor: { mode: config.cursor.mode === 'magnet' ? 'crosshair' : 'magnet' },
              })
            }
            className={cn(
              'flex h-7 w-7 items-center justify-center rounded border border-border text-muted-foreground hover:bg-accent',
              config.cursor.mode === 'magnet' && 'bg-accent text-primary',
            )}
          >
            <Magnet className="h-3.5 w-3.5" />
          </button>
          <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs">
            <span className="text-muted-foreground">Modo</span>
            <select
              className={inputClassName}
              value={config.cursor.mode}
              onChange={(e) =>
                patch({ cursor: { mode: e.target.value as 'crosshair' | 'magnet' } })
              }
            >
              <option value="crosshair">Libre (crosshair)</option>
              <option value="magnet">Imán (ajuste a OHLC)</option>
            </select>
          </label>
        </div>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            className={checkboxClassName}
            checked={config.cursor.showOhlcInTooltip}
            onChange={(e) => patch({ cursor: { showOhlcInTooltip: e.target.checked } })}
          />
          OHLC en tooltip del gráfico
        </label>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            className={checkboxClassName}
            checked={config.cursor.showTimeAxisLabel ?? true}
            onChange={(e) => patch({ cursor: { showTimeAxisLabel: e.target.checked } })}
          />
          Etiqueta de fecha en eje temporal (X)
        </label>
      </section>

      <section className="space-y-2">
        <SectionTitle>Márgenes</SectionTitle>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Margen superior (%)</span>
          <input
            type="number"
            min={0}
            max={30}
            className={inputClassName}
            value={config.grid.topMarginPct}
            onChange={(e) => patch({ grid: { topMarginPct: Number(e.target.value) } })}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Margen derecho (%)</span>
          <input
            type="number"
            min={0}
            max={30}
            className={inputClassName}
            value={config.grid.rightMarginPct}
            onChange={(e) => patch({ grid: { rightMarginPct: Number(e.target.value) } })}
          />
        </label>
        {showFixedHeight && (
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">Altura (px)</span>
            <input
              type="number"
              min={280}
              max={900}
              step={20}
              className={inputClassName}
              value={config.display.height}
              onChange={(e) => patch({ display: { height: Number(e.target.value) } })}
            />
          </label>
        )}
      </section>

      <section className="space-y-2">
        <SectionTitle>Colores</SectionTitle>
        {(
          [
            ['Velas alcistas', 'upColor'],
            ['Velas bajistas', 'downColor'],
            ['Cuadrícula', 'gridColor'],
            ['Volumen alcista', 'volumeUpColor'],
            ['Volumen bajista', 'volumeDownColor'],
            ['SMA 20', 'sma20Color'],
            ['SMA 50', 'sma50Color'],
            ['EMA 20', 'ema20Color'],
            ['RSI 14', 'rsi14Color'],
          ] as const
        ).map(([label, key]) => (
          <label key={key} className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">{label}</span>
            <ChartColorInput
              value={config.colors[key]}
              onChange={(value) => patch({ colors: { [key]: value } })}
            />
          </label>
        ))}
      </section>

      <section className="space-y-2">
        <SectionTitle>Indicadores en canvas</SectionTitle>
        <p className="text-[10px] text-muted-foreground">
          Toggles rápidos del gráfico. Para más control usa Capas o el catálogo de indicadores.
        </p>
        <div className="grid grid-cols-2 gap-2">
          {(
            [
              ['Volumen', 'showVolume'],
              ['SMA 20', 'showSma20'],
              ['SMA 50', 'showSma50'],
              ['EMA 20', 'showEma20'],
              ['RSI 14 (panel)', 'showRsi14'],
            ] as const
          ).map(([label, key]) => (
            <label key={key} className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                className={checkboxClassName}
                checked={config.display[key]}
                onChange={(e) => patch({ display: { [key]: e.target.checked } })}
              />
              {label}
            </label>
          ))}
        </div>
      </section>

      <button
        type="button"
        className="w-full rounded-md border border-border px-2 py-1.5 text-left text-xs hover:bg-accent"
        onClick={() => resetChartConfig(chartId)}
      >
        Restaurar estilos por defecto
      </button>
    </div>
  );
}
