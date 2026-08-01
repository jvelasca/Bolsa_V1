import {
  CHART_SERIES_TYPE_MENU,
  findChartSeriesTypeOption,
  isChartSeriesTypeImplemented,
  seriesTypeRequiresParams,
  type ChartSeriesType,
  type ChartSeriesTypeParams,
} from '@bolsa/shared';
import { Star } from 'lucide-react';
import { cn } from '@/lib/utils';
import { FieldRow } from '@/components/ui/dialog';
import { useChartSeriesTypeFavorites } from '@/features/charts/use-chart-series-type-favorites';

export function ChartSeriesStylePanel({
  seriesType,
  seriesTypeParams,
  onSeriesTypeChange,
  onParamsChange,
}: {
  seriesType: ChartSeriesType;
  seriesTypeParams?: ChartSeriesTypeParams;
  onSeriesTypeChange: (next: ChartSeriesType) => void;
  onParamsChange: (patch: Partial<ChartSeriesTypeParams>) => void;
}) {
  const { toggleFavorite, isFavorite } = useChartSeriesTypeFavorites();
  const active = findChartSeriesTypeOption(seriesType);
  const showParams = seriesTypeRequiresParams(seriesType);

  return (
    <div className="space-y-4" id="inspector-config-series">
      <div>
        <p className="text-xs font-medium text-foreground">Tipo de barra / traza</p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Afecta solo a este gráfico. Pulsa una opción para aplicarla; la estrella añade un acceso
          directo en la barra.
        </p>
      </div>

      <p className="text-xs text-muted-foreground">
        Activo: <span className="font-medium text-foreground">{active.label}</span>
      </p>

      <div className="max-h-56 overflow-y-auto rounded-md border border-border">
        {CHART_SERIES_TYPE_MENU.map((entry, index) => {
          if (entry.kind === 'separator') {
            return <div key={`sep-${index}`} className="border-t border-border" aria-hidden />;
          }
          const option = findChartSeriesTypeOption(entry.id);
          const selected = seriesType === entry.id;
          const implemented = isChartSeriesTypeImplemented(entry.id);
          return (
            <div
              key={entry.id}
              className={cn(
                'flex items-center gap-1 px-1 py-0.5 hover:bg-accent/50',
                selected && 'bg-accent/60',
                !implemented && 'opacity-50',
              )}
            >
              <button
                type="button"
                disabled={!implemented}
                onClick={() => implemented && onSeriesTypeChange(entry.id)}
                className={cn(
                  'min-w-0 flex-1 px-2 py-1.5 text-left text-xs',
                  selected && 'font-medium text-primary',
                )}
              >
                {option.label}
              </button>
              <button
                type="button"
                title={isFavorite(entry.id) ? 'Quitar favorito de la barra' : 'Favorito en la barra'}
                onClick={() => toggleFavorite(entry.id)}
                className="rounded p-1 hover:bg-background/80"
              >
                <Star
                  className={cn(
                    'h-3.5 w-3.5',
                    isFavorite(entry.id) ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground',
                  )}
                />
              </button>
            </div>
          );
        })}
      </div>

      {showParams && (
        <section className="space-y-2 border-t border-border pt-3">
          <p className="text-xs font-medium text-foreground">Parámetros del tipo</p>
          <p className="text-[11px] text-muted-foreground">
            Los valores vacíos usan un tamaño automático (~0,5 % del precio medio) o los defaults del
            tipo.
          </p>
          {seriesType === 'renko' && (
            <FieldRow label="Tamaño de ladrillo">
              <input
                type="number"
                min={0.01}
                step={0.01}
                className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                value={seriesTypeParams?.renkoBrickSize ?? ''}
                onChange={(e) =>
                  onParamsChange({
                    renkoBrickSize: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              />
            </FieldRow>
          )}
          {seriesType === 'point-and-figure' && (
            <>
              <FieldRow label="Tamaño de caja">
                <input
                  type="number"
                  min={0.01}
                  step={0.01}
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                  value={seriesTypeParams?.pointAndFigureBox ?? ''}
                  onChange={(e) =>
                    onParamsChange({
                      pointAndFigureBox: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                />
              </FieldRow>
              <FieldRow label="Reversión">
                <input
                  type="number"
                  min={1}
                  step={1}
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                  value={seriesTypeParams?.pointAndFigureReversal ?? ''}
                  onChange={(e) =>
                    onParamsChange({
                      pointAndFigureReversal: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                />
              </FieldRow>
            </>
          )}
          {seriesType === 'line-break' && (
            <FieldRow label="Líneas de ruptura">
              <input
                type="number"
                min={1}
                step={1}
                className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                value={seriesTypeParams?.lineBreakLines ?? ''}
                onChange={(e) =>
                  onParamsChange({
                    lineBreakLines: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              />
            </FieldRow>
          )}
          {seriesType === 'kagi' && (
            <FieldRow label="Reversión (%)">
              <input
                type="number"
                min={0.1}
                step={0.1}
                className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                value={seriesTypeParams?.kagiReversal ?? ''}
                onChange={(e) =>
                  onParamsChange({
                    kagiReversal: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              />
            </FieldRow>
          )}
        </section>
      )}
    </div>
  );
}
