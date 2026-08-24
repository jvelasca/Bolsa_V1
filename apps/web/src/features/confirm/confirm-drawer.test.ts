/**
 * Tests — helpers del drawer Confirmar (U3).
 */

import { describe, expect, it } from "vitest";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import {
  BOLSA_CONFIRM_DRAWER_EVENT,
  CONFIRM_DRAWER_CTA_LABEL,
  CONFIRM_FULL_PAGE_LINK_LABEL,
  closeConfirmDrawer,
  confirmFullPagePath,
  formatConfirmDrawerCtaLabel,
  isConfirmDrawerCloseDetail,
  isConfirmDrawerOpenDetail,
  openConfirmDrawer,
} from "@/features/confirm/confirm-drawer";

describe("confirm-drawer helpers", () => {
  it("formats Operativa CTA with optional queue count", () => {
    expect(formatConfirmDrawerCtaLabel(0)).toBe(CONFIRM_DRAWER_CTA_LABEL);
    expect(formatConfirmDrawerCtaLabel(-1)).toBe(CONFIRM_DRAWER_CTA_LABEL);
    expect(formatConfirmDrawerCtaLabel(3)).toBe(
      `${CONFIRM_DRAWER_CTA_LABEL} (3)`,
    );
  });

  it("keeps full-page path as /confirm (deep-link)", () => {
    expect(confirmFullPagePath()).toBe(CONFIRM_PATH);
    expect(CONFIRM_FULL_PAGE_LINK_LABEL.length).toBeGreaterThan(5);
  });

  it("narrows open/close event details", () => {
    expect(isConfirmDrawerOpenDetail({ open: true })).toBe(true);
    expect(isConfirmDrawerOpenDetail({ open: false })).toBe(false);
    expect(isConfirmDrawerCloseDetail({ open: false })).toBe(true);
    expect(isConfirmDrawerCloseDetail({ open: true })).toBe(false);
    expect(isConfirmDrawerOpenDetail(null)).toBe(false);
    expect(isConfirmDrawerOpenDetail("x")).toBe(false);
  });

  it("dispatches bolsa:confirm-drawer open/close", () => {
    const seen: unknown[] = [];
    const onEv = (e: Event) => {
      seen.push((e as CustomEvent).detail);
    };
    window.addEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEv);
    try {
      openConfirmDrawer();
      closeConfirmDrawer();
      expect(seen).toEqual([{ open: true }, { open: false }]);
    } finally {
      window.removeEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEv);
    }
  });
});
