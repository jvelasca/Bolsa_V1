/**
 * V1.20 — redirects Zona 1 + deep-links Hoy / Cartera / Decisiones.
 */

import { describe, expect, it } from "vitest";
import {
  CARTERA_POSICIONES_PATH,
  DECISIONES_PATH,
  DECISION_SPINE_PATH,
  LIBRO_OPERACIONES_PATH,
  MESA_PATH,
  hoyViewHref,
  HOY_VIEW,
} from "@/features/confirm/daily-nav";
import {
  mesaOperationsHref,
  mesaSpineHref,
} from "@/features/mesa/mesa-nav-links";
import { mesaScreenersUniverseHref } from "@/features/mesa/mesa-candidates-panel";

describe("v120 mesa zone1 redirects and deep-links", () => {
  it("Cartera posiciones path is Hoy view=posiciones", () => {
    expect(LIBRO_OPERACIONES_PATH).toBe("/mesa?view=posiciones");
    expect(CARTERA_POSICIONES_PATH).toBe("/mesa?view=posiciones");
    expect(mesaOperationsHref()).toBe("/mesa?view=posiciones");
    expect(LIBRO_OPERACIONES_PATH.startsWith(MESA_PATH)).toBe(true);
  });

  it("Decisiones path is Hoy view=decisiones (not /decision-board)", () => {
    expect(DECISION_SPINE_PATH).toBe("/mesa?view=decisiones");
    expect(DECISIONES_PATH).toBe("/mesa?view=decisiones");
    expect(mesaSpineHref()).toBe("/mesa?view=decisiones");
    expect(hoyViewHref(HOY_VIEW.decisiones)).toBe("/mesa?view=decisiones");
  });

  it("Screeners CTA deep-links Estudio listId by default", () => {
    expect(mesaScreenersUniverseHref()).toBe("/screeners?listId=estudio");
  });
});
