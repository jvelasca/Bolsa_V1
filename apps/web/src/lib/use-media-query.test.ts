/**
 * V2.47 — `mediaQueryMatches`: lectura segura de matchMedia.
 * El hook se usaba en componentes de la cabina; sin guardia lanzaba `TypeError`
 * en cualquier entorno sin `matchMedia` (jsdom). Aquí se fija el contrato.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { mediaQueryMatches } from "@/lib/use-media-query";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("mediaQueryMatches", () => {
  it("devuelve el matches real cuando matchMedia existe", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query === "(max-width: 640px)",
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    expect(mediaQueryMatches("(max-width: 640px)")).toBe(true);
    expect(mediaQueryMatches("(min-width: 1024px)")).toBe(false);
  });

  it("sin matchMedia devuelve false en vez de lanzar", () => {
    vi.stubGlobal("matchMedia", undefined);
    expect(mediaQueryMatches("(max-width: 640px)")).toBe(false);
  });

  it("no inventa coincidencias para queries no soportadas", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    expect(mediaQueryMatches("(prefers-reduced-motion: reduce)")).toBe(false);
  });
});
