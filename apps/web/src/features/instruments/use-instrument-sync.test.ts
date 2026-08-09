import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { formatSyncError } from "./use-instrument-sync";

describe("formatSyncError", () => {
  it("devuelve el mensaje del ApiError (con status) tal cual", () => {
    const err = new ApiError("Error de sincronización", 502);
    expect(formatSyncError(err)).toBe("Error de sincronización");
  });

  it("traduce el fetch abortado a mensaje de API no contactable", () => {
    const err = new TypeError("Failed to fetch");
    expect(formatSyncError(err)).toMatch(/no se pudo contactar con la API/i);
  });

  it("devuelve el mensaje de un Error genérico", () => {
    const err = new Error("boom");
    expect(formatSyncError(err)).toBe("boom");
  });

  it("devuelve mensaje por defecto ante valor desconocido", () => {
    expect(formatSyncError(null)).toMatch(/error desconocido/i);
    expect(formatSyncError(undefined)).toMatch(/error desconocido/i);
    expect(formatSyncError("x")).toMatch(/error desconocido/i);
  });
});
