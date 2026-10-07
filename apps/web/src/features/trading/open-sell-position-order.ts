/**
 * V2.88.85+ (H1 UX) — abrir el flujo Vender canónico (OrderDialog) para una posición.
 *
 * Se usa desde la CTA de salida de una posición ``HUMAN_MANUAL`` con el libro en
 * MANUAL: el backend ya autoriza esa venta por HTTP (``row_is_human_manual``) y aquí
 * se enruta la superficie de posición al mismo canal Vender que la ficha/el diálogo,
 * sin inventar un bypass. No ejecuta nada: abre el diálogo con la firma humana
 * pre-armada (Confirm), igual que el resto de la vía manual.
 */

import type {
  InstrumentListMetaDto,
  InstrumentWithMetaDto,
  SyncStatus,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/query-client";
import { useTradingUiStore } from "@/stores/trading-ui-store";

export async function openSellOrderForPosition(opts: {
  instrumentId: string;
  quantity: number;
  /** Precio de marca de la posición (fallback si el instrumento no trae lastClose). */
  lastPrice?: number | null;
}): Promise<void> {
  const { instrumentId, quantity, lastPrice } = opts;
  const qty = Math.floor(quantity);
  if (!instrumentId || !(qty > 0)) {
    throw new Error(
      "No se pudo preparar la venta: instrumento o cantidad inválidos.",
    );
  }

  // Reusa el caché del cockpit si ya se cargó el instrumento (queryKey canónica).
  const res = await queryClient.fetchQuery({
    queryKey: ["instrument", instrumentId],
    queryFn: () => api.getInstrument(instrumentId),
  });
  const data = res?.data;
  if (!data) {
    throw new Error("No se pudo cargar el instrumento para vender.");
  }

  const priceSummary = res.meta?.priceSummary ?? null;
  const rawLastSync = res.meta?.lastSync ?? null;
  const meta: InstrumentListMetaDto = {
    barCount: priceSummary?.barCount ?? 0,
    lastSync: rawLastSync
      ? {
          status: rawLastSync.status as SyncStatus,
          syncedAt: rawLastSync.syncedAt,
          error: rawLastSync.error,
        }
      : null,
    lastClose: priceSummary?.lastClose ?? lastPrice ?? null,
    changePct: priceSummary?.changePct ?? null,
  };

  const instrument: InstrumentWithMetaDto = { ...data, meta };
  useTradingUiStore.getState().openOrderDialog(instrument, {
    side: "sell",
    quantity: qty,
  });
}
