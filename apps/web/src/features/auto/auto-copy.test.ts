/**
 * Contrato del copy de primer nivel del espacio AUTO (UI 7.0 · semántica de producto).
 *
 * Estos tests son la vara falsable de los hallazgos P1 de la auditoría de UI 6.x:
 * - `operar` NO afirma una decisión inexistente («qué ha elegido») mientras no exista
 *   `PortfolioDecision` durable (`ranking ≠ decisión`, `UI5-12`).
 * - `riesgo` NO promete «cuánto puedes perder» mientras el read-model fije
 *   `positionRiskAvailable: false` (`UI5-16`, `UI5-18`).
 * - `cartera` separa «AUTO actúa solo» de «el usuario firma» (`UI5-13`, `UI5-17`).
 * - un único término de dinero virtual; sin alternar DEMO/PAPER/SIMULADO (`UI5-20`).
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-12 §UI5-18 §UI5-20 §UI5-21
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_SECTION_COPY,
  AUTO_VIRTUAL_MONEY_PHRASE,
  type AutoSectionId,
} from "@/features/auto/auto-copy";

const ALL_SECTIONS: readonly AutoSectionId[] = [
  "operar",
  "actividad",
  "cartera",
  "riesgo",
  "analisis",
  "sistema",
];

/** Descripciones de primer nivel concatenadas (nivel 1 auditable). */
const ALL_DESCRIPTIONS = ALL_SECTIONS.map(
  (id) => AUTO_SECTION_COPY[id].description,
).join("\n");

describe("auto-copy — semántica de usuario básico (UI 7.0)", () => {
  it("cada sección tiene título y descripción no vacíos", () => {
    for (const id of ALL_SECTIONS) {
      expect(AUTO_SECTION_COPY[id].title.trim().length).toBeGreaterThan(0);
      expect(AUTO_SECTION_COPY[id].description.trim().length).toBeGreaterThan(
        0,
      );
    }
  });

  it("operar NO afirma una decisión inexistente (ranking ≠ decisión)", () => {
    const description = AUTO_SECTION_COPY.operar.description;
    // Prohibido: afirmar que AUTO ya eligió/decidió.
    expect(description.toLowerCase()).not.toContain("ha elegido");
    expect(description.toLowerCase()).not.toContain("ha decidido");
    // Debe hablar de oportunidades y de operaciones en curso (hechos sí medidos).
    expect(description.toLowerCase()).toContain("oportunidades");
    expect(description.toLowerCase()).toContain("operaciones");
  });

  it("riesgo pregunta por problemas actuales, no promete una cifra inexistente", () => {
    const description = AUTO_SECTION_COPY.riesgo.description;
    expect(description.toLowerCase()).not.toContain("cuánto puedes perder");
    expect(description.toLowerCase()).not.toContain("cuanto puedes perder");
    expect(description.toLowerCase()).toContain("problema de riesgo");
  });

  it("cartera separa la operativa autónoma de la firma humana", () => {
    const description = AUTO_SECTION_COPY.cartera.description.toLowerCase();
    // AUTO continúa solo (sin firma)…
    expect(description).toContain("sin tu firma");
    // …pero lo que hace el usuario sí necesita confirmación.
    expect(description).toContain("confirmación");
  });

  it("usa un único término de dinero virtual (sin DEMO/PAPER en primer nivel)", () => {
    for (const id of ALL_SECTIONS) {
      const lower = AUTO_SECTION_COPY[id].description.toLowerCase();
      expect(lower).not.toContain("demo");
      expect(lower).not.toContain("paper");
    }
    expect(ALL_DESCRIPTIONS.toLowerCase()).toContain("dinero virtual");
  });

  it("expone una única frase oficial de dinero virtual", () => {
    const lower = AUTO_VIRTUAL_MONEY_PHRASE.toLowerCase();
    expect(lower).toContain("dinero virtual");
    expect(lower).toContain("no utiliza dinero real");
  });
});
