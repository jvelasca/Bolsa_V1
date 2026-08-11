import { describe, expect, it, vi } from "vitest";
import {
  scrollListInstrumentToTop,
  stickyListHeaderOffset,
} from "@/lib/scroll-list-instrument-into-view";

describe("scrollListInstrumentToTop", () => {
  it("returns false when container or instrument missing", () => {
    expect(scrollListInstrumentToTop(null, "a")).toBe(false);
    const container = document.createElement("div");
    expect(scrollListInstrumentToTop(container, null)).toBe(false);
  });

  it("subtracts sticky header height so the row is not hidden under it", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "scrollTop", {
      value: 100,
      writable: true,
    });
    container.scrollTo = vi.fn();
    container.getBoundingClientRect = () =>
      ({
        top: 200,
        bottom: 500,
        left: 0,
        right: 100,
        width: 100,
        height: 300,
        x: 0,
        y: 200,
      }) as DOMRect;

    const header = document.createElement("div");
    header.className = "sticky top-0";
    header.getBoundingClientRect = () =>
      ({
        top: 200,
        bottom: 228,
        left: 0,
        right: 100,
        width: 100,
        height: 28,
        x: 0,
        y: 200,
      }) as DOMRect;

    const row = document.createElement("div");
    row.setAttribute("data-instrument-id", "inst-1");
    row.getBoundingClientRect = () =>
      ({
        top: 350,
        bottom: 380,
        left: 0,
        right: 100,
        width: 100,
        height: 30,
        x: 0,
        y: 350,
      }) as DOMRect;

    container.appendChild(header);
    container.appendChild(row);
    document.body.appendChild(container);

    expect(stickyListHeaderOffset(container)).toBe(28);
    expect(
      scrollListInstrumentToTop(container, "inst-1", { behavior: "auto" }),
    ).toBe(true);
    // 100 + (350 - 200) - 28 = 222
    expect(container.scrollTo).toHaveBeenCalledWith({
      top: 222,
      behavior: "auto",
    });

    document.body.removeChild(container);
  });
});
