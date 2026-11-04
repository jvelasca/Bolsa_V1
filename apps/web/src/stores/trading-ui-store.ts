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
  /**
   * Lado sugerido al abrir el diálogo (botones V/C del gráfico). No pre-arma la
   * confirmación: solo orienta y enfoca el botón correcto.
   */
  orderSideHint: "buy" | "sell" | null;
  infoInstrument: InstrumentWithMetaDto | null;
  toggleExpanded: (instrumentId: string) => void;
  isExpanded: (instrumentId: string) => boolean;
  openOrderDialog: (
    instrument: InstrumentWithMetaDto,
    preset?: OrderDialogPreset | null,
    sideHint?: "buy" | "sell" | null,
  ) => void;
  closeOrderDialog: () => void;
  openInfoDialog: (instrument: InstrumentWithMetaDto) => void;
  closeInfoDialog: () => void;
}

export const useTradingUiStore = create<TradingUiState>((set, get) => ({
  expandedInstrumentIds: {},
  orderInstrument: null,
  orderPreset: null,
  orderSideHint: null,
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

  openOrderDialog: (instrument, preset = null, sideHint = null) =>
    set({
      orderInstrument: instrument,
      orderPreset: preset,
      orderSideHint: sideHint ?? preset?.side ?? null,
    }),
  closeOrderDialog: () =>
    set({ orderInstrument: null, orderPreset: null, orderSideHint: null }),
  openInfoDialog: (instrument) => set({ infoInstrument: instrument }),
  closeInfoDialog: () => set({ infoInstrument: null }),
}));
