import type { ChartTimeframe } from './chart-timeframes.js';
import type { IndicatorSpec } from './research-platform.js';
import type { BacktestStrategyType } from './types.js';

/** Draft serializado desde ChartTabState (BT-3b). */
export interface ChartStrategySetupDraft {
  instrumentId: string;
  instrumentLabel: string;
  timeframe: ChartTimeframe;
  indicatorSpecs: IndicatorSpec[];
  indicatorLabels: string[];
  drawingAlertCount: number;
  inferredPresetKey: BacktestStrategyType | null;
  canRunPresetBacktest: boolean;
  warnings: string[];
}
