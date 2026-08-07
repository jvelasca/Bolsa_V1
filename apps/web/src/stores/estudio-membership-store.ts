/**
 * Cache local de membresía Estudio (lista API canónica ADR-024).
 * Separado de `visualization-store` (= lista virtual Visualizados / pestañas).
 */

import { create } from 'zustand';

export type EstudioMemberEntry = {
  instrumentId: string;
  symbol: string;
  name: string;
};

type EstudioMembershipState = {
  members: EstudioMemberEntry[];
  replaceMembers: (members: EstudioMemberEntry[]) => void;
  upsertMembers: (members: EstudioMemberEntry[]) => void;
  removeIds: (instrumentIds: ReadonlyArray<string>) => void;
  contains: (instrumentId: string) => boolean;
  ids: () => string[];
};

export const useEstudioMembershipStore = create<EstudioMembershipState>()((set, get) => ({
  members: [],

  replaceMembers: (members) => set({ members: [...members] }),

  upsertMembers: (incoming) =>
    set((state) => {
      const byId = new Map(state.members.map((m) => [m.instrumentId, m]));
      for (const m of incoming) {
        byId.set(m.instrumentId, m);
      }
      return { members: [...byId.values()] };
    }),

  removeIds: (instrumentIds) => {
    const remove = new Set(instrumentIds);
    set((state) => ({
      members: state.members.filter((m) => !remove.has(m.instrumentId)),
    }));
  },

  contains: (instrumentId) =>
    get().members.some((m) => m.instrumentId === instrumentId),

  ids: () => get().members.map((m) => m.instrumentId),
}));
