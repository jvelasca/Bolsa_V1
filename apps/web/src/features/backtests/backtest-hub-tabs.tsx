import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Botón de pestaña de la cabecera del Hub Backtesting (`/backtests`).
 * Extraído de `backtests-page.tsx` (F4·8).
 */
export function HubTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-accent text-primary"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
