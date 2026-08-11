import type { LucideIcon } from "lucide-react";
import { ChevronDown } from "lucide-react";
import {
  type ScreenerPanelId,
  useScreenerPreferencesStore,
} from "@/stores/screener-preferences-store";
import { cn } from "@/lib/utils";

interface ScreenerCollapsibleSectionProps {
  panelId: ScreenerPanelId;
  title: string;
  icon?: LucideIcon;
  badge?: React.ReactNode;
  defaultOpen?: boolean;
  splitMode?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function ScreenerCollapsibleSection({
  panelId,
  title,
  icon: Icon,
  badge,
  defaultOpen = true,
  splitMode = false,
  children,
  className,
}: ScreenerCollapsibleSectionProps) {
  const storedOpen = useScreenerPreferencesStore(
    (state) => state.layout.panels[panelId],
  );
  const togglePanel = useScreenerPreferencesStore((state) => state.togglePanel);
  const open = storedOpen ?? defaultOpen;

  return (
    <section
      className={cn(
        "min-w-0 overflow-hidden rounded-lg border border-border bg-card shadow-sm",
        splitMode && "flex h-full min-h-0 flex-col",
        className,
      )}
    >
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-muted/40"
        aria-expanded={open}
        onClick={() => togglePanel(panelId)}
      >
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            !open && "-rotate-90",
          )}
        />
        {Icon && <Icon className="h-4 w-4 shrink-0 text-primary" />}
        <span className="min-w-0 flex-1 truncate text-sm font-medium">
          {title}
        </span>
        {badge}
      </button>
      {open && (
        <div
          className={cn(
            "border-t border-border px-3 py-3 min-w-0",
            splitMode
              ? "flex min-h-0 flex-1 flex-col overflow-hidden"
              : "max-h-[min(70vh,520px)] overflow-y-auto overscroll-contain",
          )}
        >
          {children}
        </div>
      )}
    </section>
  );
}
