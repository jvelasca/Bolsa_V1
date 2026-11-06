/**
 * GP-E2E-OVERVIEW-ACCOUNT-ERROR — U-1: un fallo de `/accounts` NO es «no hay cuentas».
 *
 * Cubre en navegador lo que el test de unidad de `dashboard-page.test.tsx` ya fija en
 * jsdom: sobre `/overview`, con la API mockeada, los cinco estados de la cuenta activa y
 * del ledger se distinguen y se rotulan distinto.
 *
 *   1. `/accounts` 500  → error + «Reintentar», SIN «Nueva demo», y el ledger NO se
 *                          consulta (no hay cuenta activa) ni se disfraza de
 *                          «Sin movimientos».
 *   2. Reintentar       → recupera la cuenta activa y el estado vacío REAL del ledger.
 *   3. Ledger 500       → error propio (la cuenta sí cargó) y reintento que pinta filas.
 *   4. `/accounts` `[]` → estado vacío REAL: sí ofrece «Nueva demo».
 *
 * El fallo de la cuenta tiene que ser un error y no un vacío: ofrecer «Nueva demo» cuando
 * `/accounts` falló empuja a crear una cuenta duplicada porque el sistema no pudo
 * consultar las existentes.
 *
 * Patrón gemelo de `gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` (skip-by-default).
 * UI pura: no toca motor (`Delta motor = 0`).
 *
 * Run (auto-starts Vite; API mocked — no Python stack):
 *   E2E_RUN=1 pnpm e2e -- gp-e2e-overview-account-error
 * Against an existing dev server:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e -- gp-e2e-overview-account-error
 *
 * Default (no env): skipped.
 */
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { e2eEnabled, E2E_SKIP_REASON, installApiMocks } from "./fixtures";
import { E2E_ACCOUNT_ID, E2E_INSTRUMENT_ID } from "./helpers/ids";

const ACCOUNTS_ROUTE = /\/api\/accounts(\?.*)?$/;
const LEDGER_ROUTE = /\/api\/accounts\/[^/]+\/ledger(\?.*)?$/;

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

function ledgerEntry() {
  return {
    id: "e2e-ledger-deposit-1",
    accountId: E2E_ACCOUNT_ID,
    portfolioId: null,
    type: "deposit" as const,
    amount: 10_000,
    currency: "EUR",
    balanceAfter: 110_000,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: "AAA",
    quantity: null,
    price: null,
    referenceType: "manual",
    referenceId: null,
    description: "Ingreso sembrado por E2E",
    executedAt: "2026-10-01T09:00:00.000Z",
  };
}

test.describe("GP-E2E-OVERVIEW-ACCOUNT-ERROR — U-1 (error ≠ ausencia)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!e2eEnabled(), E2E_SKIP_REASON);
    await installApiMocks(page);
  });

  test("un fallo de /accounts no se lee como «sin cuenta» ni como «sin movimientos»", async ({
    page,
  }) => {
    const ledgerCalls: string[] = [];
    page.on("request", (request) => {
      if (LEDGER_ROUTE.test(request.url())) ledgerCalls.push(request.url());
    });
    await page.route(ACCOUNTS_ROUTE, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: "{}",
      }),
    );

    await page.goto("/overview");
    await expect(
      page.getByRole("heading", { level: 1, name: "Overview" }),
    ).toBeVisible({ timeout: 15_000 });

    // El error se declara como error…
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "No se pudieron cargar tus cuentas." }),
    ).toBeVisible();
    // …y no induce a crear una demo que quizá ya existe.
    await expect(page.getByRole("button", { name: "Nueva demo" })).toHaveCount(
      0,
    );
    await expect(
      page.getByRole("button", { name: "Reintentar" }),
    ).toBeVisible();
    await expect(
      page.getByText(/No se puede afirmar que no tengas ninguna/i),
    ).toBeVisible();

    // El ledger NO se rotula como vacío: sin cuenta activa la causa es de la cuenta.
    await expect(
      page.getByText(/no se pudo cargar la cuenta activa/i),
    ).toBeVisible();
    await expect(page.getByText(/^Sin movimientos\./)).toHaveCount(0);

    // Sin cuenta activa no hay ledger que consultar (la query está deshabilitada).
    await page.waitForTimeout(500);
    expect(ledgerCalls, "no se consulta el ledger sin cuenta activa").toEqual(
      [],
    );

    await expectNoCriticalSerious(page, "/overview (error de /accounts)");
  });

  test("Reintentar recupera la cuenta activa y el estado vacío real del ledger", async ({
    page,
  }) => {
    let failAccounts = true;
    await page.route(ACCOUNTS_ROUTE, (route) =>
      failAccounts
        ? route.fulfill({
            status: 500,
            contentType: "application/json",
            body: "{}",
          })
        : route.fallback(),
    );

    await page.goto("/overview");
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "No se pudieron cargar tus cuentas." }),
    ).toBeVisible();

    failAccounts = false;
    await page.getByRole("button", { name: "Reintentar" }).click();

    // La cuenta activa vuelve a pintarse…
    await expect(
      page.getByText(/Toda la app opera con esta cuenta/),
    ).toBeVisible();
    await expect(page.getByText(/Movimientos de «E2E Demo»/)).toBeVisible();
    await expect(
      page.getByText("No se pudieron cargar tus cuentas."),
    ).toHaveCount(0);
    // …y ahora sí, el vacío del ledger es un hecho recibido, no un fallo disfrazado.
    await expect(page.getByText(/^Sin movimientos\./)).toBeVisible();

    await expectNoCriticalSerious(page, "/overview (recuperado)");
  });

  test("un fallo del ledger con cuentas sanas se rotula como error y se reintenta", async ({
    page,
  }) => {
    let failLedger = true;
    await page.route(LEDGER_ROUTE, (route) =>
      failLedger
        ? route.fulfill({
            status: 500,
            contentType: "application/json",
            body: "{}",
          })
        : route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ data: [ledgerEntry()], tradeFeesTotal: 0 }),
          }),
    );

    await page.goto("/overview");
    await expect(
      page.getByText(/Toda la app opera con esta cuenta/),
    ).toBeVisible({ timeout: 15_000 });

    const ledgerAlert = page
      .getByRole("alert")
      .filter({ hasText: "No se pudieron cargar los movimientos." });
    await expect(ledgerAlert).toBeVisible();
    await expect(page.getByText(/^Sin movimientos\./)).toHaveCount(0);
    // La cuenta cargó: el error del ledger no puede colarse como error de cuenta.
    await expect(
      page.getByText(/No se pudieron cargar tus cuentas/i),
    ).toHaveCount(0);

    await expectNoCriticalSerious(page, "/overview (error de ledger)");

    failLedger = false;
    await ledgerAlert.getByRole("button", { name: "Reintentar" }).click();

    await expect(ledgerAlert).toHaveCount(0);
    await expect(page.getByRole("listitem")).toHaveCount(1);
    await expect(page.getByRole("listitem")).toContainText("Depósito inicial");
  });

  test("una respuesta sana SIN cuentas sí ofrece «Nueva demo»", async ({
    page,
  }) => {
    await page.route(ACCOUNTS_ROUTE, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [] }),
      }),
    );

    await page.goto("/overview");
    await expect(page.getByText(/No hay cuenta activa/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByRole("button", { name: "Nueva demo" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Reintentar" })).toHaveCount(
      0,
    );
    // Vacío REAL: el ledger tampoco tiene movimientos, y eso sí es un hecho.
    await expect(page.getByText(/^Sin movimientos\./)).toBeVisible();

    await expectNoCriticalSerious(page, "/overview (vacío real)");
  });
});
