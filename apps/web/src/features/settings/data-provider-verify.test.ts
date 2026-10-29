/**
 * Ayuda secuencial de proveedores — `HLP-1` a `HLP-3` del documento
 * `docs/engineering/seguimiento-ui-proveedores-2026-10-29.md`.
 *
 * La secuencia es el recorrido que el operador puede repetir sin leer código: si un
 * paso deja de apuntar a una pantalla o a un endpoint existente, esta prueba lo delata.
 */

import { describe, expect, it } from "vitest";
import { DATA_PROVIDER_VERIFY } from "@/features/settings/data-market-tracker";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";

const KNOWN_SURFACES = [
  "Pantalla",
  "/api/market/providers",
  "/api/sync/queue",
  "/api/sync/settings",
  "/api/instruments/",
  "market_provider_settings",
  "sync_queue",
  "sync_settings",
];

describe("DATA_PROVIDER_VERIFY", () => {
  it("tiene los ocho pasos en orden", () => {
    expect(DATA_PROVIDER_VERIFY).toHaveLength(8);
    expect(DATA_PROVIDER_VERIFY.map((step) => step.id)).toEqual([
      "HLP-1",
      "HLP-2",
      "HLP-3",
      "HLP-4",
      "HLP-5",
      "HLP-6",
      "HLP-7",
      "HLP-8",
    ]);
  });

  it("cada paso declara acción, resultado esperado y dónde se comprueba", () => {
    for (const step of DATA_PROVIDER_VERIFY) {
      expect(step.action.length).toBeGreaterThan(10);
      expect(step.expect.length).toBeGreaterThan(10);
      expect(step.check.length).toBeGreaterThan(5);
    }
  });

  it("no deja pasos huérfanos: cada comprobación apunta a una superficie conocida", () => {
    for (const step of DATA_PROVIDER_VERIFY) {
      const known = KNOWN_SURFACES.some((surface) =>
        step.check.includes(surface),
      );
      expect(known, `paso ${step.id} → ${step.check}`).toBe(true);
    }
  });

  it("está sincronizada con la fecha de la Ayuda", () => {
    expect(HELP_CONTENT_AS_OF).toBe("2026-10-29");
  });
});
