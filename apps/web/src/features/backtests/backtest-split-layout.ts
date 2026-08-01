/** Split prefs for Backtesting hub (wizard ↔ resultado ↔ secciones). */

export const BACKTEST_LAYOUT_STORAGE_KEY = 'bolsa-backtest-layout-v4';

export const MIN_WIZARD_WIDTH_PCT = 18;
export const MAX_WIZARD_WIDTH_PCT = 60;
export const DEFAULT_WIZARD_WIDTH_PCT = 34;

export const MIN_CHART_HEIGHT_PCT = 28;
export const MAX_CHART_HEIGHT_PCT = 88;
export const DEFAULT_CHART_HEIGHT_PCT = 76;

export const MIN_EQUITY_WIDTH_PCT = 25;
export const MAX_EQUITY_WIDTH_PCT = 75;
export const DEFAULT_EQUITY_WIDTH_PCT = 50;

/** Mobile / stacked: wizard height share of the run column. */
export const MIN_WIZARD_STACK_HEIGHT_PCT = 18;
export const MAX_WIZARD_STACK_HEIGHT_PCT = 72;
export const DEFAULT_WIZARD_STACK_HEIGHT_PCT = 38;

/** Result summary / balance block (scrollable). Compact by default — chart first. */
export const MIN_HEADER_HEIGHT_PCT = 8;
export const MAX_HEADER_HEIGHT_PCT = 45;
export const DEFAULT_HEADER_HEIGHT_PCT = 14;

/** When equity/trades stack vertically: equity share of bottom row. */
export const MIN_BOTTOM_EQUITY_HEIGHT_PCT = 25;
export const MAX_BOTTOM_EQUITY_HEIGHT_PCT = 75;
export const DEFAULT_BOTTOM_EQUITY_HEIGHT_PCT = 50;

export type BacktestSplitLayoutPrefs = {
  wizardWidthPct: number;
  wizardStackHeightPct: number;
  /** Share of result body (below header) for the price chart. */
  chartHeightPct: number;
  equityWidthPct: number;
  /** Share of full result column for the balance/summary block. */
  headerHeightPct: number;
  /** Stacked bottom: equity panel height share. */
  bottomEquityHeightPct: number;
};

export const DEFAULT_BACKTEST_SPLIT_LAYOUT: BacktestSplitLayoutPrefs = {
  wizardWidthPct: DEFAULT_WIZARD_WIDTH_PCT,
  wizardStackHeightPct: DEFAULT_WIZARD_STACK_HEIGHT_PCT,
  chartHeightPct: DEFAULT_CHART_HEIGHT_PCT,
  equityWidthPct: DEFAULT_EQUITY_WIDTH_PCT,
  headerHeightPct: DEFAULT_HEADER_HEIGHT_PCT,
  bottomEquityHeightPct: DEFAULT_BOTTOM_EQUITY_HEIGHT_PCT,
};

export function clampWizardWidthPct(value: number): number {
  return Math.min(MAX_WIZARD_WIDTH_PCT, Math.max(MIN_WIZARD_WIDTH_PCT, value));
}

export function clampWizardStackHeightPct(value: number): number {
  return Math.min(MAX_WIZARD_STACK_HEIGHT_PCT, Math.max(MIN_WIZARD_STACK_HEIGHT_PCT, value));
}

export function clampChartHeightPct(value: number): number {
  return Math.min(MAX_CHART_HEIGHT_PCT, Math.max(MIN_CHART_HEIGHT_PCT, value));
}

export function clampEquityWidthPct(value: number): number {
  return Math.min(MAX_EQUITY_WIDTH_PCT, Math.max(MIN_EQUITY_WIDTH_PCT, value));
}

export function clampHeaderHeightPct(value: number): number {
  return Math.min(MAX_HEADER_HEIGHT_PCT, Math.max(MIN_HEADER_HEIGHT_PCT, value));
}

export function clampBottomEquityHeightPct(value: number): number {
  return Math.min(
    MAX_BOTTOM_EQUITY_HEIGHT_PCT,
    Math.max(MIN_BOTTOM_EQUITY_HEIGHT_PCT, value),
  );
}

function migrateFromPrevious(): Partial<BacktestSplitLayoutPrefs> | null {
  try {
    for (const key of [
      'bolsa-backtest-layout-v3',
      'bolsa-backtest-layout-v2',
      'bolsa-backtest-layout-v1',
    ]) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as Partial<BacktestSplitLayoutPrefs>;
      // Prefer new chart-first defaults for header/chart; keep wizard/equity prefs.
      return {
        wizardWidthPct: parsed.wizardWidthPct,
        wizardStackHeightPct: parsed.wizardStackHeightPct,
        equityWidthPct: parsed.equityWidthPct,
        bottomEquityHeightPct: parsed.bottomEquityHeightPct,
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function loadBacktestSplitLayout(): BacktestSplitLayoutPrefs {
  if (typeof window === 'undefined') return DEFAULT_BACKTEST_SPLIT_LAYOUT;
  try {
    const raw = localStorage.getItem(BACKTEST_LAYOUT_STORAGE_KEY);
    const parsed = (raw
      ? (JSON.parse(raw) as Partial<BacktestSplitLayoutPrefs>)
      : migrateFromPrevious()) ?? {};
    return {
      wizardWidthPct: clampWizardWidthPct(
        parsed.wizardWidthPct ?? DEFAULT_WIZARD_WIDTH_PCT,
      ),
      wizardStackHeightPct: clampWizardStackHeightPct(
        parsed.wizardStackHeightPct ?? DEFAULT_WIZARD_STACK_HEIGHT_PCT,
      ),
      chartHeightPct: clampChartHeightPct(
        parsed.chartHeightPct ?? DEFAULT_CHART_HEIGHT_PCT,
      ),
      equityWidthPct: clampEquityWidthPct(
        parsed.equityWidthPct ?? DEFAULT_EQUITY_WIDTH_PCT,
      ),
      headerHeightPct: clampHeaderHeightPct(
        parsed.headerHeightPct ?? DEFAULT_HEADER_HEIGHT_PCT,
      ),
      bottomEquityHeightPct: clampBottomEquityHeightPct(
        parsed.bottomEquityHeightPct ?? DEFAULT_BOTTOM_EQUITY_HEIGHT_PCT,
      ),
    };
  } catch {
    return DEFAULT_BACKTEST_SPLIT_LAYOUT;
  }
}

export function saveBacktestSplitLayout(prefs: BacktestSplitLayoutPrefs): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(BACKTEST_LAYOUT_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore quota */
  }
}

export function pxToPct(px: number, total: number): number {
  return total > 0 ? (px / total) * 100 : 0;
}
