/**
 * Guarda de reentrada para el flush de cierre de página.
 *
 * `beforeunload` y `pagehide` disparan AMBOS al cerrar una pestaña en Chromium, así
 * que registrar el mismo handler en los dos ejecutaba el flush dos veces: dos
 * `POST /charts/close` y dos PUT keepalive con el mismo documento. El segundo podía
 * llegar con una revisión ya movida por el primero.
 *
 * `reset()` se llama cuando la página vuelve a estar visible (`pageshow` /
 * `visibilitychange`), de modo que un cierre posterior sí se envía.
 */
export interface UnloadFlushGuard {
  run: () => void;
  reset: () => void;
}

export function createUnloadFlushGuard(flush: () => void): UnloadFlushGuard {
  let flushed = false;
  return {
    run: () => {
      if (flushed) return;
      flushed = true;
      flush();
    },
    reset: () => {
      flushed = false;
    },
  };
}
