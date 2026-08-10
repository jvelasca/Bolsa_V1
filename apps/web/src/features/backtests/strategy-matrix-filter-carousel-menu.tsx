/**
 * Menú (…) del carrusel de filtros de la matriz — visibles + favoritos ★.
 */

import { MoreHorizontal, Star } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { checkboxClassName } from "@/components/ui/dialog";
import {
  STRATEGY_MATRIX_FILTER_IDS,
  STRATEGY_MATRIX_FILTER_LABELS,
  type StrategyMatrixFilter,
} from "@/features/backtests/backtest-strategy-matrix";
import {
  saveStrategyMatrixFilterCarouselPrefs,
  toggleStrategyMatrixFilterFavorite,
  toggleStrategyMatrixFilterVisible,
  type StrategyMatrixFilterCarouselPrefs,
} from "@/features/backtests/strategy-matrix-filter-carousel-prefs";
import { cn } from "@/lib/utils";

type Props = {
  prefs: StrategyMatrixFilterCarouselPrefs;
  onPrefsChange: (next: StrategyMatrixFilterCarouselPrefs) => void;
  /** Si el filtro activo queda oculto, el padre reubica. */
  activeFilter: StrategyMatrixFilter;
  onActiveHidden?: (nextVisible: StrategyMatrixFilter) => void;
};

export function StrategyMatrixFilterCarouselMenu({
  prefs,
  onPrefsChange,
  activeFilter,
  onActiveHidden,
}: Props) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  function commit(next: StrategyMatrixFilterCarouselPrefs) {
    saveStrategyMatrixFilterCarouselPrefs(next);
    onPrefsChange(next);
    if (!next.visibleIds.includes(activeFilter) && onActiveHidden) {
      onActiveHidden(next.visibleIds[0] ?? "all");
    }
  }

  return (
    <div
      ref={menuRef}
      className="relative shrink-0 border-l border-border/60 pl-0.5"
    >
      <button
        type="button"
        title="Configurar carrusel de filtros"
        className="rounded p-1 hover:bg-accent"
        onClick={() => setOpen((v) => !v)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-30 mt-1 min-w-[220px] rounded-md border border-border bg-background py-1 shadow-lg ring-1 ring-black/10 dark:bg-zinc-950 dark:ring-white/10">
          <p className="px-2 py-1 text-[10px] font-medium text-muted-foreground">
            Carrusel · filtros
          </p>
          <div className="scroll-area max-h-56 overflow-auto">
            {STRATEGY_MATRIX_FILTER_IDS.map((id) => {
              const visible = prefs.visibleIds.includes(id);
              const favorite = prefs.favoriteIds.includes(id);
              const lastVisible = visible && prefs.visibleIds.length <= 1;
              return (
                <label
                  key={id}
                  className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-xs hover:bg-accent/50"
                >
                  <input
                    type="checkbox"
                    className={checkboxClassName}
                    checked={visible}
                    disabled={lastVisible}
                    onChange={() =>
                      commit(toggleStrategyMatrixFilterVisible(prefs, id))
                    }
                  />
                  <span className="min-w-0 flex-1 truncate">
                    {STRATEGY_MATRIX_FILTER_LABELS[id]}
                  </span>
                  <button
                    type="button"
                    title={favorite ? "Quitar de favoritos" : "Marcar favorito"}
                    disabled={!visible}
                    className={cn(
                      "rounded p-0.5",
                      favorite
                        ? "text-amber-500"
                        : "text-muted-foreground/50 hover:text-muted-foreground",
                      !visible && "opacity-30",
                    )}
                    onClick={(event) => {
                      event.preventDefault();
                      if (!visible) return;
                      commit(toggleStrategyMatrixFilterFavorite(prefs, id));
                    }}
                  >
                    <Star
                      className="h-3 w-3"
                      fill={favorite ? "currentColor" : "none"}
                    />
                  </button>
                </label>
              );
            })}
          </div>
          <p className="mt-0.5 border-t border-border/60 px-2 pt-1.5 text-[10px] text-muted-foreground">
            ★ Favoritos al inicio del carrusel · en este dispositivo
          </p>
        </div>
      ) : null}
    </div>
  );
}
