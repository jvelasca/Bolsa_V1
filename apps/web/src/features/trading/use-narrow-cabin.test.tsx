/**
 * V2.47 — primer slice móvil de la cabina de trading.
 *
 * Cubre las dos piezas que comparten los 6 componentes:
 * · helper de filas (`cabinRowClass`) — apilado en estrecho, wrap en ancho;
 * · umbral del slice (`CABIN_NARROW_QUERY`) y su hook sobre `matchMedia`.
 */

import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CABIN_NARROW_QUERY,
  cabinRowClass,
  cabinRowValueClass,
  cabinWidth,
  useNarrowCabin,
} from "@/features/trading/use-narrow-cabin";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("cabinRowClass — la misma fila, dos anchos", () => {
  it("en ancho mantiene una línea con wrap de seguridad", () => {
    const wide = cabinRowClass(false);
    expect(wide).toMatch(/justify-between/);
    expect(wide).toMatch(/flex-wrap/);
    expect(wide).not.toMatch(/flex-col/);
  });

  it("en estrecho apila etiqueta y valor (sin columnas peleando)", () => {
    const narrow = cabinRowClass(true);
    expect(narrow).toMatch(/flex-col/);
    expect(narrow).toMatch(/items-start/);
    expect(narrow).not.toMatch(/justify-between/);
  });

  it("el valor se alinea a la izquierda solo al apilar", () => {
    expect(cabinRowValueClass(false)).toBe("text-right");
    expect(cabinRowValueClass(true)).toBe("text-left");
  });

  it("declara el ancho en un marcador estable para test/QA", () => {
    expect(cabinWidth(true)).toBe("narrow");
    expect(cabinWidth(false)).toBe("wide");
  });
});

describe("useNarrowCabin — umbral del slice", () => {
  it("el umbral es el borde `sm` de Tailwind (teléfono)", () => {
    expect(CABIN_NARROW_QUERY).toBe("(max-width: 640px)");
  });

  it("teléfono (390 px) ⇒ estrecho", () => {
    // Stub propio: 390 px cumple `max-width: 640px`.
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query === CABIN_NARROW_QUERY,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    const { result } = renderHook(() => useNarrowCabin());
    expect(result.current).toBe(true);
  });

  it("escritorio (viewpor del stub global de tests) ⇒ ancho, sin asumirlo a ciegas", () => {
    const { result } = renderHook(() => useNarrowCabin());
    expect(result.current).toBe(false);
  });

  it("sin `matchMedia` disponible NO revienta: cae al lado conservador", () => {
    vi.stubGlobal("matchMedia", undefined);
    const { result } = renderHook(() => useNarrowCabin());
    expect(result.current).toBe(false);
  });
});
