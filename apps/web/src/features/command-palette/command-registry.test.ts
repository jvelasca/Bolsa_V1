import { describe, expect, it, vi } from "vitest";
import {
  filterCommands,
  LABORATORIO_PATH,
  PLATFORM_COMMANDS,
  type CommandRunContext,
} from "./command-registry";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import {
  ASESOR_PATH,
  CARTERA_POSICIONES_PATH,
  MERCADO_PATH,
  MESA_PATH,
} from "@/features/confirm/daily-nav";

function mockCtx(
  overrides: Partial<CommandRunContext> = {},
): CommandRunContext {
  return {
    navigate: vi.fn(),
    openPlatformConfig: vi.fn(),
    uiDensity: "comfortable",
    setUiDensity: vi.fn(),
    uiTheme: "dark",
    setUiTheme: vi.fn(),
    applyNamedLayout: vi.fn(),
    ...overrides,
  };
}

describe("filterCommands", () => {
  it("returns all commands for empty query", () => {
    expect(filterCommands("")).toHaveLength(PLATFORM_COMMANDS.length);
    expect(filterCommands("   ")).toHaveLength(PLATFORM_COMMANDS.length);
  });

  it("matches label and keywords (accent-insensitive)", () => {
    const hoy = filterCommands("hoy");
    expect(hoy.some((c) => c.id === "nav-hoy")).toBe(true);

    const firma = filterCommands("firma");
    expect(firma.some((c) => c.id === "nav-confirmar")).toBe(true);

    const dens = filterCommands("densidad");
    expect(dens.length).toBeGreaterThanOrEqual(2);
  });

  it("returns empty for unknown query", () => {
    expect(filterCommands("xyzzy-no-match")).toEqual([]);
  });
});

describe("PLATFORM_COMMANDS run", () => {
  it("navigates L1 destinations", () => {
    const ctx = mockCtx();
    const byId = Object.fromEntries(PLATFORM_COMMANDS.map((c) => [c.id, c]));

    byId["nav-hoy"].run(ctx);
    byId["nav-mercado"].run(ctx);
    byId["nav-cartera"].run(ctx);
    byId["nav-asesor"].run(ctx);
    byId["nav-laboratorio"].run(ctx);
    byId["nav-confirmar"].run(ctx);

    expect(ctx.navigate).toHaveBeenCalledWith(MESA_PATH);
    expect(ctx.navigate).toHaveBeenCalledWith(MERCADO_PATH);
    expect(ctx.navigate).toHaveBeenCalledWith(CARTERA_POSICIONES_PATH);
    expect(ctx.navigate).toHaveBeenCalledWith(ASESOR_PATH);
    expect(ctx.navigate).toHaveBeenCalledWith(LABORATORIO_PATH);
    expect(ctx.navigate).toHaveBeenCalledWith(CONFIRM_PATH);
  });

  it("opens config tabs and toggles density", () => {
    const setUiDensity = vi.fn();
    const ctx = mockCtx({ uiDensity: "comfortable", setUiDensity });
    const byId = Object.fromEntries(PLATFORM_COMMANDS.map((c) => [c.id, c]));

    byId["config-general"].run(ctx);
    expect(ctx.openPlatformConfig).toHaveBeenCalledWith("general");

    byId["density-compact"].run(ctx);
    expect(setUiDensity).toHaveBeenCalledWith("compact");

    byId["density-toggle"].run(ctx);
    expect(setUiDensity).toHaveBeenCalledWith("compact");
  });

  it("sets theme and cycles toggle", () => {
    const setUiTheme = vi.fn();
    const ctx = mockCtx({ uiTheme: "dark", setUiTheme });
    const byId = Object.fromEntries(PLATFORM_COMMANDS.map((c) => [c.id, c]));

    byId["theme-light"].run(ctx);
    expect(setUiTheme).toHaveBeenCalledWith("light");

    byId["theme-system"].run(ctx);
    expect(setUiTheme).toHaveBeenCalledWith("system");

    byId["theme-toggle"].run(ctx);
    expect(setUiTheme).toHaveBeenCalledWith("light");
  });

  it("applies named layouts", () => {
    const applyNamedLayout = vi.fn();
    const ctx = mockCtx({ applyNamedLayout });
    const byId = Object.fromEntries(PLATFORM_COMMANDS.map((c) => [c.id, c]));

    byId["layout-simple"].run(ctx);
    byId["layout-trader"].run(ctx);
    byId["layout-analista"].run(ctx);

    expect(applyNamedLayout).toHaveBeenCalledWith("simple");
    expect(applyNamedLayout).toHaveBeenCalledWith("trader");
    expect(applyNamedLayout).toHaveBeenCalledWith("analista");
  });
});
