/**
 * Constantes y aliases de tipo del Hub Backtesting (`/backtests`).
 *
 * Extraído de `backtests-page.tsx` (Track B B1) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 */

import { BACKTEST_STRATEGIES, type BacktestStrategyType } from "@bolsa/shared";

export type {
  HubTab,
  ResultFocus,
  RunSource,
  UniverseMode,
} from "@/features/backtests/backtest-hub-nav";
export type { StrategiesListFilter } from "@/features/backtests/library-strategy-buckets";

export const STRATEGY_OPTIONS = Object.entries(BACKTEST_STRATEGIES) as [
  BacktestStrategyType,
  { label: string; description: string },
][];
