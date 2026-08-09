import { describe, expect, it } from "vitest";

import { isAnalysisResultFocus, isHubTab, parseTab } from "./backtest-hub-nav";

describe("parseTab (navegación Hub `/backtests`)", () => {
  it("parsea tabs válidos", () => {
    expect(parseTab("run")).toBe("run");
    expect(parseTab("history")).toBe("history");
    expect(parseTab("strategies")).toBe("strategies");
    expect(parseTab("jobs")).toBe("jobs");
  });

  it("legacy deep-links (?tab=new / null / vacío) → run", () => {
    expect(parseTab("new")).toBe("run");
    expect(parseTab(null)).toBe("run");
    expect(parseTab("")).toBe("run");
    expect(parseTab(undefined as unknown as string | null)).toBe("run");
  });

  it("tabs desconocidos → run (default seguro)", () => {
    expect(parseTab("nope")).toBe("run");
    expect(parseTab("archive")).toBe("run");
  });
});

describe("isAnalysisResultFocus", () => {
  it("detail y fundamental son análisis", () => {
    expect(isAnalysisResultFocus("detail")).toBe(true);
    expect(isAnalysisResultFocus("fundamental")).toBe(true);
  });

  it("focus de flujo NO son análisis", () => {
    expect(isAnalysisResultFocus("coach")).toBe(false);
    expect(isAnalysisResultFocus("lab")).toBe(false);
    expect(isAnalysisResultFocus("finalists")).toBe(false);
    expect(isAnalysisResultFocus("ranking")).toBe(false);
    expect(isAnalysisResultFocus("list_auto")).toBe(false);
  });
});

describe("isHubTab (guard)", () => {
  it("valida tabs conocidos", () => {
    expect(isHubTab("run")).toBe(true);
    expect(isHubTab("history")).toBe(true);
    expect(isHubTab("strategies")).toBe(true);
    expect(isHubTab("jobs")).toBe(true);
  });

  it("rechaza no-tabs", () => {
    expect(isHubTab("foo")).toBe(false);
    expect(isHubTab("")).toBe(false);
    expect(isHubTab(null)).toBe(false);
    expect(isHubTab(undefined)).toBe(false);
  });
});
