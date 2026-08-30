import { describe, expect, it } from "vitest";
import {
  isNamedLayoutId,
  namedLayoutDockSnapshot,
  NAMED_LAYOUT_DEFAULT,
} from "./named-layout";

describe("named-layout", () => {
  it("validates ids", () => {
    expect(isNamedLayoutId("simple")).toBe(true);
    expect(isNamedLayoutId("trader")).toBe(true);
    expect(isNamedLayoutId("analista")).toBe(true);
    expect(isNamedLayoutId("custom")).toBe(false);
    expect(isNamedLayoutId(null)).toBe(false);
  });

  it("default is trader", () => {
    expect(NAMED_LAYOUT_DEFAULT).toBe("trader");
  });

  it("SIMPLE = chart + operativa", () => {
    expect(namedLayoutDockSnapshot("simple")).toEqual({
      listsOpen: false,
      chartsOpen: true,
      operationsOpen: false,
      operativaOpen: true,
    });
  });

  it("TRADER = all docks open", () => {
    expect(namedLayoutDockSnapshot("trader")).toEqual({
      listsOpen: true,
      chartsOpen: true,
      operationsOpen: true,
      operativaOpen: true,
    });
  });

  it("ANALISTA = lists + chart + operativa, ops off", () => {
    expect(namedLayoutDockSnapshot("analista")).toEqual({
      listsOpen: true,
      chartsOpen: true,
      operationsOpen: false,
      operativaOpen: true,
    });
  });
});
