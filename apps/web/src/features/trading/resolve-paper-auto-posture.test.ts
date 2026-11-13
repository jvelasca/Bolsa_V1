/**
 * Fase 4 — el postura AUTO usa el valor reactivo que le pasa el hook.
 *
 * Antes, `resolvePaperAutoPosture` releía `localStorage` para `autoArmed`; si el panel
 * pasaba el valor del hook reactivo, esa relectura podía contradecirlo (armado congelado
 * o carrera tras desarmar). Con `autoArmed` explícito no debe tocar el latch.
 */

import { beforeEach, describe, expect, it } from "vitest";
import { AUTO_ARM_CONFIRM_PHRASE, saveAutoArm } from "@/features/trading/demo-book-auto-arm";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";

describe("resolvePaperAutoPosture", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("no relee el latch cuando autoArmed se pasa explícito", () => {
    // Latch armado en storage, pero el hook (fuente reactiva) dice desarmado.
    saveAutoArm({
      armed: true,
      armedAt: "2026-01-01T00:00:00.000Z",
      confirmPhrase: AUTO_ARM_CONFIRM_PHRASE,
    });

    const posture = resolvePaperAutoPosture({
      bookMode: "auto",
      autoArmed: false,
      paperDExecuteEnv: false,
    });

    expect(posture.autoArmed).toBe(false);
    expect(posture.autoActive).toBe(false);
    expect(posture.requiresHumanConfirm).toBe(true);
  });

  it("AUTO activo solo con modo auto + armado reactivo", () => {
    const posture = resolvePaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: true,
    });

    expect(posture.autoActive).toBe(true);
    expect(posture.requiresHumanConfirm).toBe(false);
    expect(posture.executeEligible).toBe(true);
  });

  it("sin entradas cae a SEMI desde storage vacío", () => {
    const posture = resolvePaperAutoPosture();
    expect(posture.bookMode).toBe("semi");
    expect(posture.autoArmed).toBe(false);
    expect(posture.autoActive).toBe(false);
  });
});
