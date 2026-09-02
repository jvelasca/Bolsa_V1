/**
 * V1.82 — Playwright route installers (API mocks for smoke / mock journeys).
 */
import type { Page } from "@playwright/test";
import {
  resetE2eMockRuntimeFlags,
  setE2eMockDeskMode,
  setE2eMockPositionStage,
  setMercadoMockWorkspaceDocument,
} from "./e2e-mock-runtime";
import {
  jsonResponse,
  routeBody,
  type E2eMockRouteOpts,
} from "./e2e-mock-routes";

/** Intercept /api/* so smoke tests run without the Python stack. */
export async function installApiMocks(
  page: Page,
  opts?: E2eMockRouteOpts,
): Promise<void> {
  await page.route(/\/api\//, async (route) => {
    await route.fulfill(jsonResponse(routeBody(route, opts)));
  });
}

/** Mercado DECISIÓN + gráfico con posición protegida (GP-E2E-03 / GP-V164-UI-03 mock). */
export async function installMercadoApiMocks(page: Page): Promise<void> {
  await installApiMocks(page, { mercado: true });
}

/** Mercado multi-instrumento (≥3 posiciones + Entry-only NVDA). */
export async function installMercadoMultiApiMocks(page: Page): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  resetE2eMockRuntimeFlags();
  await installApiMocks(page, { mercado: true, multi: true });
}

/** V1.77 — Session reliability journey (multi + mutable stale/UNKNOWN/recon). */
export async function installSessionReliabilityMocks(
  page: Page,
): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  resetE2eMockRuntimeFlags();
  await installApiMocks(page, { mercado: true, multi: true });
}

/** V1.78 — Golden MERCADO→EXIT (multi + deskMode/positionStage mutables). */
export async function installGoldenSessionMocks(page: Page): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  resetE2eMockRuntimeFlags();
  await installApiMocks(page, { mercado: true, multi: true });
}

/** V1.79 — Stateful AAPL lifecycle (Hoy + Mercado, no multi). */
export async function installStatefulLifecycleMocks(page: Page): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  resetE2eMockRuntimeFlags();
  setE2eMockDeskMode("lifecycle");
  setE2eMockPositionStage("candidate");
  await installApiMocks(page, { mercado: true });
}

/** Hoy Paper Autonomous Day — autoDesk + T1 AAPL + entry MSFT + Mercado wire. */
export async function installHoyPaperDayApiMocks(page: Page): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  await installApiMocks(page, { hoyDay: true });
}

/**
 * V1.75 — Chaos & stale → no-execute (helper separado; no usa hoyDay).
 * ENTRY_STALE_DATA · incidente abierto · data-status stale.
 * UNKNOWN order vive en installUnknownOrderMocks (V1.76).
 */
export async function installHoyStaleNoExecuteMocks(page: Page): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  await installApiMocks(page, { hoyStale: true });
}

/** V1.76 — UNKNOWN order aislado (sin stale, sin incidente). */
export async function installUnknownOrderMocks(page: Page): Promise<void> {
  setMercadoMockWorkspaceDocument(null);
  await installApiMocks(page, { hoyUnknown: true });
}
