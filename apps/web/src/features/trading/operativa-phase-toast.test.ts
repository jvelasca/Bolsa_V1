import { describe, expect, it } from "vitest";
import {
  collectOperativaToastEvents,
  formatOperativaToastMessage,
  partitionFreshOperativaEvents,
  resolveListOperativaBadge,
} from "@/features/trading/operativa-phase-toast";

describe("resolveListOperativaBadge", () => {
  it("shows Disparada for disparada phase", () => {
    expect(
      resolveListOperativaBadge({
        phase: "disparada",
        target1Touched: false,
        target1Managed: false,
      }),
    ).toEqual({ kind: "disparada", label: "Disparada" });
  });

  it("shows Propuesta for propuesta phase", () => {
    expect(
      resolveListOperativaBadge({
        phase: "propuesta",
        target1Touched: false,
        target1Managed: false,
      }),
    ).toEqual({ kind: "propuesta", label: "Propuesta" });
  });

  it("shows T1 when touched and not managed in posicion", () => {
    expect(
      resolveListOperativaBadge({
        phase: "posicion",
        target1Touched: true,
        target1Managed: false,
      }),
    ).toEqual({ kind: "t1", label: "T1 ●" });
  });

  it("H2 — no T1 badge when managed", () => {
    expect(
      resolveListOperativaBadge({
        phase: "posicion",
        target1Touched: true,
        target1Managed: true,
      }),
    ).toBeNull();
  });

  it("no badge for vigilar", () => {
    expect(
      resolveListOperativaBadge({
        phase: "vigilar",
        target1Touched: false,
        target1Managed: false,
      }),
    ).toBeNull();
  });
});

describe("collectOperativaToastEvents", () => {
  it("collects disparada and T1 events", () => {
    const events = collectOperativaToastEvents([
      {
        instrumentId: "a",
        symbol: "AAA",
        phase: "disparada",
        target1Touched: false,
        target1Managed: false,
        decisionId: "d1",
      },
      {
        instrumentId: "b",
        symbol: "BBB",
        phase: "posicion",
        target1Touched: true,
        target1Managed: false,
        positionId: "p1",
      },
      {
        instrumentId: "c",
        symbol: "CCC",
        phase: "vigilar",
        target1Touched: false,
        target1Managed: false,
      },
    ]);
    expect(events).toHaveLength(2);
    expect(events[0]?.kind).toBe("disparada");
    expect(events[1]?.kind).toBe("t1");
  });
});

describe("formatOperativaToastMessage", () => {
  it("DISPARADA mentions confirm and ranking", () => {
    expect(
      formatOperativaToastMessage({
        key: "x",
        kind: "disparada",
        instrumentId: "a",
        symbol: "NVDA",
      }),
    ).toMatch(/disparada/i);
    expect(
      formatOperativaToastMessage({
        key: "x",
        kind: "disparada",
        instrumentId: "a",
        symbol: "NVDA",
      }),
    ).toMatch(/Ranking ≠ BUY/);
  });

  it("T1 is informational (H2)", () => {
    const msg = formatOperativaToastMessage({
      key: "x",
      kind: "t1",
      instrumentId: "a",
      symbol: "NVDA",
    });
    expect(msg).toMatch(/T1 alcanzado/i);
    expect(msg).toMatch(/pendiente de gestión/i);
    expect(msg).toMatch(/tocado ≠ reducido/i);
  });
});

describe("partitionFreshOperativaEvents", () => {
  it("skips already seen keys", () => {
    const events = collectOperativaToastEvents([
      {
        instrumentId: "a",
        symbol: "AAA",
        phase: "disparada",
        target1Touched: false,
        target1Managed: false,
        decisionId: "d1",
      },
    ]);
    const seen = new Set([events[0]!.key]);
    const { fresh } = partitionFreshOperativaEvents(events, seen);
    expect(fresh).toHaveLength(0);
  });
});
