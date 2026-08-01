import { create } from 'zustand';

interface ScreenerActivityState {
  /** Scan sync en curso (antes de que aparezca en cola BD). */
  syncScanActive: boolean;
  setSyncScanActive: (active: boolean) => void;
}

export const useScreenerActivityStore = create<ScreenerActivityState>((set) => ({
  syncScanActive: false,
  setSyncScanActive: (syncScanActive) => set({ syncScanActive }),
}));
