import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { HubTab } from "@/features/backtests/backtest-hub-nav";

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

/**
 * Barra de pestañas de la cabecera del Hub Backtesting (`/backtests`).
 * Extraído de `backtests-page.tsx` (F4·8).
 */
export function BacktestHubTabsBar({
  tab,
  onTab,
  onOpenLibrary,
}: {
  tab: HubTab;
  onTab: (next: HubTab) => void;
  onOpenLibrary: () => void;
}) {
  return (
    <div className="flex flex-wrap rounded-lg border border-border p-0.5">
      <HubTabButton active={tab === "run"} onClick={() => onTab("run")}>
        Probar estrategia
      </HubTabButton>
      <HubTabButton
        active={tab === "strategies"}
        onClick={() => onOpenLibrary()}
      >
        Biblioteca
      </HubTabButton>
      <HubTabButton active={tab === "jobs"} onClick={() => onTab("jobs")}>
        Lab · Optimizar
      </HubTabButton>
      <HubTabButton active={tab === "history"} onClick={() => onTab("history")}>
        Pruebas anteriores
      </HubTabButton>
    </div>
  );
}
