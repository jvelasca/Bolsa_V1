import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ActiveAccountState {
  activeAccountId: string | null;
  setActiveAccountId: (id: string | null) => void;
}

export const useActiveAccountStore = create<ActiveAccountState>()(
  persist(
    (set) => ({
      activeAccountId: null,
      setActiveAccountId: (id) => set({ activeAccountId: id }),
    }),
    { name: "bolsa-active-account" },
  ),
);

export function getActiveAccountId(): string | null {
  return useActiveAccountStore.getState().activeAccountId;
}

export function useActiveAccountQueryKey(): string | null {
  return useActiveAccountStore((s) => s.activeAccountId);
}
