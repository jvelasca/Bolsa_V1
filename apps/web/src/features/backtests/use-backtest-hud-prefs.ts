import { useCallback, useState } from 'react';
import {
  BACKTEST_CURSOR_FIELD_OPTIONS,
  BACKTEST_GLOBAL_FIELD_OPTIONS,
  BACKTEST_TEMPORAL_FIELD_OPTIONS,
  loadBacktestHudPrefs,
  saveBacktestHudPrefs,
  toggleFavoriteInList,
  type BacktestCursorFieldId,
  type BacktestCursorPanelPos,
  type BacktestGlobalFieldId,
  type BacktestHudPrefs,
  type BacktestTemporalFieldId,
} from '@/features/backtests/backtest-hud-prefs';

export function useBacktestHudPrefs() {
  const [prefs, setPrefs] = useState<BacktestHudPrefs>(() => loadBacktestHudPrefs());

  const commit = useCallback((updater: (current: BacktestHudPrefs) => BacktestHudPrefs) => {
    setPrefs((current) => {
      const next = updater(current);
      saveBacktestHudPrefs(next);
      return next;
    });
  }, []);

  const toggleGlobalFavorite = useCallback(
    (id: BacktestGlobalFieldId) => {
      commit((current) => ({
        ...current,
        globalFavorites: toggleFavoriteInList(
          current.globalFavorites,
          id,
          BACKTEST_GLOBAL_FIELD_OPTIONS,
        ),
      }));
    },
    [commit],
  );

  const toggleTemporalFavorite = useCallback(
    (id: BacktestTemporalFieldId) => {
      commit((current) => ({
        ...current,
        temporalFavorites: toggleFavoriteInList(
          current.temporalFavorites,
          id,
          BACKTEST_TEMPORAL_FIELD_OPTIONS,
        ),
      }));
    },
    [commit],
  );

  const toggleCursorFavorite = useCallback(
    (id: BacktestCursorFieldId) => {
      commit((current) => ({
        ...current,
        cursorFavorites: toggleFavoriteInList(
          current.cursorFavorites,
          id,
          BACKTEST_CURSOR_FIELD_OPTIONS,
        ),
      }));
    },
    [commit],
  );

  const setCursorPanelPos = useCallback(
    (cursorPanelPos: BacktestCursorPanelPos) => {
      commit((current) => ({ ...current, cursorPanelPos }));
    },
    [commit],
  );

  return {
    prefs,
    toggleGlobalFavorite,
    toggleTemporalFavorite,
    toggleCursorFavorite,
    setCursorPanelPos,
  };
}
