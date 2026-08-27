/**
 * V1.19 — redirects Zona 1 + deep-links Mesa.
 */

import { describe, expect, it } from "vitest";
import {
  DECISION_SPINE_PATH,
  LIBRO_OPERACIONES_PATH,
  MESA_PATH,
} from "@/features/confirm/daily-nav";
import {
  mesaOperationsHref,
  mesaSpineHref,
} from "@/features/mesa/mesa-nav-links";
import { mesaScreenersUniverseHref } from "@/features/mesa/mesa-candidates-panel";

describe("v119 mesa zone1 redirects and deep-links", () => {
  it("Libro operaciones path is Mesa focus=libro (not /operations)", () => {
    expect(LIBRO_OPERACIONES_PATH).toBe("/mesa?focus=libro");
    expect(mesaOperationsHref()).toBe("/mesa?focus=libro");
    expect(LIBRO_OPERACIONES_PATH.startsWith(MESA_PATH)).toBe(true);
  });

  it("Decision Spine path is Mesa focus=spine (not /decision-board)", () => {
    expect(DECISION_SPINE_PATH).toBe("/mesa?focus=spine");
    expect(mesaSpineHref()).toBe("/mesa?focus=spine");
  });

  it("Screeners CTA deep-links ibex35 listId", () => {
    expect(mesaScreenersUniverseHref()).toBe("/screeners?listId=ibex35");
  });
});
