/**
 * Tests — sección de cabina de evidencia AUTO (procedencia + import manual).
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { OpsAutoEvidenceSection } from "./auto-evidence-section";
import {
  AUTO_EVIDENCE_ARTIFACT_SCHEMA,
  AUTO_EVIDENCE_CALIBRATION_KEYS,
} from "./auto-evidence-report";
import {
  AUTO_EVIDENCE_ARCHIVE_KEY,
  useAutoEvidenceArchiveStore,
} from "@/stores/auto-evidence-archive-store";

function artifactJson(overrides: Record<string, unknown> = {}): string {
  const origin =
    (overrides.materialOrigin as string | undefined) ?? "paper_real";
  const materialOverride =
    (overrides.material as Record<string, unknown> | undefined) ?? {};
  // `material` y `materialOrigin` se gestionan aparte para que la procedencia sea COHERENTE
  // entre raíz y material (P3-2): un override de `materialOrigin` manda en ambos sitios.
  const rest = { ...overrides };
  delete rest.material;
  delete rest.materialOrigin;
  return JSON.stringify({
    schema: AUTO_EVIDENCE_ARTIFACT_SCHEMA,
    executionReality: "virtual_paper_only",
    realMoneyAtRisk: false,
    brokerVenue: "paper",
    materialOrigin: origin,
    note: "PAPER VIRTUAL",
    material: {
      materialOrigin: origin,
      closedCycles: 184,
      cyclesWithRisk: 161,
      cyclesWithoutRisk: 23,
      regimesPresent: ["bull"],
      fingerprint: "sha256:abc",
      requestedStrategyVersions: ["orb-trend"],
      observedStrategyVersions: ["orb-trend"],
      fillsTotalForAccount: 500,
      fillsSelected: 420,
      fillsExcludedNoVersion: 80,
      fillsExcludedOtherVersion: 0,
      ...materialOverride,
    },
    report: {
      questions: AUTO_EVIDENCE_CALIBRATION_KEYS.map((key) => ({
        question: key,
        verdict: "supported",
      })),
      aggregate: { walkForwardEfficiency: 0.4213 },
    },
    ...rest,
  });
}

function paste(raw: string) {
  render(<OpsAutoEvidenceSection />);
  fireEvent.change(screen.getByTestId("ops-auto-evidence-paste"), {
    target: { value: raw },
  });
  fireEvent.click(screen.getByTestId("ops-auto-evidence-paste-cta"));
}

describe("OpsAutoEvidenceSection", () => {
  beforeEach(() => {
    localStorage.removeItem(AUTO_EVIDENCE_ARCHIVE_KEY);
    useAutoEvidenceArchiveStore.setState({ items: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it("starts as SIN MATERIAL · NO MEDIDO", () => {
    render(<OpsAutoEvidenceSection />);
    const badge = screen.getByTestId("ops-auto-evidence-badge");
    expect(badge.textContent).toContain("SIN MATERIAL");
    expect(badge.getAttribute("data-source-kind")).toBe("sin_material");
  });

  it("shows a PAPER REAL badge for a real run artifact", () => {
    paste(artifactJson());
    const badge = screen.getByTestId("ops-auto-evidence-badge");
    expect(badge.textContent).toContain("PAPER REAL");
    expect(badge.getAttribute("data-source-kind")).toBe("paper_real");
    expect(
      screen.getByTestId("ops-auto-evidence-origin").textContent,
    ).toContain("PAPER real");
    expect(
      screen.getByTestId("ops-auto-evidence-calibration").textContent,
    ).toContain("0.4213");
  });

  it("makes a synthetic fixture impossible to misread", () => {
    paste(artifactJson({ materialOrigin: "synthetic_fixture" }));
    const badge = screen.getByTestId("ops-auto-evidence-badge");
    expect(badge.textContent).toContain("FIXTURE SINTÉTICO");
    expect(badge.textContent).toContain("NO UTILIZAR PARA DECISIONES");
    expect(badge.getAttribute("data-source-kind")).toBe("synthetic_fixture");
  });

  it("shows NO MEDIDO instead of inventing a zero", () => {
    paste(
      artifactJson({
        material: {
          closedCycles: 184,
          cyclesWithRisk: 0,
          fingerprint: "sha256:x",
        },
      }),
    );
    const material = screen.getByTestId("ops-auto-evidence-material");
    expect(material.textContent).toContain("NO MEDIDO");
    expect(material.textContent).toContain("0");
  });

  it("rejects a foreign schema without persisting", () => {
    paste(JSON.stringify({ schema: "otra_cosa", report: {} }));
    expect(screen.getByTestId("ops-auto-evidence-import-error")).toBeTruthy();
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(0);
    expect(
      screen
        .getByTestId("ops-auto-evidence-badge")
        .getAttribute("data-source-kind"),
    ).toBe("sin_material");
  });

  it("flags a real-money artifact with an integrity warning", () => {
    paste(artifactJson({ realMoneyAtRisk: true, executionReality: "live" }));
    const warnings = screen.getAllByTestId("ops-auto-evidence-warning");
    expect(warnings.length).toBeGreaterThan(0);
    expect(warnings.map((node) => node.textContent).join(" ")).toContain(
      "realMoneyAtRisk",
    );
    expect(warnings.map((node) => node.textContent).join(" ")).toContain(
      "executionReality",
    );
  });

  it("clears the imported artifact", () => {
    paste(artifactJson());
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(1);
    fireEvent.click(screen.getByTestId("ops-auto-evidence-clear"));
    expect(useAutoEvidenceArchiveStore.getState().items).toHaveLength(0);
  });
});
