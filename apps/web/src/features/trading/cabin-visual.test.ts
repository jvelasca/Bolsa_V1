/**
 * V2.31 — Premium Visual System tokens.
 */

import { describe, expect, it } from "vitest";
import {
  CABIN_NUM,
  CABIN_TOUCH_TARGET,
  CABIN_TYPE,
  CABIN_VISUAL_VERSION,
  cabinNumClass,
  cabinNumTone,
} from "@/features/trading/cabin-visual";

describe("cabin-visual V2.37", () => {
  it("exposes three type sizes: hero / operativa / meta", () => {
    expect(CABIN_VISUAL_VERSION).toBe("v2.37");
    expect(CABIN_TYPE.hero).toMatch(/cabin-type-hero/);
    expect(CABIN_TYPE.operativa).toMatch(/cabin-type-operativa/);
    expect(CABIN_TYPE.meta).toMatch(/cabin-type-meta/);
    expect(JSON.stringify(CABIN_TYPE)).not.toMatch(
      /text-\[9px\]|text-\[10px\]/,
    );
  });

  it("financial numbers are tabular with semantic color and no fill", () => {
    expect(CABIN_NUM.base).toMatch(/tabular-nums/);
    expect(CABIN_NUM.base).toMatch(/font-semibold/);
    expect(CABIN_NUM.pos).toMatch(/emerald/);
    expect(CABIN_NUM.neg).toMatch(/rose/);
    expect(CABIN_NUM.pos).not.toMatch(/bg-/);
    expect(CABIN_NUM.neg).not.toMatch(/bg-/);
    expect(cabinNumTone(1.2)).toBe("pos");
    expect(cabinNumTone(-0.4)).toBe("neg");
    expect(cabinNumTone(0)).toBe("neu");
    expect(cabinNumTone(null)).toBe("neu");
    expect(cabinNumClass({ signed: true, value: 2 })).toMatch(/emerald/);
    expect(cabinNumClass()).toMatch(/tabular-nums/);
  });

  it("V2.40 — CABIN_TOUCH_TARGET is ≥40px (min-h-10 / min-w-10)", () => {
    expect(CABIN_TOUCH_TARGET).toMatch(/min-h-10/);
    expect(CABIN_TOUCH_TARGET).toMatch(/min-w-10/);
  });
});
