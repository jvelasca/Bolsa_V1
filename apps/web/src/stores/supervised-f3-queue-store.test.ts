import { describe, expect, it } from "vitest";
import {
  openHelpAiPlatform,
  resolveSupervisedQueueOrigin,
  supervisedQueueOriginLabel,
} from "@/stores/supervised-f3-queue-store";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

describe("resolveSupervisedQueueOrigin", () => {
  it("prefers explicit origin", () => {
    expect(
      resolveSupervisedQueueOrigin({
        origin: "finalists",
        scanId: "scan-1",
        payload: { source: "x" } as never,
      }),
    ).toBe("finalists");
  });

  it("detects finalists from payload.source or legacy scanId prefix", () => {
    expect(
      resolveSupervisedQueueOrigin({
        payload: { source: "finalists" } as never,
      }),
    ).toBe("finalists");
    expect(
      resolveSupervisedQueueOrigin({
        scanId: "finalists:inst-1",
        payload: {} as never,
      }),
    ).toBe("finalists");
  });

  it("labels scan vs manual", () => {
    expect(
      resolveSupervisedQueueOrigin({
        scanId: "abc",
        payload: {} as never,
      }),
    ).toBe("scan");
    expect(resolveSupervisedQueueOrigin({ payload: {} as never })).toBe(
      "manual",
    );
    expect(supervisedQueueOriginLabel("finalists")).toBe("Finalistas");
    expect(supervisedQueueOriginLabel("scan")).toBe("Scan");
  });

  it("resolves alarm origin from source or meta", () => {
    expect(
      resolveSupervisedQueueOrigin({
        origin: "alarm",
        payload: {} as never,
      }),
    ).toBe("alarm");
    expect(
      resolveSupervisedQueueOrigin({
        payload: { source: "alarm" } as never,
      }),
    ).toBe("alarm");
    expect(supervisedQueueOriginLabel("alarm")).toBe("Alarma Radar");
  });
});

describe("openHelpAiPlatform", () => {
  it("dispatches bolsa:navigate to /confirm when panel is supervised-f3", () => {
    const navigated: string[] = [];
    const helped: unknown[] = [];
    const onNav = (e: Event) => {
      navigated.push((e as CustomEvent<{ to?: string }>).detail?.to ?? "");
    };
    const onHelp = (e: Event) => {
      helped.push((e as CustomEvent).detail);
    };
    window.addEventListener("bolsa:navigate", onNav);
    window.addEventListener("bolsa:open-help", onHelp);
    try {
      openHelpAiPlatform({ panel: "supervised-f3" });
      expect(navigated).toEqual([CONFIRM_PATH]);
      expect(helped).toEqual([]);
    } finally {
      window.removeEventListener("bolsa:navigate", onNav);
      window.removeEventListener("bolsa:open-help", onHelp);
    }
  });

  it("dispatches bolsa:open-help when called without panel", () => {
    const navigated: string[] = [];
    const helped: unknown[] = [];
    const onNav = (e: Event) => {
      navigated.push((e as CustomEvent<{ to?: string }>).detail?.to ?? "");
    };
    const onHelp = (e: Event) => {
      helped.push((e as CustomEvent).detail);
    };
    window.addEventListener("bolsa:navigate", onNav);
    window.addEventListener("bolsa:open-help", onHelp);
    try {
      openHelpAiPlatform();
      expect(navigated).toEqual([]);
      expect(helped).toEqual([{ section: "ai", panel: undefined }]);
    } finally {
      window.removeEventListener("bolsa:navigate", onNav);
      window.removeEventListener("bolsa:open-help", onHelp);
    }
  });
});
