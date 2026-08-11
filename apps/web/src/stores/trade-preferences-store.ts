import { create } from "zustand";
import { persist } from "zustand/middleware";

interface TradePreferencesState {
  confirmBeforeTrade: boolean;
  setConfirmBeforeTrade: (value: boolean) => void;
}

export const useTradePreferencesStore = create<TradePreferencesState>()(
  persist(
    (set) => ({
      confirmBeforeTrade: true,
      setConfirmBeforeTrade: (value) => set({ confirmBeforeTrade: value }),
    }),
    { name: "bolsa-trade-preferences" },
  ),
);
