import {
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  Settings2,
  Trash2,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface IndicatorPanelChromeProps {
  title: string;
  subtitle?: string;
  hidden?: boolean;
  badge?: ReactNode;
  onConfigure: () => void;
  onToggleHidden: () => void;
  onDelete: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onOpenConfig?: () => void;
  extra?: ReactNode;
  className?: string;
}

export function IndicatorPanelChrome({
  title,
  subtitle,
  hidden = false,
  badge,
  onConfigure,
  onToggleHidden,
  onDelete,
  onMoveUp,
  onMoveDown,
  onOpenConfig,
  extra,
  className,
}: IndicatorPanelChromeProps) {
  const openConfig = onOpenConfig ?? onConfigure;

  return (
    <div
      className={cn(
        "flex h-[1.625rem] shrink-0 items-center gap-0.5 border-b border-border/60 bg-muted/20 px-2",
        hidden && "opacity-55",
        className,
      )}
      onDoubleClick={(event) => {
        event.preventDefault();
        openConfig();
      }}
      title="Doble clic para configurar el indicador"
    >
      <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden">
        <span className="truncate text-[11px] font-semibold leading-none text-foreground">
          {title}
        </span>
        {subtitle && (
          <span className="truncate text-[10px] leading-none text-muted-foreground">
            {subtitle}
          </span>
        )}
        {hidden && (
          <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[9px] font-medium uppercase text-muted-foreground">
            Oculto
          </span>
        )}
        {badge}
      </div>

      {extra}

      <button
        type="button"
        title="Configurar indicador"
        onClick={openConfig}
        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <Settings2 className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        title={hidden ? "Mostrar indicador" : "Ocultar indicador"}
        onClick={onToggleHidden}
        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        {hidden ? (
          <Eye className="h-3.5 w-3.5" />
        ) : (
          <EyeOff className="h-3.5 w-3.5" />
        )}
      </button>
      <button
        type="button"
        title="Eliminar indicador"
        onClick={onDelete}
        className="rounded p-0.5 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        disabled={!onMoveUp}
        title="Subir posición"
        onClick={onMoveUp}
        className="indicator-panel-move-btns rounded p-0.5 hover:bg-accent disabled:opacity-30"
      >
        <ChevronUp className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        disabled={!onMoveDown}
        title="Bajar posición"
        onClick={onMoveDown}
        className="indicator-panel-move-btns rounded p-0.5 hover:bg-accent disabled:opacity-30"
      >
        <ChevronDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
