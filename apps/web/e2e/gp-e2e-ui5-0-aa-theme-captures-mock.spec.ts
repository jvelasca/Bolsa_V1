/**
 * GP-E2E UI5-0 · capturas y medición AA por tema (H-21).
 *
 * El expediente de H-21 cita capturas claro/oscuro de cuatro superficies. Tres de las
 * parejas «dark» eran copias byte a byte de las «light» (mismo MD5): el tema no se había
 * aplicado, así que la evidencia no respaldaba una medición en oscuro. Este spec sustituye
 * esas capturas por unas producidas con el tema **forzado antes del arranque** y verifica
 * tres cosas que el cierre anterior daba por supuestas:
 *
 *   1. `<html data-theme>` toma el valor pedido antes de medir (si no, falla el test).
 *   2. axe (WCAG 2.0/2.1 A+AA) no deja violaciones `critical`/`serious` en ningún tema.
 *   3. La captura oscura **no** es idéntica a la clara (guarda contra el incidente).
 *
 * El tema no se resuelve por `prefers-color-scheme`: `applyUiThemeToDocument` escribe
 * `data-theme` desde `bolsa-ui-prefs-v1` (`ui-store`), de ahí que el init-script escriba esa
 * clave y no baste `emulateMedia`.
 *
 * Salidas (expediente, no baselines de `toHaveScreenshot`):
 *   `aa-{superficie}-{tema}.png` × 8 · `aa-axe-sweep.txt`
 *
 * Run (auto-arranca Vite; API simulada — no hace falta el stack Python):
 *   $env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-aa-theme-captures
 *
 * Sin entorno: skipped (igual que el resto de `apps/web/e2e`).
 */
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  e2eEnabled,
  E2E_SKIP_REASON,
  installApiMocks,
  installHoyPaperDayApiMocks,
} from "./fixtures";
import { E2E_ACCOUNT_ID } from "./helpers/ids";

/** Mismo encuadre que las capturas que ya vivían en el expediente. */
const VIEWPORT = { width: 1600, height: 1000 } as const;
const THEMES = ["light", "dark"] as const;
type Theme = (typeof THEMES)[number];

/** Clave del store de preferencias de UI (`ui-store.ts`). */
const UI_PREFS_STORAGE_KEY = "bolsa-ui-prefs-v1";

/** Raíz del repositorio: Playwright corre con cwd = apps/web. */
function repoRoot(): string {
  const cwd = process.cwd();
  return /apps[\\/]web$/.test(cwd) ? resolve(cwd, "../..") : cwd;
}

const EVIDENCE_DIR = resolve(
  repoRoot(),
  "docs/engineering/evidence/operativa-asesor-2026-11-15",
);

/**
 * Parte del día completo (mismo shape que `DailyOpsReportV1`).
 *
 * Sin este mock el catch-all de `installApiMocks` responde `{ data: [] }` y el Diario se
 * mediría en su estado de ausencia. Con él, la captura enseña el panel real: KPIs, canales
 * y semana. `tradesToday: []` es un cero **medido** (el parte llegó y no hubo operaciones),
 * no un hueco.
 */
function dailyOpsReportFixture() {
  return {
    schemaVersion: "daily_ops_report_v1",
    asOf: "2026-11-16",
    generatedAt: "2026-11-16T12:00:00.000Z",
    accountId: E2E_ACCOUNT_ID,
    summary: {
      cash: 100_000,
      totalEquity: 101_060,
      totalUnrealizedPnl: 60,
      positionsCount: 1,
    },
    ledgerToday: [],
    tradesToday: [],
    week: [
      {
        date: "2026-11-10",
        tradeCount: 0,
        ledgerCount: 0,
        balanceAfter: 100_400,
        netAmount: 0,
      },
      {
        date: "2026-11-11",
        tradeCount: 2,
        ledgerCount: 2,
        balanceAfter: 100_820,
        netAmount: 420,
      },
      {
        date: "2026-11-12",
        tradeCount: 1,
        ledgerCount: 1,
        balanceAfter: 100_650,
        netAmount: -170,
      },
      {
        date: "2026-11-13",
        tradeCount: 0,
        ledgerCount: 0,
        balanceAfter: 100_650,
        netAmount: 0,
      },
      {
        date: "2026-11-16",
        tradeCount: 1,
        ledgerCount: 1,
        balanceAfter: 101_060,
        netAmount: 410,
      },
    ],
    f3PendingCount: 0,
    channels: { alarma: 1, aviso: 2, none: 3 },
    opinions: [],
    notes: ["Cierre de sesión sin incidencias."],
    estudioStatus: "ok",
    estudioCount: 3,
  };
}

type Surface = {
  /** Nombre usado en el archivo de captura y en el barrido. */
  name: string;
  path: string;
  install: (page: Page) => Promise<void>;
  ready: (page: Page) => Promise<void>;
};

const SURFACES: readonly Surface[] = [
  {
    name: "asesor-cartera",
    path: "/research",
    install: (page) => installApiMocks(page),
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Asesor" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
  {
    name: "asesor-diario",
    path: "/research?tab=diario",
    install: async (page) => {
      // El catch-all se registra primero; el handler específico, después: Playwright
      // evalúa el último registrado primero y el Diario recibe el parte completo.
      await installApiMocks(page, { hoyDay: true });
      await page.route(/\/api\/accounts\/[^/]+\/daily-ops-report/, (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: dailyOpsReportFixture() }),
        }),
      );
    },
    ready: async (page) => {
      await expect(page.getByTestId("asesor-daily-ops")).toBeVisible({
        timeout: 15_000,
      });
      // El parte llegó de verdad: la semana se pinta y el hueco no existe.
      await expect(page.getByTestId("asesor-week-absent")).toHaveCount(0);
    },
  },
  {
    name: "mesa",
    path: "/mesa",
    install: installHoyPaperDayApiMocks,
    ready: async (page) => {
      await expect(page.getByTestId("mesa-hoy-page")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("hoy-inbox")).toBeVisible();
    },
  },
  {
    name: "backtests",
    path: "/backtests",
    install: (page) => installApiMocks(page),
    ready: async (page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "Laboratorio" }),
      ).toBeVisible({ timeout: 15_000 });
    },
  },
];

/** Fuerza el tema resuelto antes de que arranque la app. */
async function forceTheme(page: Page, theme: Theme) {
  await page.addInitScript(
    ({ key, value }) => {
      try {
        localStorage.setItem(key, value);
      } catch {
        /* sin storage: la aserción de data-theme lo detecta */
      }
    },
    {
      key: UI_PREFS_STORAGE_KEY,
      value: JSON.stringify({
        state: { uiTheme: theme, uiDensity: "comfortable" },
        version: 0,
      }),
    },
  );
  await page.emulateMedia({ colorScheme: theme });
}

function capturePath(surface: string, theme: Theme): string {
  return resolve(EVIDENCE_DIR, `aa-${surface}-${theme}.png`);
}

/** Devuelve las violaciones `critical`/`serious` con detalle accionable. */
async function auditCriticalSerious(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations
    .filter(
      (violation) =>
        violation.impact === "critical" || violation.impact === "serious",
    )
    .map(
      (violation) =>
        `${violation.id} [${violation.impact}] ×${violation.nodes.length}`,
    );
}

/** Líneas del barrido, en el orden en que se miden. */
const sweep: string[] = [];

test.describe.configure({ mode: "serial" });

test.describe("GP-E2E UI5-0 — capturas y AA por tema (H-21)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await page.setViewportSize(VIEWPORT);
  });

  for (const surface of SURFACES) {
    for (const theme of THEMES) {
      test(`AA · ${surface.name} @${theme}`, async ({ page }) => {
        await surface.install(page);
        await forceTheme(page, theme);
        await page.goto(surface.path);

        // El tema tiene que estar aplicado ANTES de medir: sin esto, una captura
        // «dark» podría ser en realidad la clara y el expediente mentiría.
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

        await surface.ready(page);

        const blocking = await auditCriticalSerious(page);
        sweep.push(
          `[${theme}][${surface.name}] graves=${blocking.length} · ${
            blocking.length ? blocking.join(", ") : "ninguna"
          }`,
        );
        expect(
          blocking,
          `[${theme}][${surface.name}] ${blocking.join(", ")}`,
        ).toEqual([]);

        mkdirSync(EVIDENCE_DIR, { recursive: true });
        await page.screenshot({
          path: capturePath(surface.name, theme),
          fullPage: false,
          animations: "disabled",
        });
      });
    }
  }

  test.afterAll(() => {
    if (!e2eEnabled()) return;
    mkdirSync(EVIDENCE_DIR, { recursive: true });

    writeFileSync(
      resolve(EVIDENCE_DIR, "aa-axe-sweep.txt"),
      `${sweep.join("\n")}\n`,
      "utf8",
    );

    // Guarda del incidente: si el tema no cambió nada visible, la pareja es idéntica.
    // Con una corrida filtrada (`-g`) pueden faltar archivos: se comparan solo las parejas
    // completas, para no convertir un filtro en un ENOENT.
    for (const surface of SURFACES) {
      const lightPath = capturePath(surface.name, "light");
      const darkPath = capturePath(surface.name, "dark");
      if (!existsSync(lightPath) || !existsSync(darkPath)) continue;
      const light = readFileSync(lightPath);
      const dark = readFileSync(darkPath);
      expect(
        dark.equals(light),
        `${surface.name}: la captura oscura es idéntica a la clara — el tema no se aplicó`,
      ).toBe(false);
    }
  });
});
