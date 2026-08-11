import type {
  InstrumentWithMetaDto,
  VisualizationPersistedEntry,
} from "@bolsa/shared";
import { createRandomId } from "@bolsa/shared";
import { create } from "zustand";
export type VisualizationViewSource = "search" | "list" | "import";

export type VisualizationSessionEntry = VisualizationPersistedEntry;

export interface VisualizationLogEntry {
  id: string;
  instrumentId: string;
  symbol: string;
  name: string;
  viewedAt: string;
  searchQuery?: string;
  source: VisualizationViewSource;
}

interface VisualizationState {
  entries: VisualizationSessionEntry[];
  log: VisualizationLogEntry[];
  addInstrument: (
    instrument: InstrumentWithMetaDto,
    options?: { searchQuery?: string; source?: VisualizationViewSource },
  ) => void;
  removeInstrument: (instrumentId: string) => void;
  contains: (instrumentId: string) => boolean;
  replaceEntries: (entries: VisualizationSessionEntry[]) => void;
  clearSession: () => void;
}

export const useVisualizationStore = create<VisualizationState>()(
  (set, get) => ({
    entries: [],
    log: [],

    addInstrument: (instrument, options) => {
      const now = new Date().toISOString();
      const source = options?.source ?? "search";
      const searchQuery = options?.searchQuery?.trim() || undefined;

      set((state) => {
        const existing = state.entries.find(
          (entry) => entry.instrumentId === instrument.id,
        );
        const logEntry: VisualizationLogEntry = {
          id: createRandomId(),
          instrumentId: instrument.id,
          symbol: instrument.symbol,
          name: instrument.name,
          viewedAt: now,
          searchQuery,
          source,
        };

        if (existing) {
          const updated: VisualizationSessionEntry = {
            ...existing,
            symbol: instrument.symbol,
            name: instrument.name,
            lastViewedAt: now,
            viewCount: existing.viewCount + 1,
            lastSearchQuery: searchQuery ?? existing.lastSearchQuery,
          };
          const rest = state.entries.filter(
            (entry) => entry.instrumentId !== instrument.id,
          );
          return {
            entries: [updated, ...rest],
            log: [logEntry, ...state.log],
          };
        }

        const created: VisualizationSessionEntry = {
          instrumentId: instrument.id,
          symbol: instrument.symbol,
          name: instrument.name,
          firstViewedAt: now,
          lastViewedAt: now,
          viewCount: 1,
          lastSearchQuery: searchQuery,
        };

        return {
          entries: [created, ...state.entries],
          log: [logEntry, ...state.log],
        };
      });
    },

    removeInstrument: (instrumentId) =>
      set((state) => ({
        entries: state.entries.filter(
          (entry) => entry.instrumentId !== instrumentId,
        ),
      })),

    contains: (instrumentId) =>
      get().entries.some((entry) => entry.instrumentId === instrumentId),

    replaceEntries: (entries) => set({ entries }),

    clearSession: () => set({ entries: [], log: [] }),
  }),
);

export function clearVisualizationSession() {
  useVisualizationStore.getState().clearSession();
}
