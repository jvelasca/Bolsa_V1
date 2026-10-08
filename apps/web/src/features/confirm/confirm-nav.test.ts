/**
 * Tests — ruta y badge de Confirmar (R-12 C1).
 */

import { describe, expect, it } from "vitest";
import {
  BOLSA_NAVIGATE_EVENT,
  CONFIRM_PATH,
  HOY_ATTENTION_QUESTION,
  confirmNavAriaLabel,
  formatConfirmNavBadge,
  isConfirmNavigateTarget,
} from "@/features/confirm/confirm-nav";

describe("confirm-nav", () => {
  it("exports the first-level confirm path", () => {
    expect(CONFIRM_PATH).toBe("/confirm");
    expect(BOLSA_NAVIGATE_EVENT).toBe("bolsa:navigate");
  });

  it("hides the badge when the queue is empty", () => {
    expect(formatConfirmNavBadge(0)).toBeNull();
    expect(formatConfirmNavBadge(-1)).toBeNull();
    expect(confirmNavAriaLabel(0)).toBeUndefined();
  });

  it("shows the count and caps at 9+", () => {
    expect(formatConfirmNavBadge(1)).toBe("1");
    expect(formatConfirmNavBadge(9)).toBe("9");
    expect(formatConfirmNavBadge(10)).toBe("9+");
  });

  it("rotula los pendientes con lenguaje de resultado (sin jerga de firma)", () => {
    expect(confirmNavAriaLabel(1)).toBe("1 requiere tu atención");
    expect(confirmNavAriaLabel(3)).toBe("3 requieren tu atención");
    expect(confirmNavAriaLabel(3)).not.toMatch(/firma/i);
  });

  it("declara la pregunta de primer nivel de Hoy (`R-G2`)", () => {
    expect(HOY_ATTENTION_QUESTION).toBe("¿Qué requiere mi atención?");
  });

  it("allows only the internal /confirm navigate target", () => {
    expect(isConfirmNavigateTarget("/confirm")).toBe(true);
    expect(isConfirmNavigateTarget("https://evil.example/confirm")).toBe(false);
    expect(isConfirmNavigateTarget("/help")).toBe(false);
    expect(isConfirmNavigateTarget("//evil.example")).toBe(false);
    expect(isConfirmNavigateTarget(undefined)).toBe(false);
  });
});
