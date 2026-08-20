import type { WatchlistPanelTab } from "@bolsa/shared";
import { LayoutGrid, ListTree } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { ListHubPanel } from "@/features/trading/lists-tab/list-hub-panel";
import { ListValuesPanel } from "@/features/trading/lists-tab/list-values-panel";

function WatchlistPanelTabs({
  tab,
  onChange,
}: {
  tab: WatchlistPanelTab;
  onChange: (tab: WatchlistPanelTab) => void;
}) {
  return (
    <div
      className="grid shrink-0 grid-cols-2 gap-1 border-b border-border bg-muted/20 p-1"
      role="tablist"
      aria-label="Watchlist"
    >
      {(
        [
          { id: "lists" as const, label: "Listas", icon: ListTree },
          { id: "values" as const, label: "Valores", icon: LayoutGrid },
        ] as const
      ).map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={tab === id}
          className={cn(
            "inline-flex items-center justify-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
            tab === id
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
          onClick={() => onChange(id)}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" />
          {label}
        </button>
      ))}
    </div>
  );
}

export function WatchlistPanel() {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);
  const tab = listConfig.watchlistTab ?? "values";

  function setTab(next: WatchlistPanelTab) {
    updateListConfig({ watchlistTab: next });
    save();
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <WatchlistPanelTabs tab={tab} onChange={setTab} />
      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === "lists" ? <ListHubPanel /> : <ListValuesPanel />}
      </div>
    </div>
  );
}
