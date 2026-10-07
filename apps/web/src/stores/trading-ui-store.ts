import type { InstrumentWithMetaDto } from "@bolsa/shared";
import { create } from "zustand";

export type { PendingOrder } from "@/features/trading/use-pending-orders";

/**
 * V2.88.85+ (H1 UX) — preset opcional al abrir el diálogo de orden.
 * Permite que la CTA de salida MANUAL aterrice en el flujo Vender canónico
 * con la cantidad de desriesgo ya precargada.
 */
export interface OrderDialogPreset {
  side: "buy" | "sell";
  quantity: number;
}

interface TradingUiState {
  expandedInstrumentIds: Record<string, boolean>;
  orderInstrument: InstrumentWithMetaDto | null;
  orderPreset: OrderDialogPreset | null;
  infoInstrument: InstrumentWithMetaDto | null;
  toggleExpanded: (instrumentId: string) => void;
  isExpanded: (instrumentId: string) => boolean;
  openOrderDialog: (
    instrument: InstrumentWithMetaDto,
    preset?: OrderDialogPreset | null,
  ) => void;
  closeOrderDialog: () => void;
  openInfoDialog: (instrument: InstrumentWithMetaDto) => void;
  closeInfoDialog: () => void;
}

export const useTradingUiStore = create<TradingUiState>((set, get) => ({
  expandedInstrumentIds: {},
  orderInstrument: null,
  orderPreset: null,
  infoInstrument: null,

  toggleExpanded: (instrumentId) =>
    set((state) => ({
      expandedInstrumentIds: {
        ...state.expandedInstrumentIds,
        [instrumentId]: !state.expandedInstrumentIds[instrumentId],
      },
    })),

  isExpanded: (instrumentId) =>
    Boolean(get().expandedInstrumentIds[instrumentId]),

  openOrderDialog: (instrument, preset = null) =>
    set({ orderInstrument: instrument, orderPreset: preset }),
  closeOrderDialog: () => set({ orderInstrument: null, orderPreset: null }),
  openInfoDialog: (instrument) => set({ infoInstrument: instrument }),
  closeInfoDialog: () => set({ infoInstrument: null }),
}));
