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
      screen.getByTestId("ops-auto-evidence-global").textContent,
    ).toContain("0.4213");
  });

  it("makes a synthetic fixture impossible to misread", () => {
    paste(artifactJson({ materialOrigin: "synthetic_fixture" }));
    const badge = screen.getByTestId("ops-auto-evidence-badge");
    expect(badge.textContent).toContain("FIXTURE SINTÉTICO");
    expect(badge.textContent).toContain("NO UTILIZAR PARA DECISIONES");
    expect(badge.getAttribute("data-source-kind")).toBe("synthetic_fixture");
  });

  it("separates PAPER REAL data from real money in the SOURCE subtitle", () => {
    paste(artifactJson());
    const subtitle = screen.getByTestId("ops-auto-evidence-source-subtitle");
    expect(subtitle.textContent).toContain("NO ES DINERO REAL");
  });

  it("renders a prominent VIRTUAL execution reality for a paper artifact", () => {
    paste(artifactJson());
    const block = screen.getByTestId("ops-auto-evidence-execution-reality");
    expect(block.textContent).toContain("VIRTUAL — NO REAL MONEY");
    expect(block.getAttribute("data-execution-kind")).toBe("virtual_paper");
  });

  it("flags a real-money artifact in EXECUTION REALITY, never degrading to virtual", () => {
    paste(artifactJson({ realMoneyAtRisk: true, executionReality: "live" }));
    const block = screen.getByTestId("ops-auto-evidence-execution-reality");
    expect(block.textContent).toContain("DINERO REAL EN RIESGO");
    expect(block.getAttribute("data-execution-kind")).toBe("desconocido");
    expect(block.textContent).not.toContain("VIRTUAL — NO REAL MONEY");
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

  it("always renders the three evidence levels, with NO MEDIDO where nothing was measured", () => {
    paste(artifactJson());
    const global = screen.getByTestId("ops-auto-evidence-global");
    expect(global.textContent).toContain("WFE");
    expect(global.textContent).toContain("0.4213");
    expect(global.textContent).toContain("NO MEDIDO");
    expect(
      screen.getByTestId("ops-auto-evidence-current-regime").textContent,
    ).toContain("NO MEDIDO");
    expect(
      screen.getByTestId("ops-auto-evidence-regime-evidence").textContent,
    ).toContain("NO MEDIDO");
    expect(
      screen.getByTestId("ops-auto-evidence-allocation").textContent,
    ).toContain("auto18-v1");
  });

  it("shows the cross-strategy block as NOT MEASURED when the artifact brings no matrix", () => {
    paste(artifactJson());
    // No se OCULTA el bloque: la ausencia de correlación se declara, nunca se interpreta como 0.
    const block = screen.getByTestId("ops-auto-evidence-cross-strategy");
    expect(block.textContent).toContain("NO MEDIDO");
    expect(block.textContent).not.toContain("0.0000");
  });

  it("renders the correlation matrix and never a 0 for an unmeasured pair", () => {
    paste(
      artifactJson({
        correlation: {
          method: "bucket_correlation_v1",
          bucket: "day",
          minBuckets: 4,
          strategies: ["a", "b", "c"],
          pairs: [
            {
              left: "a",
              right: "b",
              correlation: 0.5,
              sharedBuckets: 6,
              notes: [],
            },
            {
              left: "a",
              right: "c",
              correlation: null,
              sharedBuckets: 0,
              notes: ["no_shared_buckets"],
            },
          ],
          notes: [],
        },
      }),
    );
    const block = screen.getByTestId("ops-auto-evidence-cross-strategy");
    expect(block.textContent).toContain("a vs b");
    expect(block.textContent).toContain("0.5000");
    expect(block.textContent).toContain("cubos=6");
    expect(block.textContent).toContain("a vs c");
    expect(block.textContent).toContain("NO MEDIDO");
    expect(block.textContent).not.toContain("0.0000");
  });

  it("shows the regime verdict per strategy, with INCONCLUSIVE for a missing cell", () => {
    paste(
      artifactJson({
        currentRegime: "RANGE",
        currentEvidence: {
          method: "current_regime_evidence_v1",
          regime: "RANGE",
          adverse: false,
          byStrategy: {
            "orb-a": {
              strategyVersion: "orb-a",
              regime: "RANGE",
              measuredN: 12,
              episodes: 4,
              expectancyR: 0.4,
              probabilityPositive: 0.75,
              edgeConfidence: "HIGH",
              notes: [],
            },
            "orb-b": {
              strategyVersion: "orb-b",
              regime: "RANGE",
              measuredN: 0,
              episodes: 0,
              expectancyR: null,
              probabilityPositive: null,
              edgeConfidence: "UNKNOWN",
              notes: ["no_evidence_for_regime"],
            },
          },
          notes: [],
        },
      }),
    );
    expect(
      screen.getByTestId("ops-auto-evidence-current-regime").textContent,
    ).toContain("RANGE");
    const regime = screen.getByTestId("ops-auto-evidence-regime-evidence");
    expect(regime.textContent).toContain("orb-a");
    expect(regime.textContent).toContain("SUPPORTED");
    expect(regime.textContent).toContain("orb-b");
    expect(regime.textContent).toContain("INCONCLUSIVE");
    expect(regime.textContent).toContain("no_evidence_for_regime");
  });
});
