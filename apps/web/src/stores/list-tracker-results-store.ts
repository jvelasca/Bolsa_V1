import type { ScanRunResultDto } from '@bolsa/shared';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface CachedTrackerResult {
  result: ScanRunResultDto;
  updatedAt: string;
}

interface ListTrackerResultsState {
  byTrackerId: Record<string, CachedTrackerResult>;
  setResult: (trackerId: string, result: ScanRunResultDto) => void;
  getResult: (trackerId: string) => ScanRunResultDto | null;
  removeResult: (trackerId: string) => void;
}

export const useListTrackerResultsStore = create<ListTrackerResultsState>()(
  persist(
    (set, get) => ({
      byTrackerId: {},
      setResult: (trackerId, result) =>
        set((state) => ({
          byTrackerId: {
            ...state.byTrackerId,
            [trackerId]: { result, updatedAt: new Date().toISOString() },
          },
        })),
      getResult: (trackerId) => get().byTrackerId[trackerId]?.result ?? null,
      removeResult: (trackerId) =>
        set((state) => {
          const next = { ...state.byTrackerId };
          delete next[trackerId];
          return { byTrackerId: next };
        }),
    }),
    { name: 'bolsa-list-tracker-results' },
  ),
);
