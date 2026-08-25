import { describe, expect, it, vi } from "vitest";
import {
  actorBadgeClasses,
  eventTypeBadgeClasses,
  formatEventTypeLabel,
  formatJournalDateTime,
  formatJournalSetupLine,
  openDecisionReplay,
} from "@/features/decision-journal/decision-journal-helpers";

describe("decision-journal-helpers", () => {
  it("formatJournalDateTime devuelve ISO si la fecha es inválida", () => {
    expect(formatJournalDateTime("not-a-date")).toBe("not-a-date");
  });

  it("formatJournalDateTime formatea ISO válido", () => {
    const out = formatJournalDateTime("2026-08-24T10:30:00Z");
    expect(out).toMatch(/24/);
    expect(out).toMatch(/08/);
  });

  it("formatEventTypeLabel reemplaza guiones bajos", () => {
    expect(formatEventTypeLabel("human_confirm")).toBe("human confirm");
    expect(formatEventTypeLabel("gate_evaluated")).toBe("gate evaluated");
  });

  it("formatJournalSetupLine construye setup · status · phase · effort", () => {
    expect(
      formatJournalSetupLine({
        entrySetup: "wyckoff",
        tradePlanStatus: "ARMED",
        phase: "lps",
        effort: "result_ok",
      }),
    ).toBe("wyckoff · ARMED · fase lps · result ok");
    expect(formatJournalSetupLine({ status: "open" })).toBeNull();
    expect(formatJournalSetupLine(null)).toBeNull();
  });

  it("eventTypeBadgeClasses asigna colores por tipo", () => {
    expect(eventTypeBadgeClasses("human_confirm")).toMatch(/emerald/);
    expect(eventTypeBadgeClasses("risk_veto")).toMatch(/rose/);
    expect(eventTypeBadgeClasses("proposal_recorded")).toMatch(/sky/);
    expect(eventTypeBadgeClasses("unknown_type")).toMatch(/muted/);
  });

  it("actorBadgeClasses distingue human vs system", () => {
    expect(actorBadgeClasses("human")).toMatch(/indigo/);
    expect(actorBadgeClasses("system")).toMatch(/muted/);
  });

  it("openDecisionReplay despacha bolsa:open-help con sessionId", () => {
    const spy = vi.fn();
    window.addEventListener("bolsa:open-help", spy);
    openDecisionReplay("sess-abc");
    expect(spy).toHaveBeenCalledOnce();
    const event = spy.mock.calls[0]![0] as CustomEvent;
    expect(event.detail).toEqual({
      section: "value-analysis",
      sessionId: "sess-abc",
    });
    window.removeEventListener("bolsa:open-help", spy);
  });
});
