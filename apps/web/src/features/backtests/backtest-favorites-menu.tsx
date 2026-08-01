import { MoreHorizontal, Star } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { BacktestHudFieldOption } from '@/features/backtests/backtest-hud-prefs';
import { cn } from '@/lib/utils';

type Props<T extends string> = {
  title: string;
  hint?: string;
  options: BacktestHudFieldOption<T>[];
  favorites: T[];
  onToggleFavorite: (id: T) => void;
  className?: string;
  /** Align menu to the right edge of the button (bars). */
  align?: 'left' | 'right';
};

/** (…) menu with star favorites — same philosophy as chart / list hubs. */
export function BacktestFavoritesMenu<T extends string>({
  title,
  hint,
  options,
  favorites,
  onToggleFavorite,
  className,
  align = 'right',
}: Props<T>) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const favoriteSet = new Set(favorites);

  function openMenu() {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return;
    const width = 220;
    const left =
      align === 'right'
        ? Math.max(8, rect.right - width)
        : Math.min(rect.left, window.innerWidth - width - 8);
    setPos({ top: rect.bottom + 4, left });
    setOpen(true);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    const onReposition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = 220;
      const left =
        align === 'right'
          ? Math.max(8, rect.right - width)
          : Math.min(rect.left, window.innerWidth - width - 8);
      setPos({ top: rect.bottom + 4, left });
    };
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', onReposition);
    window.addEventListener('scroll', onReposition, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', onReposition);
      window.removeEventListener('scroll', onReposition, true);
    };
  }, [align, open]);

  const menu =
    open && pos
      ? createPortal(
          <>
            <div
              className="fixed inset-0 z-[200] bg-black/10"
              aria-hidden
              onPointerDown={() => setOpen(false)}
            />
            <div
              ref={menuRef}
              role="dialog"
              aria-label={title}
              className="fixed z-[203] min-w-[13.5rem] rounded-md border border-border bg-card p-1 shadow-lg"
              style={{ top: pos.top, left: pos.left, width: 220 }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <p className="px-2 py-1 text-[10px] font-medium text-muted-foreground" title={hint}>
                {title}
              </p>
              {hint && (
                <p className="px-2 pb-1 text-[10px] leading-snug text-muted-foreground/80">
                  Estrella = visible en la barra. Se guarda en este dispositivo.
                </p>
              )}
              {options.map((option) => {
                const favorited = favoriteSet.has(option.id) || Boolean(option.locked);
                return (
                  <div
                    key={option.id}
                    className="flex items-center gap-1 rounded px-1 hover:bg-accent"
                  >
                    <span className="min-w-0 flex-1 px-2 py-1 text-left text-xs" title={option.hint}>
                      {option.label}
                    </span>
                    <button
                      type="button"
                      disabled={option.locked}
                      title={
                        option.locked
                          ? 'Siempre visible'
                          : favorited
                            ? 'Quitar de favoritos'
                            : 'Añadir a favoritos'
                      }
                      className="rounded p-1 hover:bg-background/80 disabled:opacity-40"
                      onClick={() => onToggleFavorite(option.id)}
                    >
                      <Star
                        className={cn(
                          'h-3.5 w-3.5',
                          favorited ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground',
                        )}
                      />
                    </button>
                  </div>
                );
              })}
            </div>
          </>,
          document.body,
        )
      : null;

  return (
    <div className={cn('relative shrink-0', className)}>
      <button
        ref={buttonRef}
        type="button"
        title={`${title}: más opciones y favoritos`}
        aria-label={`${title}: más opciones y favoritos`}
        aria-expanded={open}
        className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={() => {
          if (open) setOpen(false);
          else openMenu();
        }}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {menu}
    </div>
  );
}
