/**
 * Controles del libro DEMO: modo MANUAL/SEMI + N posiciones + % sizing.
 * Slice 1 — AUTO deshabilitado (Camino D freeze).
 */

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  DEMO_BOOK_MAX_OPEN_MAX,
  DEMO_BOOK_MAX_OPEN_MIN,
  DEMO_BOOK_SIZE_PCT_MAX,
  DEMO_BOOK_SIZE_PCT_MIN,
  loadDemoBookPrefs,
  patchDemoBookPrefs,
  type DemoBookCountryPrefer,
  type DemoBookMode,
  type DemoBookPrefs,
} from '@/features/trading/demo-book-prefs';

const MODE_LABEL: Record<DemoBookMode, string> = {
  manual: 'Manual',
  semi: 'Semi',
  auto: 'Auto',
};

const GEO_LABEL: Record<DemoBookCountryPrefer, string> = {
  home_first: 'País primero',
  europe_first: 'Europa primero',
  global_ok: 'Sin preferencia',
};

type Props = {
  className?: string;
  compact?: boolean;
};

export function DemoBookModePanel({ className, compact }: Props) {
  const [prefs, setPrefs] = useState<DemoBookPrefs>(() => loadDemoBookPrefs());

  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === 'bolsa-demo-book-prefs-v1') {
        setPrefs(loadDemoBookPrefs());
      }
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  function update(patch: Partial<DemoBookPrefs>) {
    setPrefs(patchDemoBookPrefs(patch));
  }

  return (
    <div
      className={cn(
        'space-y-2 rounded-md border border-border/80 bg-muted/20 p-2 text-[11px]',
        className,
      )}
      data-testid="demo-book-mode-panel"
    >
      <p className="font-medium text-foreground">
        Libro DEMO
        {!compact ? (
          <span className="ml-1 font-normal text-muted-foreground">
            · operativa
          </span>
        ) : null}
      </p>
      <div className="flex flex-wrap gap-1">
        {(['manual', 'semi', 'auto'] as const).map((mode) => {
          const disabled = mode === 'auto';
          const active = prefs.mode === mode;
          return (
            <button
              key={mode}
              type="button"
              disabled={disabled}
              title={
                disabled
                  ? 'AUTO congelado (Camino D). Usa SEMI + Confirm.'
                  : mode === 'manual'
                    ? 'Solo avisos · sin Confirm automático'
                    : 'Propuestas → Confirm F3 → DEMO'
              }
              onClick={() => update({ mode })}
              className={cn(
                'rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                active
                  ? 'border-emerald-500 bg-emerald-500/15 text-emerald-800 dark:text-emerald-300'
                  : 'border-border text-muted-foreground hover:border-primary/40 hover:text-foreground',
              )}
            >
              {MODE_LABEL[mode]}
            </button>
          );
        })}
      </div>
      <div className={cn('grid gap-1.5', compact ? 'grid-cols-1' : 'grid-cols-2')}>
        <label className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">Máx. posiciones</span>
          <input
            type="number"
            min={DEMO_BOOK_MAX_OPEN_MIN}
            max={DEMO_BOOK_MAX_OPEN_MAX}
            value={prefs.maxOpenPositions}
            onChange={(e) =>
              update({ maxOpenPositions: Number(e.target.value) })
            }
            className="rounded border border-border bg-background px-1.5 py-1 text-foreground"
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">% cash / op</span>
          <input
            type="number"
            min={DEMO_BOOK_SIZE_PCT_MIN}
            max={DEMO_BOOK_SIZE_PCT_MAX}
            value={prefs.defaultSizePctOfCash}
            onChange={(e) =>
              update({ defaultSizePctOfCash: Number(e.target.value) })
            }
            className="rounded border border-border bg-background px-1.5 py-1 text-foreground"
            title="Por defecto ~10% del efectivo disponible"
          />
        </label>
        <label className={cn('flex flex-col gap-0.5', compact ? '' : 'col-span-2')}>
          <span className="text-muted-foreground">Preferencia geo</span>
          <select
            value={prefs.countryPrefer}
            onChange={(e) =>
              update({ countryPrefer: e.target.value as DemoBookCountryPrefer })
            }
            className="rounded border border-border bg-background px-1.5 py-1 text-foreground"
            title="Suave: no bloquea óptimos de otras zonas"
          >
            {(Object.keys(GEO_LABEL) as DemoBookCountryPrefer[]).map((k) => (
              <option key={k} value={k}>
                {GEO_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        SEMI = Confirm humano (F3). Geo ordena la cola (óptimo → preferencia); no veta.
      </p>
    </div>
  );
}
