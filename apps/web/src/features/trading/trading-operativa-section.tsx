/**
 * Sección colapsable vertical del panel Operativa (Trading).
 */

import { ChevronDown } from 'lucide-react';
import {
  type OperativaSectionId,
  useTradingLayoutStore,
} from '@/stores/trading-layout-store';
import { cn } from '@/lib/utils';

export function TradingOperativaSection({
  sectionId,
  title,
  children,
  className,
}: {
  sectionId: OperativaSectionId;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  const open = useTradingLayoutStore(
    (s) => s.operativaSections?.[sectionId] ?? true,
  );
  const toggle = useTradingLayoutStore((s) => s.toggleOperativaSection);

  return (
    <section
      className={cn(
        'min-w-0 overflow-hidden rounded-md border border-border/80 bg-background/60',
        className,
      )}
      data-testid={`operativa-section-${sectionId}`}
    >
      <button
        type="button"
        className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left hover:bg-muted/40"
        aria-expanded={open}
        onClick={() => toggle(sectionId)}
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
            !open && '-rotate-90',
          )}
        />
        <span className="min-w-0 flex-1 truncate text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </span>
      </button>
      {open ? (
        <div className="space-y-2 border-t border-border/70 px-2 py-2 text-[11px]">{children}</div>
      ) : null}
    </section>
  );
}
