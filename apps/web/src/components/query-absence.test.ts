/**
 * P1-01 — precedencia y vocabulario del estado de lectura de una colección.
 *
 * Falsable: si una superficie vuelve a `data ?? []` sin mirar `isError`, la
 * prueba de render de esa superficie falla; aquí se fija la regla que usa.
 */
import { describe, expect, it } from "vitest";
import {
  collectionAbsenceCopy,
  collectionAbsenceLabel,
  isCollectionAbsent,
  queryCollectionState,
} from "@/components/query-absence";

describe("queryCollectionState", () => {
  it("un error manda sobre el vacío y sobre la carga", () => {
    expect(
      queryCollectionState({ isError: true, isLoading: true, count: 0 }),
    ).toBe("error");
    expect(queryCollectionState({ isError: true, count: 42 })).toBe("error");
  });

  it("la carga no es un vacío", () => {
    expect(queryCollectionState({ isLoading: true, count: null })).toBe(
      "loading",
    );
  });

  it("sin dato (null/undefined) no se interpreta como cero", () => {
    expect(queryCollectionState({ count: null })).toBe("unavailable");
    expect(queryCollectionState({})).toBe("unavailable");
  });

  it("solo un cero leído es vacío", () => {
    expect(queryCollectionState({ count: 0 })).toBe("empty");
    expect(queryCollectionState({ count: 1 })).toBe("ready");
  });

  it("un error durante el refetch no rehabilita la cifra previa", () => {
    expect(queryCollectionState({ isError: true, count: 3 })).toBe("error");
  });
});

describe("vocabulario del hueco", () => {
  it("error y ausencia usan los rótulos de la casa, nunca el vacío", () => {
    expect(collectionAbsenceLabel("error")).toBe("No disponible");
    expect(collectionAbsenceLabel("unavailable")).toBe("Sin dato todavía");
    expect(collectionAbsenceLabel("empty")).toBeNull();
    expect(collectionAbsenceLabel("ready")).toBeNull();
  });

  it("la frase declara el sujeto y no afirma «sin …»", () => {
    const copy = collectionAbsenceCopy("error", "el historial de movimientos");
    expect(copy).toContain("No disponible");
    expect(copy).toContain("el historial de movimientos");
    expect(copy).not.toMatch(/^Sin /);
  });

  it("vacío y listo no producen frase de hueco", () => {
    expect(collectionAbsenceCopy("empty", "el historial")).toBeNull();
    expect(collectionAbsenceCopy("ready", "el historial")).toBeNull();
  });

  it("solo carga, error y sin dato son estados ausentes", () => {
    expect(isCollectionAbsent("error")).toBe(true);
    expect(isCollectionAbsent("loading")).toBe(true);
    expect(isCollectionAbsent("unavailable")).toBe(true);
    expect(isCollectionAbsent("empty")).toBe(false);
    expect(isCollectionAbsent("ready")).toBe(false);
  });
});
