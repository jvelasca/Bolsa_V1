/**
 * GP-S5 · Certificación global del rediseño S1–S4.
 *
 * Demuestra, con un mock determinista, que la recomendación (S1), el contexto
 * técnico (S2), el estado de cartera (S3) y la vía de actuación (S4) cuentan la
 * misma historia en los seis escenarios de producto, en las tres superficies y
 * en los tres cortes de ancho. Las capturas van al expediente
 * `docs/engineering/evidence/s5-rediseno-2026-11-12/`.
 *
 * No toca motor, decisión, contrato ni migraciones: solo lee UI y datos mock.
 *
 * Run (auto-arranca Vite; API simulada — no hace falta el stack Python):
 *   $env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-s5-rediseno
 * Contra un servidor ya levantado:
 *   $env:PLAYWRIGHT_BASE_URL="http://localhost:5173"; pnpm --filter @bolsa/web exec playwright test gp-s5-rediseno
 *
 * Sin entorno: skipped (igual que el resto de `apps/web/e2e`).
 */
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { e2eEnabled, E2E_SKIP_REASON } from "./fixtures";
import { E2E_SYMBOL } from "./helpers/ids";
import { seedMercadoBrowserState } from "./helpers/mercado";
import {
  S5_SCENARIOS,
  installS5Scenario,
  openS5MaximizedDecision,
  saveS5Screenshot,
} from "./helpers/s5-decision-scenarios";

const DESKTOP = { width: 1600, height: 1000 } as const;
const MEDIUM = { width: 1200, height: 900 } as const;
const NARROW = { width: 403, height: 900 } as const;

/** Falla con detalle accionable si hay violaciones `critical`/`serious`. */
async function expectNoCriticalSerious(page: Page, context: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter(
    (violation) =>
      violation.impact === "critical" || violation.impact === "serious",
  );
  const detail = blocking
    .map(
      (violation) =>
        `· ${violation.id} [${violation.impact}] ×${violation.nodes.length} — ${violation.help}\n    ${violation.nodes
          .slice(0, 3)
          .map((node) => node.target.join(" "))
          .join("\n    ")}`,
    )
    .join("\n");
  expect(blocking, `[${context}] ${detail}`).toEqual([]);
}

function gridColumns(value: string): number {
  return value.trim().split(/\s+/).filter(Boolean).length;
}

test.describe("GP-S5 · certificación del rediseño S1–S4", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await page.setViewportSize(DESKTOP);
  });

  for (const scenario of S5_SCENARIOS) {
    test(`S5.${scenario.id} · ${scenario.title}`, async ({ page }) => {
      await installS5Scenario(page, scenario);
      await openS5MaximizedDecision(page);

      const expected = scenario.expect;
      const panel = page.getByTestId("trading-operativa-panel");
      await expect(panel).toHaveAttribute("data-surface", "maximized");

      // S1 + S3 + S4 en el hero: una sola lectura.
      const hero = page.getByTestId("operativa-recomendacion-principal");
      await expect(hero).toHaveAttribute("data-state", expected.state);
      await expect(hero).toHaveAttribute(
        "data-action-hint",
        expected.actionHint,
      );
      const stateChip = page.getByTestId("operativa-cartera-state");
      await expect(stateChip).toHaveAttribute("data-state", expected.state);
      await expect(stateChip).toHaveText(expected.stateLabel);

      const actionChip = page
        .getByTestId("operativa-actuacion")
        .locator("[data-action-hint]");
      await expect(actionChip).toHaveText(expected.actionLabel);
      if (expected.blockedReason) {
        await expect(actionChip).toHaveAttribute(
          "data-blocked-reason",
          expected.blockedReason,
        );
      } else {
        await expect(actionChip).not.toHaveAttribute(
          "data-blocked-reason",
          /.+/,
        );
      }

      // Un solo dictamen, dentro del hero, en la etiqueta canónica de S1.
      await expect(page.getByTestId("operativa-dictamen")).toHaveCount(1);
      const dictamen = hero.getByTestId("operativa-dictamen");
      if (expected.stanceLabel) {
        await expect(dictamen).toContainText(expected.stanceLabel);
      } else {
        await expect(dictamen).toContainText("Sin recomendación todavía");
      }
      await expect(hero).not.toContainText("Sobrecomprado");
      await expect(hero).not.toContainText(/sin posición/i);
      await expect(page.getByTestId("operativa-recomendacion-aviso")).toContainText(
        "la recomendación no ejecuta",
      );

      // El contexto técnico informa y no añade una segunda recomendación.
      await expect(
        page.getByTestId("operativa-contexto-tecnico"),
      ).toContainText("Informan; no autorizan entradas");

      // Coherencia con el cockpit real (ACCIÓN).
      const cockpit = page.getByTestId("operativa-cockpit");
      await expect(cockpit).toHaveAttribute(
        "data-phase",
        expected.cockpitPhase,
      );
      await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
        0,
      );

      const propose = page.getByTestId("operativa-cockpit-cta-preparar");
      if (expected.proposeEnabled) {
        await expect(propose).toBeVisible();
        await expect(propose).toBeEnabled();
      } else if (scenario.hasPosition) {
        // Con posición, ACCIÓN no ofrece entrada: la gestión de salida vive en su
        // propia zona. El cockpit declara la postura, nunca «Comprar».
        await expect(propose).toHaveCount(0);
        await expect(cockpit).toContainText(
          /Mantener|Revisar|Proteger|Reducir|Vender/,
        );
      } else if (!scenario.portfolioMeasured) {
        await expect(propose).toHaveCount(0);
        await expect(page.getByTestId("operativa-panel-unmeasured")).toBeVisible();
        await expect(
          page.getByTestId("operativa-cockpit-unmeasured"),
        ).toBeVisible();
      } else {
        // Entradas bloqueadas: el CTA existe, está deshabilitado y su etiqueta es
        // el propio aviso («Entradas bloqueadas»).
        await expect(propose).toBeVisible();
        await expect(propose).toBeDisabled();
        await expect(propose).toContainText("Entradas bloqueadas");
      }

      if (scenario.hasPosition) {
        await expect(
          page.getByTestId("position-operational-star-card"),
        ).toBeVisible();
      } else if (scenario.portfolioMeasured) {
        await expect(page.getByTestId("entry-decision-surface")).toBeVisible();
      }

      await saveS5Screenshot(
        page,
        `s5-${scenario.id}-1600x1000.png`,
      );

      await expectNoCriticalSerious(page, `maximizada · ${scenario.id}`);
    });
  }

  test("S5.responsive · 3 → 2 → 1 columnas y superficie estrecha", async ({
    page,
  }) => {
    const scenario = S5_SCENARIOS[0]!;
    await installS5Scenario(page, scenario);
    await openS5MaximizedDecision(page);

    const grid = page.locator(".operativa-maximized-grid");
    await expect(grid).toBeVisible();
    const columnsAt = async () =>
      gridColumns(
        (await grid.evaluate(
          (el) => getComputedStyle(el).gridTemplateColumns,
        )) as string,
      );

    await expect.poll(columnsAt, { timeout: 5_000 }).toBe(3);
    await saveS5Screenshot(page, "s5-responsive-1600x1000.png");

    await page.setViewportSize(MEDIUM);
    await expect.poll(columnsAt, { timeout: 5_000 }).toBe(2);
    await saveS5Screenshot(page, "s5-responsive-1200x900.png");

    await page.setViewportSize(NARROW);
    await expect(page.getByTestId("trading-operativa-panel")).toHaveAttribute(
      "data-surface",
      "narrow",
    );
    await expect(
      page.getByTestId("operativa-recomendacion-principal"),
    ).toHaveCount(0);
    await expect(page.getByTestId("trading-operativa-panel")).toBeVisible();
    await saveS5Screenshot(page, "s5-responsive-403x900.png");
  });

  test("S5.superficie dock · conserva la composición anterior", async ({
    page,
  }) => {
    const scenario = S5_SCENARIOS[0]!;
    await installS5Scenario(page, scenario);
    await seedMercadoBrowserState(page, { operativaMaximized: false });
    await page.goto("/trading");

    const panel = page.getByTestId("trading-operativa-panel");
    await expect(panel).toBeVisible({ timeout: 25_000 });
    await expect(panel).toHaveAttribute("data-surface", "dock");
    await expect(
      page.getByTestId("operativa-recomendacion-principal"),
    ).toHaveCount(0);

    // El dock abre solo Recomendación: el dictamen compacto vive ahí y Evidencia
    // ya no lo repite (una sola lectura por pantalla).
    const recomendacion = page.getByTestId("operativa-section-recomendacion");
    await expect(recomendacion).toBeVisible();
    await expect(recomendacion).toHaveAttribute("data-variant", "group");
    await expect(
      recomendacion.locator('[data-testid="operativa-dictamen"]'),
    ).toHaveCount(1);
    await expect(
      recomendacion.locator('[data-testid="operativa-cockpit"]'),
    ).toHaveCount(1);

    const evidencia = page.getByTestId("operativa-section-evidencia");
    await expect(evidencia).toBeVisible();
    await expect(
      evidencia.getByRole("button").first(),
    ).toHaveAttribute("aria-expanded", "false");
    await expect(
      evidencia.locator('[data-testid="operativa-dictamen"]'),
    ).toHaveCount(0);

    await saveS5Screenshot(page, "s5-superficie-dock-1600x1000.png");
  });

  test("S5.S2 · estructura calculada declara que informa, no autoriza", async ({
    page,
  }) => {
    const scenario = S5_SCENARIOS[0]!;
    await installS5Scenario(page, scenario);
    await openS5MaximizedDecision(page);

    const readout = page.getByTestId("market-structure-readout");
    await expect(readout).toBeVisible({ timeout: 20_000 });
    await expect(readout).toHaveAttribute("data-status", "ok");
    await expect(
      page.getByTestId("market-structure-strength"),
    ).toBeVisible();
    await expect(readout).not.toContainText("COMPRAR");

    await saveS5Screenshot(page, "s5-s2-contexto-tecnico-1600x1000.png");
  });

  test("S5.S3 · Asesor/Cartera clasifica la misma cartera", async ({ page }) => {
    const withPosition = S5_SCENARIOS.find(
      (scenario) => scenario.id === "posicion_con_respaldo",
    )!;
    await installS5Scenario(page, withPosition);
    await page.goto("/research?tab=cartera");

    const cartera = page.getByTestId("asesor-cartera");
    await expect(cartera).toBeVisible({ timeout: 25_000 });
    const row = page.getByTestId("asesor-cartera-row").filter({
      hasText: E2E_SYMBOL,
    });
    await expect(row).toHaveAttribute("data-state", "posicion_abierta");
    await expect(page.getByTestId("asesor-cartera-totals")).toBeVisible();
    await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(
      0,
    );

    await saveS5Screenshot(page, "s5-s3-asesor-cartera-posicion-1600x1000.png");
    await expectNoCriticalSerious(page, "asesor · cartera");
  });

  test("S5.S3 · Asesor/Cartera sin posición no inventa respaldo", async ({
    page,
  }) => {
    const withoutPosition = S5_SCENARIOS[0]!;
    await installS5Scenario(page, withoutPosition);
    await page.goto("/research?tab=cartera");

    await expect(page.getByTestId("asesor-cartera")).toBeVisible({
      timeout: 25_000,
    });
    const row = page.getByTestId("asesor-cartera-row").filter({
      hasText: E2E_SYMBOL,
    });
    await expect(row).toHaveAttribute("data-state", "recomendacion_favorable");
    await expect(row).not.toContainText("Sobrecomprado");

    await saveS5Screenshot(page, "s5-s3-asesor-cartera-sin-posicion.png");
  });
});
