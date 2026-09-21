import "@testing-library/jest-dom/vitest";
import { matchesViewport, DESKTOP_VIEWPORT_PX } from "./src/lib/test-viewport";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverMock as typeof ResizeObserver;

/**
 * V2.47 — `window.matchMedia` NO existe en jsdom (`typeof === "undefined"`), así que
 * cualquier componente que consulte el ancho (hook `useMediaQuery`) o el tema caía en
 * el fallback o directamente lanzaba. Este stub por defecto fija un viewport de
 * ESCRITORIO (1280 px) para que los tests existentes sigan ejerciendo el layout de
 * siempre; los tests que quieran el layout móvil usan `stubNarrowViewport()`
 * (`src/lib/test-viewport.ts`), con el mismo parser de `min-width`/`max-width`.
 */
globalThis.matchMedia = ((query: string) => {
  const matches = matchesViewport(query, DESKTOP_VIEWPORT_PX);
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
}) as unknown as typeof globalThis.matchMedia;
