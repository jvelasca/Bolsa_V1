/**
 * Switch barra Indicadores: overlay Finalista TOP #1 del valor/TF del gráfico.
 */

import { cn } from '@/lib/utils';
import {
  CHART_BAR_ZONE_LABEL_BTN_CLASS,
  CHART_BAR_ZONE_ROW_CLASS,
} from '@/features/charts/chart-bar-zone-styles';

type Props = {
  checked: boolean;
  disabled?: boolean;
  title?: string;
  onCheckedChange: (next: boolean) => void;
  className?: string;
};

export function ChartFinalistTop1Switch({
  checked,
  disabled,
  title,
  onCheckedChange,
  className,
}: Props) {
  return (
    <div
      className={cn(CHART_BAR_ZONE_ROW_CLASS, 'gap-1.5', className)}
      title={
        title ??
        'Mostrar en el gráfico los indicadores del Finalista TOP #1 (mismo timeframe)'
      }
      data-testid="chart-finalist-top1-switch"
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          CHART_BAR_ZONE_LABEL_BTN_CLASS,
          'inline-flex items-center gap-1.5 pr-1.5 disabled:cursor-not-allowed disabled:opacity-40',
          checked && 'border-emerald-500/50 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300',
        )}
      >
        <span
          className={cn(
            'relative inline-flex h-3.5 w-6 shrink-0 items-center rounded-full border transition-colors',
            checked
              ? 'border-emerald-500 bg-emerald-500/80'
              : 'border-border bg-muted',
          )}
          aria-hidden
        >
          <span
            className={cn(
              'absolute h-2.5 w-2.5 rounded-full bg-background shadow transition-transform',
              checked ? 'translate-x-3' : 'translate-x-0.5',
            )}
          />
        </span>
        <span className="chart-indicators-label-text text-[10px] font-semibold uppercase tracking-wide">
          TOP#1
        </span>
        <span className="chart-indicators-label-short text-[10px] font-semibold">T1</span>
      </button>
    </div>
  );
}
