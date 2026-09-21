/**
 * V2.47 — utilidad de test del primer slice móvil de la cabina.
 *
 * jsdom no implementa `matchMedia` (`typeof === "undefined"`), así que los tests
 * no pueden distinguir ancho de estrecho sin un stub. `vitest.setup.ts` instala por
 * defecto un viewport de ESCRITORIO (para que los tests existentes sigan ejerciendo
 * el layout de siempre) y aquí se ofrece el cambio explícito a teléfono, con el
 * mismo parser de `min-width`/`max-width` en ambos sitios.
 */

import { vi } from "vitest";

export const DESKTOP_VIEWPORT_PX = 1280;
export const PHONE_VIEWPORT_PX = 390;

/** Interpreta consultas `min-width` / `max-width` contra un ancho de viewport. */
export function matchesViewport(query: string, widthPx: number): boolean {
  const min = /\(min-width:\s*(\d+(?:\.\d+)?)px\)/.exec(query);
  if (min) return widthPx >= Number(min[1]);
  const max = /\(max-width:\s*(\d+(?:\.\d+)?)px\)/.exec(query);
  if (max) return widthPx <= Number(max[1]);
  // Otras features (prefers-color-scheme, prefers-reduced-motion…) → sin preferencia.
  return false;
}

/** Instala un `matchMedia` que responde como un viewport de `widthPx`. */
export function stubViewportWidth(widthPx: number): void {
  vi.stubGlobal("matchMedia", (query: string) => {
    const matches = matchesViewport(query, widthPx);
    return {
      matches,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    };
  });
}

/** Teléfono (por debajo del `sm` de Tailwind). */
export function stubNarrowViewport(): void {
  stubViewportWidth(PHONE_VIEWPORT_PX);
}

/** Escritorio. */
export function stubWideViewport(): void {
  stubViewportWidth(DESKTOP_VIEWPORT_PX);
}
