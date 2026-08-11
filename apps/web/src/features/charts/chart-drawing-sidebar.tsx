import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import {
  ChevronDown,
  Eraser,
  LayoutTemplate,
  Star,
  Trash2,
} from "lucide-react";
import type { ChartDrawTool } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { ChartDrawingGlobalToggles } from "@/features/charts/chart-drawing-global-toggles";
import {
  DRAWING_TOOL_CATALOG,
  DRAWING_TOOL_GROUPS,
  availableToolsInGroup,
  findDrawingToolDefinition,
  groupButtonIconTool,
  drawingRailFamilyBlocks,
  isActiveDrawTool,
  isGroupRailToolActive,
  resolveGroupRailActivateTool,
  toolBelongsToGroup,
  type DrawingRailFamilyBlock,
  type DrawingToolGroupId,
} from "@/features/charts/chart-drawing-tools";
import { useDrawToolFavorites } from "@/features/charts/use-draw-tool-favorites";
import { ChartDrawToolStyleBar } from "@/features/charts/chart-draw-tool-style-bar";
import { CHART_ZONE_DROPDOWN_PANEL_CLASS } from "@/features/charts/chart-bar-zone-styles";
import { isShapeDrawTool } from "@/features/charts/chart-draw-tool-utils";

function DrawingToolFlyout({
  openGroup,
  flyoutPos,
  tool,
  flyoutRef,
  onClose,
  pickTool,
  isFavorite,
  toggleFavorite,
}: {
  openGroup: DrawingToolGroupId;
  flyoutPos: { top: number; left: number };
  tool: ChartDrawTool;
  flyoutRef: RefObject<HTMLDivElement | null>;
  onClose: () => void;
  pickTool: (id: ChartDrawTool) => void;
  isFavorite: (id: ChartDrawTool) => boolean;
  toggleFavorite: (id: ChartDrawTool) => void;
}) {
  const flyoutItems = DRAWING_TOOL_CATALOG.filter(
    (item) => item.group === openGroup && isActiveDrawTool(item.id),
  );

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-[200] bg-black/10"
        aria-hidden
        onPointerDown={onClose}
      />
      <div
        ref={flyoutRef}
        role="dialog"
        aria-modal="true"
        aria-label={DRAWING_TOOL_GROUPS.find((g) => g.id === openGroup)?.label}
        className={cn(
          "fixed z-[203] max-h-[min(50vh,20rem)] min-w-[11rem] overflow-y-auto py-1",
          CHART_ZONE_DROPDOWN_PANEL_CLASS,
        )}
        style={{ top: flyoutPos.top, left: flyoutPos.left }}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          {DRAWING_TOOL_GROUPS.find((g) => g.id === openGroup)?.label}
        </p>
        {flyoutItems.map(({ id, label, icon: Icon, available, hint }) => {
          const toolId = id as ChartDrawTool;
          const favorited = isFavorite(toolId);

          return (
            <div
              key={id}
              className={cn(
                "flex items-center gap-1 rounded px-1 hover:bg-accent",
                tool === toolId && available && "bg-accent/60",
                !available && "opacity-50",
              )}
            >
              <button
                type="button"
                disabled={!available || !isActiveDrawTool(toolId)}
                title={available ? label : (hint ?? label)}
                onPointerDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  if (available && isActiveDrawTool(toolId)) {
                    pickTool(toolId);
                  }
                }}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left text-xs",
                  tool === toolId && available && "font-medium text-primary",
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span>{label}</span>
                {!available && (
                  <span className="ml-auto text-[10px] text-muted-foreground">
                    Próx.
                  </span>
                )}
              </button>
              {isActiveDrawTool(toolId) && (
                <button
                  type="button"
                  title={
                    favorited
                      ? "Quitar chip de la barra"
                      : "Añadir chip en la barra"
                  }
                  onPointerDown={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    toggleFavorite(toolId);
                  }}
                  className="rounded p-1 hover:bg-background/80"
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
              )}
            </div>
          );
        })}
      </div>
    </>,
    document.body,
  );
}

function RailSeparator({ strong = false }: { strong?: boolean }) {
  return (
    <div
      className={cn(
        "my-0.5 shrink-0 rounded-full bg-border",
        strong ? "h-0.5 w-7" : "h-px w-6",
      )}
      aria-hidden
    />
  );
}

function ToolRailButton({
  title,
  icon: Icon,
  badgeLabel,
  isActive,
  isMenuOpen,
  showMenu,
  containerRef,
  onActivate,
  onOpenMenu,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  badgeLabel?: string;
  isActive: boolean;
  isMenuOpen: boolean;
  showMenu: boolean;
  containerRef?: (el: HTMLDivElement | null) => void;
  onActivate: () => void;
  onOpenMenu: () => void;
}) {
  const hasBadge = Boolean(badgeLabel);

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative shrink-0",
        hasBadge ? "h-10 w-8 sm:w-9" : "h-8 w-8",
      )}
    >
      <button
        type="button"
        title={title}
        onPointerDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onActivate();
        }}
        className={cn(
          "flex h-full w-full flex-col items-center justify-center gap-0 rounded transition-colors hover:bg-accent",
          (isMenuOpen || isActive) &&
            "bg-accent text-primary ring-1 ring-primary/40",
        )}
      >
        <Icon className="h-3.5 w-3.5 shrink-0" />
        {hasBadge ? (
          <span className="max-w-full truncate px-0.5 text-[8px] font-medium leading-none tabular-nums">
            {badgeLabel}
          </span>
        ) : null}
      </button>
      {showMenu && (
        <button
          type="button"
          title="Más herramientas y favoritos"
          aria-label="Más herramientas y favoritos"
          onPointerDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onOpenMenu();
          }}
          className={cn(
            "absolute bottom-0 right-0 z-10 flex h-3 w-3 items-center justify-center rounded-tl-sm border border-border/60 bg-card/95 text-muted-foreground shadow-sm hover:bg-accent hover:text-foreground",
            isMenuOpen && "bg-accent text-primary",
          )}
        >
          <ChevronDown className="h-2 w-2" strokeWidth={3} />
        </button>
      )}
    </div>
  );
}

function GroupRailButton({
  groupId,
  groupLabel,
  fallbackIcon: FallbackIcon,
  activeTool,
  lastByGroup,
  favorites,
  isOpen,
  showMenu,
  containerRef,
  onActivate,
  onOpenMenu,
}: {
  groupId: DrawingToolGroupId;
  groupLabel: string;
  fallbackIcon: React.ComponentType<{ className?: string }>;
  activeTool: ChartDrawTool;
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
  favorites: ChartDrawTool[];
  isOpen: boolean;
  showMenu: boolean;
  containerRef: (el: HTMLDivElement | null) => void;
  onActivate: () => void;
  onOpenMenu: () => void;
}) {
  const displayTool = groupButtonIconTool(
    groupId,
    activeTool,
    lastByGroup,
    favorites,
  );
  const displayDef = displayTool
    ? findDrawingToolDefinition(displayTool)
    : undefined;
  const Icon = displayDef?.icon ?? FallbackIcon;
  const isActive = isGroupRailToolActive(groupId, activeTool, favorites);
  const badgeLabel =
    isActive && toolBelongsToGroup(activeTool, groupId)
      ? findDrawingToolDefinition(activeTool)?.shortLabel
      : undefined;

  return (
    <ToolRailButton
      title={displayDef ? `${groupLabel}: ${displayDef.label}` : groupLabel}
      icon={Icon}
      badgeLabel={badgeLabel}
      isActive={isActive}
      isMenuOpen={isOpen}
      showMenu={showMenu}
      containerRef={containerRef}
      onActivate={onActivate}
      onOpenMenu={onOpenMenu}
    />
  );
}

function FamilyRailBlock({
  block,
  activeTool,
  lastByGroup,
  favorites,
  isFlyoutOpenFor,
  railBtnRefs,
  onActivateGroup,
  onPickTool,
  onToggleGroupMenu,
}: {
  block: DrawingRailFamilyBlock;
  activeTool: ChartDrawTool;
  lastByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
  favorites: ChartDrawTool[];
  isFlyoutOpenFor: (groupId: DrawingToolGroupId, anchorKey: string) => boolean;
  railBtnRefs: React.MutableRefObject<
    Partial<Record<string, HTMLDivElement | null>>
  >;
  onActivateGroup: (groupId: DrawingToolGroupId) => void;
  onPickTool: (tool: ChartDrawTool) => void;
  onToggleGroupMenu: (groupId: DrawingToolGroupId, anchorKey: string) => void;
}) {
  const group = DRAWING_TOOL_GROUPS.find((g) => g.id === block.groupId);
  if (!group) return null;

  const primaryAnchorKey = block.groupId;

  const slots = (
    <>
      <GroupRailButton
        groupId={block.groupId}
        groupLabel={group.label}
        fallbackIcon={group.icon}
        activeTool={activeTool}
        lastByGroup={lastByGroup}
        favorites={favorites}
        showMenu={block.showMenu}
        isOpen={isFlyoutOpenFor(block.groupId, primaryAnchorKey)}
        containerRef={(el) => {
          railBtnRefs.current[primaryAnchorKey] = el;
        }}
        onActivate={() => onActivateGroup(block.groupId)}
        onOpenMenu={() => onToggleGroupMenu(block.groupId, primaryAnchorKey)}
      />
      {block.extraTools.map((favoriteTool) => {
        const def = findDrawingToolDefinition(favoriteTool);
        if (!def) return null;
        const anchorKey = `fav-${favoriteTool}`;

        return (
          <ToolRailButton
            key={favoriteTool}
            title={def.label}
            icon={def.icon}
            badgeLabel={
              activeTool === favoriteTool ? def.shortLabel : undefined
            }
            isActive={activeTool === favoriteTool}
            isMenuOpen={isFlyoutOpenFor(block.groupId, anchorKey)}
            showMenu={block.showMenu}
            containerRef={(el) => {
              railBtnRefs.current[anchorKey] = el;
            }}
            onActivate={() => onPickTool(favoriteTool)}
            onOpenMenu={() => onToggleGroupMenu(block.groupId, anchorKey)}
          />
        );
      })}
    </>
  );

  if (!block.bracketed) {
    return (
      <div key={block.groupId} className="flex flex-col items-center">
        {slots}
      </div>
    );
  }

  return (
    <div
      key={block.groupId}
      className="chart-drawing-family-group my-1 flex w-full flex-col items-center gap-0.5 py-1"
      title={group.label}
    >
      <RailSeparator strong />
      <div className="flex flex-col items-center gap-0.5">{slots}</div>
      <RailSeparator strong />
    </div>
  );
}

export function ChartDrawingSidebar({ chartId }: { chartId: string }) {
  const tool = useUiStore((s) => s.chartDrawTool);
  const setTool = useUiStore((s) => s.setChartDrawTool);
  const lastByGroup = useUiStore((s) => s.lastDrawToolByGroup);
  const selectedId = useUiStore((s) => s.selectedDrawingId);
  const setSelectedId = useUiStore((s) => s.setSelectedDrawingId);
  const removeDrawing = useWorkspaceStore((s) => s.removeChartDrawing);
  const clearDrawings = useWorkspaceStore((s) => s.clearChartDrawings);
  const openTemplates = useUiStore((s) => s.openDrawingTemplates);
  const toggleLayerHidden = useWorkspaceStore(
    (s) => s.toggleChartDrawingsLayerHidden,
  );
  const toggleLayerLocked = useWorkspaceStore(
    (s) => s.toggleChartDrawingsLayerLocked,
  );
  const updateChartConfig = useWorkspaceStore((s) => s.updateChartConfig);

  const activeTab = useWorkspaceStore((s) =>
    s.workspace.charts.find((t) => t.id === chartId),
  );
  const chartConfig = activeTab?.chart;
  const layerHidden = activeTab?.drawingsLayerHidden === true;
  const layerLocked = activeTab?.drawingsLayerLocked === true;
  const magnetOn = chartConfig?.cursor.mode === "magnet";

  const activeTemplateId = useWorkspaceStore(
    (s) => s.workspace.activeDrawingTemplateByTool?.[tool],
  );
  const activeTemplateName = useWorkspaceStore((s) =>
    activeTemplateId
      ? s.workspace.drawingTemplates?.find((t) => t.id === activeTemplateId)
          ?.name
      : undefined,
  );
  const drawingCount = activeTab?.drawings.length ?? 0;

  const { favorites, toggleFavorite, isFavorite } = useDrawToolFavorites();
  const familyBlocks = useMemo(
    () => drawingRailFamilyBlocks(favorites),
    [favorites],
  );
  const cursorBlock = familyBlocks.find((block) => block.groupId === "cursor");
  const toolFamilyBlocks = familyBlocks.filter(
    (block) => block.groupId !== "cursor",
  );

  const [openFlyout, setOpenFlyout] = useState<{
    groupId: DrawingToolGroupId;
    anchorKey: string;
  } | null>(null);
  const [flyoutPos, setFlyoutPos] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const flyoutRef = useRef<HTMLDivElement>(null);
  const railBtnRefs = useRef<Partial<Record<string, HTMLDivElement | null>>>(
    {},
  );

  const closeFlyout = () => setOpenFlyout(null);

  useEffect(() => {
    if (!openFlyout) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeFlyout();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [openFlyout]);

  useEffect(() => {
    if (!openFlyout) return;
    const reposition = () => {
      const anchor = railBtnRefs.current[openFlyout.anchorKey];
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      setFlyoutPos({ top: rect.top, left: rect.right + 4 });
    };
    reposition();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [openFlyout]);
  const pickTool = (id: ChartDrawTool) => {
    setTool(id);
    closeFlyout();
  };
  const positionFlyout = (anchorKey: string) => {
    const anchor = railBtnRefs.current[anchorKey];
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    setFlyoutPos({ top: rect.top, left: rect.right + 4 });
  };

  const isFlyoutOpenFor = (groupId: DrawingToolGroupId, anchorKey: string) =>
    openFlyout?.groupId === groupId && openFlyout?.anchorKey === anchorKey;

  const activateGroupTool = (groupId: DrawingToolGroupId) => {
    const nextTool =
      resolveGroupRailActivateTool(groupId, lastByGroup, favorites) ??
      (availableToolsInGroup(groupId)[0]?.id as ChartDrawTool | undefined);
    if (nextTool) {
      setTool(nextTool);
    }
    closeFlyout();
  };

  const toggleGroupMenu = (groupId: DrawingToolGroupId, anchorKey: string) => {
    if (availableToolsInGroup(groupId).length <= 1) return;
    if (openFlyout?.groupId === groupId && openFlyout.anchorKey === anchorKey) {
      closeFlyout();
      return;
    }
    positionFlyout(anchorKey);
    setOpenFlyout({ groupId, anchorKey });
  };
  const familyBlockProps = {
    activeTool: tool,
    lastByGroup,
    favorites,
    isFlyoutOpenFor,
    railBtnRefs,
    onActivateGroup: activateGroupTool,
    onPickTool: pickTool,
    onToggleGroupMenu: toggleGroupMenu,
  };

  return (
    <div
      ref={rootRef}
      className="chart-drawing-sidebar relative z-40 flex shrink-0"
    >
      <aside
        className={cn(
          "chart-drawing-sidebar-rail flex w-9 flex-col items-center gap-1 border-r border-border bg-card/40 py-1 sm:w-10",
          openFlyout && "relative z-[202]",
        )}
      >
        {cursorBlock && (
          <FamilyRailBlock block={cursorBlock} {...familyBlockProps} />
        )}

        <div className="flex min-h-0 flex-1 flex-col items-center gap-1 overflow-y-auto overflow-x-hidden px-0.5">
          {toolFamilyBlocks.map((block) => (
            <FamilyRailBlock
              key={block.groupId}
              block={block}
              {...familyBlockProps}
            />
          ))}
        </div>

        <RailSeparator strong />

        <ChartDrawingGlobalToggles
          magnetOn={magnetOn}
          onMagnetToggle={() =>
            updateChartConfig({
              chartId,
              cursor: { mode: magnetOn ? "crosshair" : "magnet" },
            })
          }
          drawingsHidden={layerHidden}
          onDrawingsHiddenToggle={() => toggleLayerHidden(chartId)}
          drawingsLocked={layerLocked}
          onDrawingsLockedToggle={() => toggleLayerLocked(chartId)}
        />

        <RailSeparator strong />

        <button
          type="button"
          title={
            activeTemplateName
              ? `Plantilla: ${activeTemplateName}`
              : "Plantillas gráficas"
          }
          onClick={openTemplates}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-accent",
            activeTemplateName && "text-primary ring-1 ring-primary/40",
          )}
        >
          <LayoutTemplate className="h-3.5 w-3.5" />
        </button>

        <button
          type="button"
          title="Borrar seleccionado"
          disabled={!selectedId}
          onClick={() => {
            if (!selectedId) return;
            removeDrawing(selectedId, chartId);
            setSelectedId(null);
          }}
          className="flex h-7 w-7 items-center justify-center rounded hover:bg-accent disabled:opacity-30"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          title="Limpiar todos los dibujos"
          disabled={drawingCount === 0}
          onClick={() => {
            if (!window.confirm("¿Eliminar todos los dibujos de esta pestaña?"))
              return;
            clearDrawings(chartId);
            setSelectedId(null);
          }}
          className="flex h-7 w-7 items-center justify-center rounded hover:bg-accent disabled:opacity-30"
        >
          <Eraser className="h-3.5 w-3.5" />
        </button>
      </aside>
      {isShapeDrawTool(tool) && !openFlyout && (
        <div className="absolute left-9 top-1 z-20 sm:left-10">
          <ChartDrawToolStyleBar tool={tool} />
        </div>
      )}
      {openFlyout && flyoutPos && (
        <DrawingToolFlyout
          openGroup={openFlyout.groupId}
          flyoutPos={flyoutPos}
          tool={tool}
          flyoutRef={flyoutRef}
          onClose={closeFlyout}
          pickTool={pickTool}
          isFavorite={isFavorite}
          toggleFavorite={toggleFavorite}
        />
      )}{" "}
    </div>
  );
}
