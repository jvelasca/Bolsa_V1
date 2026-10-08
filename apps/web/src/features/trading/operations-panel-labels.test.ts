/**
 * Barrido semántico P0 — el panel de operaciones en superficie AUTO no usa
 * vocabulario de mercado («… abiertas») en el primer nivel.
 *
 * @see docs/engineering/auditoria-ui-auto-pantalla-2026-10-06.md §6
 */

import { describe, expect, it } from "vitest";
import {
  ABSENT_DATA_NOT_MEASURED,
  ABSENT_DATA_TECHNICAL_DASH,
  absentDataLabel,
} from "@/components/absent-data";
import {
  OPERATIONS_PANEL_RESULT_COLUMN_LABEL,
  OPERATIONS_PANEL_SURFACE_LABELS,
} from "@/features/trading/operations-panel";

describe("OperationsPanel — rótulos por superficie", () => {
  it("en AUTO rotula «Posiciones» y no «Operaciones abiertas»", () => {
    expect(OPERATIONS_PANEL_SURFACE_LABELS.openTab.auto).toBe("Posiciones");
    expect(OPERATIONS_PANEL_SURFACE_LABELS.openTab.market).toBe(
      "Operaciones abiertas",
    );
  });

  it("en AUTO el vacío no dice «abiertas»", () => {
    expect(OPERATIONS_PANEL_SURFACE_LABELS.emptyOpen.auto).toBe(
      "Sin posiciones en la cuenta simulada",
    );
    expect(
      OPERATIONS_PANEL_SURFACE_LABELS.emptyOpen.auto.toLowerCase(),
    ).not.toContain("abiertas");
  });

  it("ningún rótulo AUTO filtra vocabulario prohibido de primer nivel", () => {
    const autoCopy = [
      OPERATIONS_PANEL_SURFACE_LABELS.openTab.auto,
      OPERATIONS_PANEL_SURFACE_LABELS.emptyOpen.auto,
    ].join(" \n ");
    for (const forbidden of [
      "T1 ejecutado",
      "Orden enviada",
      "pendiente de ack",
      "DINERO REAL",
    ]) {
      expect(autoCopy).not.toContain(forbidden);
    }
  });

  it("UI5-20 · la columna de Decisión+Ejecución ya no se fusiona bajo «Salida»", () => {
    // La celda pinta la acción de la decisión y su estado de ejecución; un solo término honesto.
    expect(OPERATIONS_PANEL_RESULT_COLUMN_LABEL).toBe("Resultado");
    expect(OPERATIONS_PANEL_RESULT_COLUMN_LABEL).not.toBe("Salida");
  });

  it("UI5-14 · primer nivel usa el rótulo oficial de hueco, no «—»", () => {
    // El hueco de nivel 1 es el rótulo compartido; el guion queda para nivel 3.
    expect(absentDataLabel()).toBe(ABSENT_DATA_NOT_MEASURED);
    expect(absentDataLabel()).not.toBe(ABSENT_DATA_TECHNICAL_DASH);
    for (const label of Object.values(OPERATIONS_PANEL_SURFACE_LABELS).flatMap(
      (bySurface) => Object.values(bySurface),
    )) {
      expect(label).not.toContain(ABSENT_DATA_TECHNICAL_DASH);
    }
  });
});
