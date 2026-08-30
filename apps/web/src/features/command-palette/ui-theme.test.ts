import { describe, expect, it } from "vitest";
import {
  isUiTheme,
  nextUiTheme,
  resolveUiTheme,
  UI_THEME_DEFAULT,
} from "./ui-theme";

describe("ui-theme", () => {
  it("defaults to dark", () => {
    expect(UI_THEME_DEFAULT).toBe("dark");
  });

  it("guards unknown values", () => {
    expect(isUiTheme("dark")).toBe(true);
    expect(isUiTheme("light")).toBe(true);
    expect(isUiTheme("system")).toBe(true);
    expect(isUiTheme("auto")).toBe(false);
    expect(isUiTheme(null)).toBe(false);
  });

  it("cycles dark → light → system → dark", () => {
    expect(nextUiTheme("dark")).toBe("light");
    expect(nextUiTheme("light")).toBe("system");
    expect(nextUiTheme("system")).toBe("dark");
  });

  it("resolves system from prefers-color-scheme", () => {
    expect(resolveUiTheme("light", true)).toBe("light");
    expect(resolveUiTheme("dark", false)).toBe("dark");
    expect(resolveUiTheme("system", true)).toBe("dark");
    expect(resolveUiTheme("system", false)).toBe("light");
  });
});
