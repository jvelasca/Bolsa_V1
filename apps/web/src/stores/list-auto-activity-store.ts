/**
 * Actividad global de Lista AUTO — sobrevive a salir de /backtests (keep-alive)
 * y alimenta la barra de estado de Trading / badge nav.
 */

import { create } from "zustand";
import { formatListAutoStatusBarSummary } from "@/features/backtests/backtest-list-auto";

export type ListAutoActivitySnapshot = {
  active: boolean;
  paused: boolean;
  listId: string | null;
  listName: string | null;
  index: number;
  total: number;
  symbol: string;
  /** Mensaje largo del rail (fase). */
  detail: string | null;
};

type ListAutoActivityState = ListAutoActivitySnapshot & {
  /** Línea corta para footer Trading. */
  summary: string | null;
  publish: (
    snap: Omit<ListAutoActivitySnapshot, "active"> & { active?: boolean },
  ) => void;
  clear: () => void;
};

const EMPTY: ListAutoActivitySnapshot = {
  active: false,
  paused: false,
  listId: null,
  listName: null,
  index: 0,
  total: 0,
  symbol: "",
  detail: null,
};

export const useListAutoActivityStore = create<ListAutoActivityState>(
  (set) => ({
    ...EMPTY,
    summary: null,
    publish: (snap) => {
      const active = snap.active ?? true;
      const next: ListAutoActivitySnapshot = {
        active,
        paused: snap.paused,
        listId: snap.listId,
        listName: snap.listName,
        index: snap.index,
        total: snap.total,
        symbol: snap.symbol,
        detail: snap.detail,
      };
      set({
        ...next,
        summary: active
          ? formatListAutoStatusBarSummary({
              index: next.index,
              total: next.total,
              symbol: next.symbol,
              paused: next.paused,
              detail: next.detail,
              listName: next.listName,
            })
          : null,
      });
    },
    clear: () => set({ ...EMPTY, summary: null }),
  }),
);
