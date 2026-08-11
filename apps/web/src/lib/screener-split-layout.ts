import type { ScreenerPanelId } from "@/stores/screener-preferences-store";

export const MIN_SCREENER_SIDEBAR_WIDTH_PCT = 20;
export const MAX_SCREENER_SIDEBAR_WIDTH_PCT = 55;
export const DEFAULT_SCREENER_SIDEBAR_WIDTH_PCT = 32;

export const MIN_SCREENER_RUNNER_HEIGHT_PCT = 22;
export const MAX_SCREENER_RUNNER_HEIGHT_PCT = 72;
export const DEFAULT_SCREENER_RUNNER_HEIGHT_PCT = 40;

export const MIN_SCREENER_FOOTER_HEIGHT_PCT = 12;
export const MAX_SCREENER_FOOTER_HEIGHT_PCT = 48;
export const DEFAULT_SCREENER_FOOTER_HEIGHT_PCT = 24;

export const MIN_SCREENER_SIDEBAR_PANEL_PCT = 10;

export interface ScreenerSplitLayoutPrefs {
  sidebarOpen: boolean;
  sidebarWidthPct: number;
  workflowRunnerPct: number;
  workflowFooterPct: number;
  sidebarPanelSizes: Partial<Record<ScreenerPanelId, number>>;
}

export const DEFAULT_SCREENER_SPLIT_LAYOUT: ScreenerSplitLayoutPrefs = {
  sidebarOpen: true,
  sidebarWidthPct: DEFAULT_SCREENER_SIDEBAR_WIDTH_PCT,
  workflowRunnerPct: DEFAULT_SCREENER_RUNNER_HEIGHT_PCT,
  workflowFooterPct: DEFAULT_SCREENER_FOOTER_HEIGHT_PCT,
  sidebarPanelSizes: {},
};

export function clampScreenerSidebarWidthPct(value: number): number {
  return Math.min(
    MAX_SCREENER_SIDEBAR_WIDTH_PCT,
    Math.max(MIN_SCREENER_SIDEBAR_WIDTH_PCT, value),
  );
}

export function clampScreenerRunnerHeightPct(value: number): number {
  return Math.min(
    MAX_SCREENER_RUNNER_HEIGHT_PCT,
    Math.max(MIN_SCREENER_RUNNER_HEIGHT_PCT, value),
  );
}

export function clampScreenerFooterHeightPct(value: number): number {
  return Math.min(
    MAX_SCREENER_FOOTER_HEIGHT_PCT,
    Math.max(MIN_SCREENER_FOOTER_HEIGHT_PCT, value),
  );
}

export function normalizeSidebarPanelLayout(
  openPanelIds: ScreenerPanelId[],
  stored: Partial<Record<ScreenerPanelId, number>> | undefined,
): Record<string, number> {
  if (openPanelIds.length === 0) return {};
  if (openPanelIds.length === 1) return { [openPanelIds[0]!]: 100 };

  const raw = openPanelIds.map((id) => stored?.[id]);
  const hasStored = raw.some((value) => value != null && value > 0);
  const weights = openPanelIds.map((_id, index) =>
    hasStored && raw[index] != null && raw[index]! > 0
      ? raw[index]!
      : 100 / openPanelIds.length,
  );

  const total = weights.reduce((sum, value) => sum + value, 0);
  const layout: Record<string, number> = {};
  openPanelIds.forEach((id, index) => {
    layout[id] = (weights[index]! / total) * 100;
  });
  return layout;
}

export function mergeSidebarPanelLayout(
  previous: Partial<Record<ScreenerPanelId, number>>,
  nextLayout: Record<string, number>,
): Partial<Record<ScreenerPanelId, number>> {
  return {
    ...previous,
    ...(nextLayout as Partial<Record<ScreenerPanelId, number>>),
  };
}
