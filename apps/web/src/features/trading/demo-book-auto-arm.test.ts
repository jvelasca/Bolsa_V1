import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  AUTO_ARM_CONFIRM_PHRASE,
  defaultAutoArm,
  disarmAutoArm,
  loadAutoArm,
  saveAutoArm,
  tryArmAuto,
  useAutoArmArmed,
} from "@/features/trading/demo-book-auto-arm";

afterEach(() => cleanup());

describe("demo-book-auto-arm (A3)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("rejects wrong phrase", () => {
    const r = tryArmAuto("activar auto");
    expect(r.ok).toBe(false);
    expect(loadAutoArm().armed).toBe(false);
  });

  it("arms with exact phrase and can disarm", () => {
    const r = tryArmAuto(AUTO_ARM_CONFIRM_PHRASE);
    expect(r.ok).toBe(true);
    expect(loadAutoArm().armed).toBe(true);
    expect(disarmAutoArm()).toEqual(defaultAutoArm());
  });

  it("useAutoArmArmed reacciona al armado sin remontar", () => {
    const { result } = renderHook(() => useAutoArmArmed());
    expect(result.current).toBe(false);

    act(() => {
      tryArmAuto(AUTO_ARM_CONFIRM_PHRASE);
    });
    expect(result.current).toBe(true);

    act(() => {
      disarmAutoArm();
    });
    expect(result.current).toBe(false);
  });

  it("useAutoArmArmed ignora escrituras de armado ajenas (solo cambia armed)", () => {
    const { result } = renderHook(() => useAutoArmArmed());
    act(() => {
      saveAutoArm({ armed: false, armedAt: "2026-01-01T00:00:00.000Z", confirmPhrase: null });
    });
    expect(result.current).toBe(false);

    act(() => {
      saveAutoArm({ armed: true, armedAt: "2026-01-02T00:00:00.000Z", confirmPhrase: AUTO_ARM_CONFIRM_PHRASE });
    });
    expect(result.current).toBe(true);
  });
});
