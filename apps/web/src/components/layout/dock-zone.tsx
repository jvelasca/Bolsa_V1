import type { CSSProperties, ReactNode } from 'react';
import { Maximize2, Minimize2, X } from 'lucide-react';
import { IconButton } from '@/components/ui/icon-button';
import { cn } from '@/lib/utils';

interface DockZoneProps {
  title: string;
  open: boolean;
  maximized: boolean;
  onClose: () => void;
  onToggleMaximize: () => void;
  children: ReactNode;
  className?: string;
  headerExtra?: ReactNode;
  style?: CSSProperties;
  closable?: boolean;
  maximizable?: boolean;
}

export function DockZone({
  title,
  open,
  maximized,
  onClose,
  onToggleMaximize,
  children,
  className,
  headerExtra,
  style,
  closable = true,
  maximizable = true,
}: DockZoneProps) {
  if (!open) return null;

  return (
    <section
      className={cn(
        'flex min-h-0 min-w-0 flex-col overflow-hidden border-border bg-card/40',
        className,
      )}
      style={style}
    >
      <header className="flex h-7 shrink-0 items-center gap-1 border-b border-border bg-muted/30 px-1.5">
        <span className="flex-1 truncate px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </span>
        {headerExtra}
        {maximizable && (
          <IconButton
            icon={maximized ? Minimize2 : Maximize2}
            title={maximized ? 'Restaurar' : 'Maximizar'}
            onClick={onToggleMaximize}
          />
        )}
        {closable && <IconButton icon={X} title="Cerrar" onClick={onClose} />}
      </header>
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </section>
  );
}
