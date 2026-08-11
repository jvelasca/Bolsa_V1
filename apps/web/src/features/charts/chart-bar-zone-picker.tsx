import { Star, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import {
  ChartBarZoneChipButton,
  ChartBarZoneIconAnchor,
  resolveBarZoneDisplayIds,
} from "@/features/charts/chart-bar-zone-rail-button";
import {
  CHART_BAR_ZONE_ROW_CLASS,
  CHART_BAR_ZONE_SCROLL_ROW_CLASS,
  CHART_ZONE_DROPDOWN_PANEL_CLASS,
} from "@/features/charts/chart-bar-zone-styles";
import { cn } from "@/lib/utils";

export interface ChartBarZoneMenuOption<T extends string> {
  id: T;
  label: string;
  hint: string;
}

interface ChartBarZonePickerProps<T extends string> {
  zoneIcon: LucideIcon;
  /** Nombre corto de la zona (menú, accesibilidad). */
  zoneTitle: string;
  zoneHint: string;
  activeId: T;
  favorites: T[];
  menuGroups: T[][];
  options: Record<T, ChartBarZoneMenuOption<T>>;
  isFavorite: (id: T) => boolean;
  onToggleFavorite: (id: T) => void;
  onSelectOption: (id: T) => void;
  getButtonLabel: (id: T) => string;
  renderButtonContent?: (id: T) => ReactNode;
  selectionMode?: "select" | "display";
  isOptionDisabled?: (id: T) => boolean;
  isButtonVisible?: (id: T) => boolean;
  isFavoriteLocked?: (id: T) => boolean;
  /** Controles extra en la misma fila (p. ej. zoom en Escala). */
  inlineTail?: ReactNode;
  trailing?: ReactNode;
  className?: string;
  getButtonClassName?: (id: T) => string | undefined;
}

export function ChartBarZonePicker<T extends string>({
  zoneIcon,
  zoneTitle,
  zoneHint,
  activeId,
  favorites,
  menuGroups,
  options,
  isFavorite,
  onToggleFavorite,
  onSelectOption,
  getButtonLabel,
  renderButtonContent,
  selectionMode = "select",
  isOptionDisabled,
  isButtonVisible,
  isFavoriteLocked,
  inlineTail,
  trailing,
  className,
  getButtonClassName,
}: ChartBarZonePickerProps<T>) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(
    null,
  );
  const zoneIconRef = useRef<HTMLDivElement | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const displayIds = useMemo(
    () =>
      resolveBarZoneDisplayIds(favorites, activeId, menuGroups, {
        includeActive: selectionMode === "display",
      }).filter((id) => isButtonVisible?.(id) ?? true),
    [activeId, favorites, isButtonVisible, menuGroups, selectionMode],
  );

  const menuOptionIds = useMemo(
    () => [...new Set(menuGroups.flat())],
    [menuGroups],
  );
  const showMenu = menuOptionIds.length > 0;

  function openMenu() {
    const rect = zoneIconRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMenuPos({ top: rect.bottom + 4, left: rect.left });
    setMenuOpen(true);
  }

  function closeMenu() {
    setMenuOpen(false);
  }

  function toggleMenu() {
    if (menuOpen) closeMenu();
    else openMenu();
  }

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMenu();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const onReposition = () => {
      const rect = zoneIconRef.current?.getBoundingClientRect();
      if (!rect) return;
      setMenuPos((prev) => {
        const next = { top: rect.bottom + 4, left: rect.left };
        if (prev && prev.top === next.top && prev.left === next.left)
          return prev;
        return next;
      });
    };
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [menuOpen]);

  const menu =
    menuOpen && menuPos
      ? createPortal(
          <>
            <div
              className="fixed inset-0 z-[200] bg-black/10"
              aria-hidden
              onPointerDown={closeMenu}
            />
            <div
              ref={menuRef}
              role="dialog"
              aria-modal="true"
              aria-label={zoneTitle}
              className={cn(
                "fixed z-[203] min-w-[12rem] p-1",
                CHART_ZONE_DROPDOWN_PANEL_CLASS,
              )}
              style={{ top: menuPos.top, left: menuPos.left }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <p
                className="px-2 py-1 text-[10px] text-muted-foreground"
                title={zoneHint}
              >
                {zoneTitle}
              </p>
              {menuGroups.map((group, groupIndex) => (
                <div key={group.join("-")}>
                  {groupIndex > 0 && (
                    <div className="my-1 border-t border-border" aria-hidden />
                  )}
                  {group.map((id) => {
                    const option = options[id];
                    const selected = id === activeId;
                    const locked = isFavoriteLocked?.(id) ?? false;
                    const favorited = isFavorite(id) || locked;
                    const disabled = isOptionDisabled?.(id) ?? false;
                    return (
                      <div
                        key={id}
                        className={cn(
                          "flex items-center gap-1 rounded px-1 hover:bg-accent",
                          selected && "bg-accent/40",
                          disabled && "opacity-50",
                        )}
                      >
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={() => {
                            onSelectOption(id);
                            closeMenu();
                          }}
                          className={cn(
                            "min-w-0 flex-1 px-2 py-1 text-left text-xs",
                            selected && "font-medium text-primary",
                          )}
                          title={option.hint}
                        >
                          {option.label}
                        </button>
                        <button
                          type="button"
                          disabled={locked}
                          title={
                            locked
                              ? "Siempre visible en la barra"
                              : favorited
                                ? "Quitar acceso directo en la barra"
                                : "Añadir acceso directo en la barra (chip)"
                          }
                          onClick={(event) => {
                            event.stopPropagation();
                            onToggleFavorite(id);
                          }}
                          className="rounded p-1 hover:bg-background/80 disabled:opacity-30"
                        >
                          <Star
                            className={cn(
                              "h-3.5 w-3.5",
                              favorited
                                ? "fill-amber-400 text-amber-400"
                                : "text-muted-foreground",
                            )}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </>,
          document.body,
        )
      : null;

  return (
    <div
      className={cn(
        CHART_BAR_ZONE_ROW_CLASS,
        menuOpen && "relative z-[202]",
        className,
      )}
      title={zoneHint}
    >
      <ChartBarZoneIconAnchor
        icon={zoneIcon}
        title={zoneTitle}
        hint={zoneHint}
        badgeLabel={
          selectionMode === "select" ? getButtonLabel(activeId) : undefined
        }
        isMenuOpen={menuOpen}
        showMenu={showMenu}
        containerRef={(el) => {
          zoneIconRef.current = el;
        }}
        onOpenMenu={toggleMenu}
      />

      <div className={CHART_BAR_ZONE_SCROLL_ROW_CLASS}>
        {displayIds.map((id) => {
          const option = options[id];
          const isActive = selectionMode === "select" && id === activeId;
          return (
            <ChartBarZoneChipButton
              key={id}
              label={getButtonLabel(id)}
              hint={option.hint}
              isActive={isActive}
              disabled={isOptionDisabled?.(id)}
              buttonClassName={getButtonClassName?.(id)}
              onActivate={() => {
                if (selectionMode === "select" && !isOptionDisabled?.(id)) {
                  onSelectOption(id);
                }
              }}
            >
              {renderButtonContent?.(id)}
            </ChartBarZoneChipButton>
          );
        })}
        {inlineTail}
      </div>

      {trailing}
      {menu}
    </div>
  );
}
