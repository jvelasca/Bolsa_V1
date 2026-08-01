import type { InstrumentWithMetaDto } from '@bolsa/shared';
import { create } from 'zustand';

export type { PendingOrder } from '@/features/trading/use-pending-orders';

interface TradingUiState {
  expandedInstrumentIds: Record<string, boolean>;
  orderInstrument: InstrumentWithMetaDto | null;
  infoInstrument: InstrumentWithMetaDto | null;
  listMembershipInstrument: InstrumentWithMetaDto | null;
  toggleExpanded: (instrumentId: string) => void;
  isExpanded: (instrumentId: string) => boolean;
  openOrderDialog: (instrument: InstrumentWithMetaDto) => void;
  closeOrderDialog: () => void;
  openInfoDialog: (instrument: InstrumentWithMetaDto) => void;
  closeInfoDialog: () => void;
  openListMembershipDialog: (instrument: InstrumentWithMetaDto) => void;
  closeListMembershipDialog: () => void;
}

export const useTradingUiStore = create<TradingUiState>((set, get) => ({
  expandedInstrumentIds: {},
  orderInstrument: null,
  infoInstrument: null,
  listMembershipInstrument: null,

  toggleExpanded: (instrumentId) =>
    set((state) => ({
      expandedInstrumentIds: {
        ...state.expandedInstrumentIds,
        [instrumentId]: !state.expandedInstrumentIds[instrumentId],
      },
    })),

  isExpanded: (instrumentId) => Boolean(get().expandedInstrumentIds[instrumentId]),

  openOrderDialog: (instrument) => set({ orderInstrument: instrument }),
  closeOrderDialog: () => set({ orderInstrument: null }),
  openInfoDialog: (instrument) => set({ infoInstrument: instrument }),
  closeInfoDialog: () => set({ infoInstrument: null }),
  openListMembershipDialog: (instrument) => set({ listMembershipInstrument: instrument }),
  closeListMembershipDialog: () => set({ listMembershipInstrument: null }),
}));
