import { createRandomId } from "@bolsa/shared";
import { create } from "zustand";

export interface AlertToast {
  id: string;
  message: string;
  /** Acción opcional (p.ej. abrir Ayuda · Monitor tras CORE-R). */
  action?: AlertToastAction | null;
}

export type AlertToastAction =
  | {
      type: "open_help_backtesting_monitor";
      label?: string;
    }
  | {
      type: "open_asesor_opiniones";
      label?: string;
    }
  | {
      type: "open_trading_instrument";
      instrumentId: string;
      symbol: string;
      label?: string;
    }
  | {
      type: "open_confirm_drawer";
      label?: string;
    };

interface AlertsState {
  toasts: AlertToast[];
  pushToast: (
    message: string,
    opts?: { action?: AlertToastAction | null },
  ) => void;
  dismissToast: (id: string) => void;
}

export const useAlertsStore = create<AlertsState>((set) => ({
  toasts: [],
  pushToast: (message, opts) =>
    set((state) => ({
      toasts: [
        ...state.toasts,
        {
          id: createRandomId(),
          message,
          action: opts?.action ?? null,
        },
      ],
    })),
  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    })),
}));
