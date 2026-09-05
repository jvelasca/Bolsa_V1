/**
 * V2.9 — cabin certification helpers.
 * Layout zoom ≠ Chrome UI chrome zoom. Viewport CSS shrink + deviceScaleFactor.
 */
import {
  expect,
  type Browser,
  type Locator,
  type Page,
} from "@playwright/test";

export const CABIN_VIEWPORTS = [
  { name: "desktop", width: 1920, height: 1080 },
  { name: "laptop", width: 1366, height: 768 },
  { name: "tablet", width: 1024, height: 768 },
] as const;

export type CabinViewport = (typeof CABIN_VIEWPORTS)[number];

/** CSS layout equivalent of browser zoom: fewer CSS px in the same window. */
export function cssViewportForZoom(
  width: number,
  height: number,
  zoomPct: number,
): { width: number; height: number; deviceScaleFactor: number } {
  const scale = zoomPct / 100;
  return {
    width: Math.max(1, Math.round(width / scale)),
    height: Math.max(1, Math.round(height / scale)),
    deviceScaleFactor: scale,
  };
}

export async function openAutoDesk(page: Page) {
  const desk = page.getByTestId("auto-desk-panel");
  const count = await desk.count();
  if (count === 0) return null;
  const summary = desk.getByTestId("auto-desk-summary");
  const open = await desk.evaluate((el) => (el as HTMLDetailsElement).open);
  if (!open) await summary.click();
  return desk;
}

export async function newCabinPage(
  browser: Browser,
  opts: {
    width: number;
    height: number;
    zoomPct?: number;
    colorScheme?: "light" | "dark";
    hasTouch?: boolean;
    isMobile?: boolean;
  },
) {
  const zoomPct = opts.zoomPct ?? 100;
  const css = cssViewportForZoom(opts.width, opts.height, zoomPct);
  const context = await browser.newContext({
    viewport: { width: css.width, height: css.height },
    deviceScaleFactor: css.deviceScaleFactor,
    colorScheme: opts.colorScheme,
    hasTouch: opts.hasTouch,
    isMobile: opts.isMobile,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  return { context, page };
}

export async function assertNoHorizontalOverflow(locator: Locator) {
  const overflow = await locator.evaluate((el) => {
    const node = el as HTMLElement;
    return {
      scrollWidth: node.scrollWidth,
      clientWidth: node.clientWidth,
    };
  });
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

function parseRgb(
  input: string,
): { r: number; g: number; b: number; a: number } | null {
  const m = input.match(
    /rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/,
  );
  if (!m) return null;
  return {
    r: Number(m[1]),
    g: Number(m[2]),
    b: Number(m[3]),
    a: m[4] == null ? 1 : Number(m[4]),
  };
}

function srgbChannel(c: number): number {
  const x = c / 255;
  return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(rgb: { r: number; g: number; b: number }): number {
  return (
    0.2126 * srgbChannel(rgb.r) +
    0.7152 * srgbChannel(rgb.g) +
    0.0722 * srgbChannel(rgb.b)
  );
}

function contrastRatio(fg: string, bg: string): number | null {
  const a = parseRgb(fg);
  const b = parseRgb(bg);
  if (!a || !b || a.a < 0.4) return null;
  const l1 = relativeLuminance(a);
  const l2 = relativeLuminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

async function effectiveBackground(locator: Locator): Promise<string> {
  return locator.evaluate((el) => {
    let node: HTMLElement | null = el as HTMLElement;
    while (node) {
      const bg = getComputedStyle(node).backgroundColor;
      const parsed = bg.match(
        /rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/,
      );
      const a = parsed?.[4] == null ? 1 : Number(parsed[4]);
      if (parsed && a > 0.4) return bg;
      node = node.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor;
  });
}

/** WCAG AA-ish floor for operational chrome (4.5:1). Transparent/low-alpha skipped. */
export async function assertReadableContrast(locator: Locator, minRatio = 4.5) {
  await expect(locator).toBeVisible();
  const color = await locator.evaluate((el) => getComputedStyle(el).color);
  const bg = await effectiveBackground(locator);
  const ratio = contrastRatio(color, bg);
  if (ratio == null) return;
  expect(ratio).toBeGreaterThanOrEqual(minRatio);
}
