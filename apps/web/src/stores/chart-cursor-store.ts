import type { OhlcvBarDto } from '@bolsa/shared';
import { create } from 'zustand';

interface ChartCursorState {
  instrumentId: string | null;
  hoveredBar: OhlcvBarDto | null;
  setHoveredBar: (instrumentId: string, bar: OhlcvBarDto | null) => void;
  clearHoveredBar: (instrumentId?: string) => void;
}

export const useChartCursorStore = create<ChartCursorState>((set) => ({
  instrumentId: null,
  hoveredBar: null,
  setHoveredBar: (instrumentId, bar) =>
    set((state) => {
      if (state.instrumentId === instrumentId && state.hoveredBar === bar) return state;
      return { instrumentId, hoveredBar: bar };
    }),
  clearHoveredBar: (instrumentId) =>
    set((state) => {
      if (instrumentId && state.instrumentId !== instrumentId) return state;
      if (state.instrumentId === null && state.hoveredBar === null) return state;
      return { instrumentId: null, hoveredBar: null };
    }),
}));
