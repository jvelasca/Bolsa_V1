import { beforeEach, describe, expect, it } from "vitest";
import {
  AUTO_ARM_CONFIRM_PHRASE,
  tryArmAuto,
} from "@/features/trading/demo-book-auto-arm";
import {
  DEMO_BOOK_PREFS_KEY,
  defaultDemoBookPrefs,
  demoBookAllowsEnqueueConfirm,
  demoBookAllowsExecute,
  demoBookRequiresEstudioMembership,
  loadDemoBookPrefs,
  normalizeDemoBookPrefs,
  patchDemoBookPrefs,
  suggestQuantityFromCash,
} from "@/features/trading/demo-book-prefs";

describe("demo-book-prefs", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to SEMI with 10 positions and 10% size", () => {
    const d = defaultDemoBookPrefs();
    expect(d.mode).toBe("semi");
    expect(d.maxOpenPositions).toBe(10);
    expect(d.defaultSizePctOfCash).toBe(10);
  });

  it("normalizes invalid mode and clamps N / pct", () => {
    const n = normalizeDemoBookPrefs({
      mode: "nope",
      maxOpenPositions: 99,
      defaultSizePctOfCash: 0,
    });
    expect(n.mode).toBe("semi");
    expect(n.maxOpenPositions).toBe(40);
    expect(n.defaultSizePctOfCash).toBe(1);
  });

  it("A3-wire: coerces stored auto → semi when not armed", () => {
    const n = normalizeDemoBookPrefs({ mode: "auto" });
    expect(n.mode).toBe("semi");
  });

  it("A3-wire: patch auto without arm stays semi", () => {
    const next = patchDemoBookPrefs({ mode: "auto" });
    expect(next.mode).toBe("semi");
    expect(loadDemoBookPrefs().mode).toBe("semi");
  });

  it("A3-wire: exact phrase arms then auto persists; leave auto disarms", () => {
    expect(tryArmAuto(AUTO_ARM_CONFIRM_PHRASE).ok).toBe(true);
    const armed = patchDemoBookPrefs({ mode: "auto" });
    expect(armed.mode).toBe("auto");
    expect(JSON.parse(localStorage.getItem(DEMO_BOOK_PREFS_KEY)!).mode).toBe(
      "auto",
    );

    const back = patchDemoBookPrefs({ mode: "semi" });
    expect(back.mode).toBe("semi");
    // Leaving auto clears arm; re-patch auto without re-arm must fail closed.
    expect(patchDemoBookPrefs({ mode: "auto" }).mode).toBe("semi");
  });

  it("gates enqueue / execute by mode", () => {
    expect(demoBookAllowsEnqueueConfirm("manual")).toBe(false);
    expect(demoBookAllowsEnqueueConfirm("semi")).toBe(true);
    expect(demoBookAllowsEnqueueConfirm("auto")).toBe(true);
    expect(demoBookAllowsExecute("manual")).toBe(false);
    expect(demoBookAllowsExecute("semi")).toBe(true);
    expect(demoBookAllowsExecute("auto")).toBe(false);
  });

  it("SEMI/AUTO require Estudio membership; MANUAL does not", () => {
    expect(demoBookRequiresEstudioMembership("manual")).toBe(false);
    expect(demoBookRequiresEstudioMembership("semi")).toBe(true);
    expect(demoBookRequiresEstudioMembership("auto")).toBe(true);
  });

  it("suggests quantity ≈ 10% cash / price", () => {
    expect(
      suggestQuantityFromCash({ cash: 20_000, price: 100, sizePctOfCash: 10 }),
    ).toBe(20);
    expect(
      suggestQuantityFromCash({ cash: 500, price: 100, sizePctOfCash: 10 }),
    ).toBe(0);
  });
});
