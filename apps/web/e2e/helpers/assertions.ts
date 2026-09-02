/**
 * E2E assertion layers (V1.77 operational · V1.79 identity/financial/certification).
 */
import { expect, type Page } from "@playwright/test";
import type { MercadoInstrumentSlice } from "./ids";

function formatLevelAssert(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return value.toFixed(2);
}

/**
 * V1.79 — identidad chart + cockpit + IDs.
 * Extraído de assertOperationalTruth; no endurece defaults de V1.77/V1.78.
 */
export async function assertIdentityTruth(
  page: Page,
  slice: MercadoInstrumentSlice,
): Promise<void> {
  const chartZone = page.getByTestId("chart-indicators-zone");
  await expect(chartZone).toBeVisible({ timeout: 20_000 });
  await expect(chartZone).toHaveAttribute(
    "data-instrument-id",
    slice.instrumentId,
  );

  const cockpit = page.getByTestId("operativa-cockpit");
  await expect(cockpit).toBeVisible({ timeout: 20_000 });
  await expect(cockpit).toHaveAttribute(
    "data-instrument-id",
    slice.instrumentId,
  );
  await expect(cockpit).toHaveAttribute("data-symbol", slice.symbol);
  await expect(cockpit).toHaveAttribute("data-position-id", slice.positionId);
  await expect(cockpit).toHaveAttribute("data-phase", "posicion");
  if (slice.tradePlanId) {
    await expect(cockpit).toHaveAttribute(
      "data-trade-plan-id",
      slice.tradePlanId,
    );
  }
  if (slice.decisionId) {
    await expect(cockpit).toHaveAttribute("data-decision-id", slice.decisionId);
  }
}

/**
 * V1.77 — identidad + verdad operativa (Mercado posición).
 * Extiende el patrón assertPositionIdentity de GP-V173.
 * Defaults intactos para GP-V177/V178.
 */
export async function assertOperationalTruth(
  page: Page,
  slice: MercadoInstrumentSlice,
  opts?: {
    expectRecon?: "CLEAN" | "CRITICAL" | "ATTENTION" | null;
    expectFreshness?: "current" | "stale" | null;
    /** Default false — WHY needs study wire; opt-in per GP. */
    openWhy?: boolean;
  },
): Promise<void> {
  await assertIdentityTruth(page, slice);

  await expect(
    page.getByTestId("position-operational-star-card"),
  ).toBeVisible();
  await expect(page.getByTestId("entry-decision-surface")).toHaveCount(0);

  const stop = formatLevelAssert(slice.levels?.currentStop);
  const t1 = formatLevelAssert(slice.levels?.target1);
  const t2 = formatLevelAssert(slice.levels?.target2);
  if (stop) {
    await expect(page.getByTestId("position-decision-stop")).toContainText(
      stop,
    );
  }
  if (t1) {
    await expect(page.getByTestId("position-decision-t1")).toContainText(t1);
  }
  if (t2) {
    await expect(page.getByTestId("position-decision-t2")).toContainText(t2);
  }

  const povAction = page.getByTestId("operativa-cockpit-pov-action");
  await expect(povAction).toBeVisible();
  await expect(povAction).not.toContainText(/comprar/i);

  if (opts?.expectRecon) {
    await expect(page.getByTestId("operativa-cockpit-recon")).toHaveAttribute(
      "data-recon",
      opts.expectRecon,
    );
  }

  if (opts?.expectFreshness) {
    const badge = page.getByTestId("chart-data-status");
    await expect(badge).toHaveAttribute(
      "data-instrument-id",
      slice.instrumentId,
    );
    await expect(badge).toHaveAttribute(
      "data-freshness-status",
      opts.expectFreshness,
    );
  }

  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);

  if (opts?.openWhy === true) {
    const whyToggle = page
      .getByTestId("position-decision-why-toggle")
      .or(page.getByTestId("operativa-cockpit-why"));
    if ((await whyToggle.count()) > 0) {
      await whyToggle.first().click();
      await expect(page.getByTestId("decision-explain-panel")).toBeVisible({
        timeout: 10_000,
      });
    }
  }
}

/** V1.79 — P&L / R / remaining (HUD + data-remaining-quantity). */
export async function assertFinancialTruth(
  page: Page,
  opts: {
    remainingQuantity: number;
    unrealizedR?: number;
  },
): Promise<void> {
  const povState = page.getByTestId("operativa-cockpit-pov-state");
  await expect(povState).toHaveAttribute(
    "data-remaining-quantity",
    String(opts.remainingQuantity),
  );
  await expect(page.getByTestId("position-decision-price")).toBeVisible();
  const pnl = page.getByTestId("position-decision-pnl");
  await expect(pnl).toBeVisible();
  if (opts.unrealizedR != null) {
    const sign = opts.unrealizedR > 0 ? "+" : "";
    await expect(pnl).toContainText(`${sign}${opts.unrealizedR.toFixed(2)}R`);
  }
}

/** V1.79 — identity + operational + financial + POV stage. Solo GP-V179. */
export async function assertPositionCertification(
  page: Page,
  slice: MercadoInstrumentSlice,
  opts: {
    operatingState: string;
    actionText: RegExp;
    remainingQuantity: number;
    unrealizedR?: number;
    expectRecon?: "CLEAN" | "CRITICAL" | "ATTENTION" | null;
  },
): Promise<void> {
  await assertOperationalTruth(page, slice, {
    expectRecon: opts.expectRecon ?? "CLEAN",
    expectFreshness: "current",
  });
  await assertFinancialTruth(page, {
    remainingQuantity: opts.remainingQuantity,
    unrealizedR: opts.unrealizedR,
  });
  const povState = page.getByTestId("operativa-cockpit-pov-state");
  await expect(povState).toHaveAttribute("data-pov-state", opts.operatingState);
  await expect(page.getByTestId("operativa-cockpit-pov-action")).toContainText(
    opts.actionText,
  );
  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);
}

/** V1.78 — entry-only candidato (sin posición). */
export async function assertEntryCandidateTruth(
  page: Page,
  opts: { instrumentId: string; symbol: string },
): Promise<void> {
  const cockpit = page.getByTestId("operativa-cockpit");
  await expect(cockpit).toBeVisible({ timeout: 20_000 });
  await expect(cockpit).toHaveAttribute(
    "data-instrument-id",
    opts.instrumentId,
  );
  await expect(cockpit).toHaveAttribute("data-symbol", opts.symbol);
  await expect(cockpit).not.toHaveAttribute("data-position-id");
  await expect(page.getByTestId("entry-decision-surface")).toBeVisible();
  await expect(page.getByTestId("position-operational-star-card")).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);
}

/** V1.78 — POV stage + identidad posición + 0 COMPRAR. */
export async function assertPovOperatingStage(
  page: Page,
  slice: MercadoInstrumentSlice,
  opts: {
    operatingState: string;
    actionText: RegExp;
    expectRecon?: "CLEAN" | "CRITICAL" | "ATTENTION" | null;
  },
): Promise<void> {
  await assertOperationalTruth(page, slice, {
    expectRecon: opts.expectRecon ?? "CLEAN",
    expectFreshness: "current",
  });
  const povState = page.getByTestId("operativa-cockpit-pov-state");
  await expect(povState).toHaveAttribute("data-pov-state", opts.operatingState);
  await expect(page.getByTestId("operativa-cockpit-pov-action")).toContainText(
    opts.actionText,
  );
  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);
}

/** V1.79 CLOSED — no HUD abierta · 0 COMPRAR · identidad en Journal. */
export async function assertClosedPositionTruth(
  page: Page,
  opts: { instrumentId: string; decisionId: string },
): Promise<void> {
  await expect(page.getByTestId("position-operational-star-card")).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);
  const cockpit = page.getByTestId("operativa-cockpit");
  if ((await cockpit.count()) > 0) {
    await expect(cockpit).toHaveAttribute(
      "data-instrument-id",
      opts.instrumentId,
    );
    await expect(cockpit).not.toHaveAttribute("data-position-id");
  }
  await page.goto("/decision-journal");
  await expect(page.getByTestId("decision-journal")).toBeVisible({
    timeout: 20_000,
  });
  const studyRow = page.getByTestId("study-row");
  await expect(studyRow).toBeVisible({ timeout: 20_000 });
  await expect(studyRow).toHaveAttribute("data-decision-id", opts.decisionId);
  await expect(studyRow).toHaveAttribute(
    "data-instrument-id",
    opts.instrumentId,
  );
  await expect(studyRow).toContainText("AAPL");
  await expect(page.getByRole("button", { name: /^COMPRAR$/i })).toHaveCount(0);
}
