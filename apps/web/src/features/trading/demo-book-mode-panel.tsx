/**
 * Controles del libro operativo de la cuenta activa: MANUAL/SEMI + N posiciones + % sizing.
 * A1 — AUTO visible con copy de riesgos; pill deshabilitada (Camino D freeze).
 * Título UI = nombre de la cuenta activa (no «Libro DEMO»).
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 * @see docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md §3 A1
 */

import { cn } from '@/lib/utils';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import {
  DEMO_BOOK_AUTO_FOOTER,
  DEMO_BOOK_AUTO_RISK_LINES,
  DEMO_BOOK_AUTO_TOOLTIP,
  DEMO_BOOK_AUTO_UI_ENABLED,
} from '@/features/trading/demo-book-auto-copy';
import {
  DEMO_BOOK_MAX_OPEN_MAX,
  DEMO_BOOK_MAX_OPEN_MIN,
  DEMO_BOOK_SIZE_PCT_MAX,
  DEMO_BOOK_SIZE_PCT_MIN,
  patchDemoBookPrefs,
  type DemoBookCountryPrefer,
  type DemoBookMode,
  type DemoBookPrefs,
} from '@/features/trading/demo-book-prefs';
import { useDemoBookPrefs } from '@/features/trading/use-demo-book-prefs';

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
  const { account } = useActiveAccount();
  const prefs = useDemoBookPrefs();
  const accountTitle = account?.name?.trim() || 'Sin cuenta activa';

  function update(patch: Partial<DemoBookPrefs>) {
    patchDemoBookPrefs(patch);
  }

  return (
    <div
      className={cn(
        'space-y-2 rounded-md border border-border/80 bg-muted/20 p-2 text-[11px]',
        className,
      )}
      data-testid="demo-book-mode-panel"
    >
      <p className="font-medium text-foreground" title={accountTitle}>
        <span className="line-clamp-2">{accountTitle}</span>
        {!compact ? (
          <span className="ml-1 font-normal text-muted-foreground">
            · operativa
          </span>
        ) : null}
      </p>
      <div className="flex flex-wrap gap-1">
        {(['manual', 'semi', 'auto'] as const).map((mode) => {
          const disabled = mode === 'auto' && !DEMO_BOOK_AUTO_UI_ENABLED;
          const active = prefs.mode === mode;
          return (
            <button
              key={mode}
              type="button"
              disabled={disabled}
              aria-disabled={disabled}
              title={
                disabled
                  ? DEMO_BOOK_AUTO_TOOLTIP
                  : mode === 'manual'
                    ? 'Solo avisos · sin Confirm automático'
                    : 'Propuestas → Confirm F3 → DEMO'
              }
              onClick={() => {
                if (mode === 'auto' && !DEMO_BOOK_AUTO_UI_ENABLED) return;
                update({ mode });
              }}
              className={cn(
                'rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                active
                  ? 'border-emerald-500 bg-emerald-500/15 text-emerald-800 dark:text-emerald-300'
                  : 'border-border text-muted-foreground hover:border-primary/40 hover:text-foreground',
                disabled && 'border-dashed',
              )}
            >
              {MODE_LABEL[mode]}
              {disabled ? (
                <span className="ml-1 font-normal opacity-70">· prep</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {!DEMO_BOOK_AUTO_UI_ENABLED ? (
        <div
          className="space-y-1 border-t border-border/60 pt-1.5 text-[10px] leading-snug text-muted-foreground"
          data-testid="demo-book-auto-risk"
        >
          <p className="font-medium text-foreground/80">AUTO (Camino D) — riesgos</p>
          <ul className="list-disc space-y-0.5 pl-3.5">
            {DEMO_BOOK_AUTO_RISK_LINES.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
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
      <p className="text-[10px] leading-snug text-muted-foreground">{DEMO_BOOK_AUTO_FOOTER}</p>
    </div>
  );
}
