import { useEffect, useMemo, useRef, useState } from 'react';
import type { InstrumentListSummaryDto } from '@bolsa/shared';
import { MoreHorizontal } from 'lucide-react';
import { checkboxClassName } from '@/components/ui/dialog';
import { isListPinnedInCarousel, patchToggleCarouselList } from '@/lib/list-carousel-config';
import { useWorkspaceStore } from '@/stores/workspace-store';

export function ListCarouselMenu({
  virtualLists,
  apiLists,
}: {
  virtualLists: InstrumentListSummaryDto[];
  apiLists: InstrumentListSummaryDto[];
}) {
  const listConfig = useWorkspaceStore((state) => state.workspace.list);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const allLists = useMemo(
    () => [...virtualLists, ...apiLists],
    [apiLists, virtualLists],
  );

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  function toggleList(listId: string) {
    updateListConfig(patchToggleCarouselList(listId, listConfig, apiLists));
    save();
  }

  return (
    <div ref={menuRef} className="relative shrink-0 border-l border-border/60 pl-0.5">
      <button
        type="button"
        title="Configurar carrusel"
        className="rounded p-1 hover:bg-accent"
        onClick={() => setMenuOpen((value) => !value)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {menuOpen && (
        <div className="absolute right-0 top-full z-20 mt-1 min-w-[200px] rounded-md border border-border bg-card py-1 shadow-lg">
          <p className="px-2 py-1 text-[10px] font-medium text-muted-foreground">Carrusel</p>
          <div className="scroll-area max-h-48 overflow-auto">
            {allLists.map((list) => (
              <label
                key={list.id}
                className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-accent/50"
              >
                <input
                  type="checkbox"
                  className={checkboxClassName}
                  checked={isListPinnedInCarousel(list.id, listConfig)}
                  onChange={() => toggleList(list.id)}
                />
                <span className="truncate">{list.name}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
