/**
 * Fase 4 del bloque crítico de /mercado/operativa — acciones del panel DECISIÓN.
 *
 * - `refreshStudy`: actualiza el estudio del instrumento, con error visible (`pushToast`)
 *   en vez de una promesa rechazada silenciosa.
 * - `addToEstudio`: alta en Estudio con `try/catch`, toast de error y guarda síncrona
 *   (`useRef`) para que un doble clic no dispare dos altas.
 *
 * La guarda vive en el hook (no en el botón) porque el alta tarda: entre el 1.er clic y
 * el re-render con `disabled` ya podría entrar el 2.º.
 */

import { useCallback, useRef, useState } from "react";

export type EstudioMemberLite = {
  instrumentId: string;
  symbol: string;
  name: string;
};

function errorMessage(e: unknown): string {
  return e instanceof Error && e.message.trim()
    ? e.message
    : "error desconocido";
}

export function useRefreshStudyAction(input: {
  instrumentId: string | null;
  symbol: string;
  pushToast: (message: string) => void;
  /** Invalida las queries de estudios (p. ej. `["decision-studies"]`). */
  invalidate: () => Promise<unknown>;
  /** Relee el TOP del estudio (opcional en tests). */
  refetch?: () => Promise<unknown>;
}): { refreshPending: boolean; refreshStudy: () => void } {
  const { instrumentId, symbol, pushToast, invalidate, refetch } = input;
  const [refreshPending, setRefreshPending] = useState(false);
  const inFlight = useRef(false);

  const refreshStudy = useCallback(() => {
    if (!instrumentId || inFlight.current) return;
    inFlight.current = true;
    setRefreshPending(true);
    void (async () => {
      try {
        const { runEstudioInstrumentsUpdate } = await import(
          "@/features/trading/estudio-instruments-update"
        );
        await runEstudioInstrumentsUpdate({
          instrumentIds: [instrumentId],
          rediscover: false,
          phaseLabel: "Actualizar",
          symbolOf: () => symbol,
        });
        await invalidate();
        await refetch?.();
      } catch (e) {
        pushToast(
          `${symbol} · no se pudo actualizar el estudio: ${errorMessage(e)}`,
        );
      } finally {
        inFlight.current = false;
        setRefreshPending(false);
      }
    })();
  }, [instrumentId, invalidate, pushToast, refetch, symbol]);

  return { refreshPending, refreshStudy };
}

export function useAddToEstudioAction(input: {
  instrumentId: string | null;
  symbol: string;
  pushToast: (message: string) => void;
  upsertMembers: (members: EstudioMemberLite[]) => void;
}): { addToEstudioPending: boolean; addToEstudio: () => void } {
  const { instrumentId, symbol, pushToast, upsertMembers } = input;
  const [addToEstudioPending, setAddToEstudioPending] = useState(false);
  const inFlight = useRef(false);

  const addToEstudio = useCallback(() => {
    if (!instrumentId || inFlight.current) return;
    inFlight.current = true;
    setAddToEstudioPending(true);
    void (async () => {
      try {
        const { addToEstudioMembership } = await import(
          "@/features/trading/estudio-membership"
        );
        const { added, ids } = await addToEstudioMembership([
          { instrumentId, symbol, name: symbol },
        ]);
        if (added <= 0) return;
        upsertMembers([{ instrumentId, symbol, name: symbol }]);
        pushToast(`${symbol} → Estudio · actualizando…`);
        const { runEstudioInstrumentsUpdate } = await import(
          "@/features/trading/estudio-instruments-update"
        );
        await runEstudioInstrumentsUpdate({
          instrumentIds: ids,
          rediscover: false,
          phaseLabel: "Alta Estudio",
          symbolOf: () => symbol,
        });
        pushToast(`${symbol} → Estudio · datos al día`);
      } catch (e) {
        pushToast(
          `${symbol} · no se pudo dar de alta en Estudio: ${errorMessage(e)}`,
        );
      } finally {
        inFlight.current = false;
        setAddToEstudioPending(false);
      }
    })();
  }, [instrumentId, pushToast, symbol, upsertMembers]);

  return { addToEstudioPending, addToEstudio };
}
