import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChartInspectorShortcutButtonProps {
  icon: LucideIcon;
  title: string;
  onClick: () => void;
  badge?: number;
  active?: boolean;
  className?: string;
}

/** Botón compacto que abre el inspector en una pestaña concreta. */
export function ChartInspectorShortcutButton({
  icon: Icon,
  title,
  onClick,
  badge,
  active,
  className,
}: ChartInspectorShortcutButtonProps) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={cn(
        "relative inline-flex h-[1.375rem] w-[1.375rem] shrink-0 items-center justify-center rounded border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-accent hover:text-foreground",
        active && "border-primary/40 bg-primary/10 text-primary",
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {badge != null && badge > 0 && (
        <span className="absolute -right-1 -top-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-primary px-0.5 text-[8px] font-semibold leading-none text-primary-foreground">
          {badge > 9 ? "9+" : badge}
        </span>
      )}
    </button>
  );
}
