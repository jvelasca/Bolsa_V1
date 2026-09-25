/**
 * Tests — AUTO-20D lectura/presentación del artefacto AUTO EVIDENCE REPORT.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  ALLOCATION_CHANGE_NONE,
  AUTO_EVIDENCE_ARTIFACT_SCHEMA,
  AUTO_EVIDENCE_CALIBRATION_KEYS,
  EXECUTION_REALITY_VIRTUAL_PAPER,
  INCONCLUSIVE,
  MATERIAL_ORIGIN_PAPER_REAL,
  MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
  buildEvidenceView,
  classifyEvidenceSource,
  integrityWarnings,
  parseAutoEvidenceArtifact,
  type AutoEvidenceArtifact,
} from "./auto-evidence-report";

function questions(
  overrides: Partial<Record<string, string>> = {},
): Array<{ question: string; verdict: string }> {
  return AUTO_EVIDENCE_CALIBRATION_KEYS.map((key) => ({
    question: key,
    verdict: overrides[key] ?? "supported",
  }));
}

function artifact(
  overrides: Partial<AutoEvidenceArtifact> = {},
): AutoEvidenceArtifact {
  const origin = overrides.materialOrigin ?? MATERIAL_ORIGIN_PAPER_REAL;
  // La procedencia por defecto es COHERENTE entre raíz y material (P3-2); un override de
  // `materialOrigin` la mantiene coherente salvo que se sobreescriba `material` a mano.
  const material: AutoEvidenceArtifact["material"] =
    overrides.material !== undefined
      ? overrides.material
      : {
          materialOrigin: origin,
          account: "acc-1",
          closedCycles: 184,
          cyclesWithRisk: 161,
          cyclesWithoutRisk: 23,
          regimesPresent: ["bull", "bear", "range"],
          fingerprint: "sha256:abc",
          requestedStrategyVersions: ["orb-trend"],
          observedStrategyVersions: ["orb-trend"],
          fillsTotalForAccount: 500,
          fillsSelected: 420,
          fillsExcludedNoVersion: 80,
          fillsExcludedOtherVersion: 0,
          reservationsRead: 184,
          riskReadSaturated: false,
        };
  return {
    schema: AUTO_EVIDENCE_ARTIFACT_SCHEMA,
    executionReality: EXECUTION_REALITY_VIRTUAL_PAPER,
    realMoneyAtRisk: false,
    brokerVenue: "paper",
    materialOrigin: origin,
    note: "PAPER VIRTUAL",
    material,
    report: {
      questions: questions(),
      aggregate: { walkForwardEfficiency: 0.4213 },
    },
    ...overrides,
  };
}

describe("parseAutoEvidenceArtifact", () => {
  it("rejects a foreign schema with a declared reason", () => {
    const result = parseAutoEvidenceArtifact({
      schema: "otra_cosa",
      report: {},
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain(AUTO_EVIDENCE_ARTIFACT_SCHEMA);
    }
  });

  it("rejects a non-object payload", () => {
    expect(parseAutoEvidenceArtifact(null).ok).toBe(false);
    expect(parseAutoEvidenceArtifact("x").ok).toBe(false);
  });

  it("keeps the report verbatim (no reinterpretation)", () => {
    const report = {
      questions: questions(),
      aggregate: { walkForwardEfficiency: 1 },
    };
    const result = parseAutoEvidenceArtifact({
      ...artifact(),
      report,
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.artifact.report).toBe(report);
    }
  });

  it("accepts a null material (sin material)", () => {
    const result = parseAutoEvidenceArtifact({ ...artifact(), material: null });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.artifact.material).toBeNull();
    }
  });
});

describe("classifyEvidenceSource", () => {
  it("paper_real is decision-safe", () => {
    const view = classifyEvidenceSource(artifact());
    expect(view.kind).toBe("paper_real");
    expect(view.label).toBe("PAPER REAL");
    expect(view.decisionSafe).toBe(true);
  });

  it("synthetic fixture is NOT decision-safe", () => {
    const view = classifyEvidenceSource(
      artifact({ materialOrigin: MATERIAL_ORIGIN_SYNTHETIC_FIXTURE }),
    );
    expect(view.kind).toBe("synthetic_fixture");
    expect(view.label).toBe("FIXTURE SINTÉTICO");
    expect(view.decisionSafe).toBe(false);
    expect(view.caveat).toContain("NO UTILIZAR PARA DECISIONES");
  });

  it("no artifact is sin_material", () => {
    const view = classifyEvidenceSource(null);
    expect(view.kind).toBe("sin_material");
    expect(view.decisionSafe).toBe(false);
  });

  it("artifact with null material is sin_material", () => {
    const view = classifyEvidenceSource(artifact({ material: null }));
    expect(view.kind).toBe("sin_material");
    expect(view.decisionSafe).toBe(false);
  });

  it("unknown origin never degrades to paper_real", () => {
    const view = classifyEvidenceSource(
      artifact({ materialOrigin: "misterio" }),
    );
    expect(view.kind).toBe("desconocido");
    expect(view.decisionSafe).toBe(false);
  });

  it("a contradictory materialOrigin is declared, never resolved to paper_real", () => {
    const conflicting = artifact({
      materialOrigin: MATERIAL_ORIGIN_PAPER_REAL,
      material: { materialOrigin: MATERIAL_ORIGIN_SYNTHETIC_FIXTURE },
    });
    const view = classifyEvidenceSource(conflicting);
    expect(view.kind).toBe("desconocido");
    expect(view.decisionSafe).toBe(false);
    expect(view.caveat).toContain("Contradicción");
    expect(
      integrityWarnings(conflicting).some((w) => w.includes("incoherente")),
    ).toBe(true);
  });
});

describe("buildEvidenceView", () => {
  it("distinguishes NO MEDIDO from a legitimate 0", () => {
    const view = buildEvidenceView(
      artifact({
        material: {
          closedCycles: null,
          cyclesWithRisk: 0,
          cyclesWithoutRisk: null,
          fingerprint: null,
        },
      }),
    );
    const byLabel = (label: string) =>
      view.material.find((row) => row.label === label);
    expect(byLabel("Ciclos cerrados")?.value).toBe("NO MEDIDO");
    expect(byLabel("Medidos (con R)")?.value).toBe("0");
    expect(byLabel("Medidos (con R)")?.inconclusive).toBe(false);
    expect(byLabel("Sin R")?.value).toBe("NO MEDIDO");
    expect(byLabel("Sin R")?.inconclusive).toBe(true);
  });

  it("maps missing verdicts to INCONCLUSIVE, never invents one", () => {
    const view = buildEvidenceView(
      artifact({ report: { questions: [], aggregate: {} } }),
    );
    for (const row of view.calibration) {
      expect(row.value).toBe(INCONCLUSIVE);
      expect(row.inconclusive).toBe(true);
    }
  });

  it("maps supported/not_supported and formats the WFE", () => {
    const view = buildEvidenceView(
      artifact({
        report: {
          questions: questions({
            edge_sign_calibration: "not_supported",
            interval_coverage: "inconclusive",
          }),
          aggregate: { walkForwardEfficiency: 0.4213 },
        },
      }),
    );
    const byLabel = (label: string) =>
      view.calibration.find((row) => row.label === label);
    expect(byLabel("Edge sign")?.value).toBe("NOT_SUPPORTED");
    expect(byLabel("Coverage (regime)")?.value).toBe("SUPPORTED");
    expect(byLabel("Interval coverage")?.value).toBe(INCONCLUSIVE);
    expect(byLabel("Walk-forward efficiency")?.value).toBe("0.4213");
  });

  it("declares AUTO-21 out of scope and the allocation freeze", () => {
    const view = buildEvidenceView(artifact());
    const declared = new Map(
      view.declared.map((row) => [row.label, row.value]),
    );
    expect(declared.get("Current regime")).toContain("AUTO-21");
    expect(declared.get("Current evidence")).toContain("AUTO-21");
    expect(declared.get("Allocation change")).toContain(ALLOCATION_CHANGE_NONE);
    expect(declared.get("Allocation change")).toContain("auto18-v1");
  });

  it("exposes the perimeter without touching the measured universe", () => {
    const view = buildEvidenceView(artifact());
    const perimeter = new Map(
      view.perimeter.map((row) => [row.label, row.value]),
    );
    expect(perimeter.get("Fills totales (cuenta)")).toBe("500");
    expect(perimeter.get("Fills seleccionados")).toBe("420");
    expect(perimeter.get("Excluidos (sin versión)")).toBe("80");
    expect(
      view.material.find((row) => row.label === "Ciclos cerrados")?.value,
    ).toBe("184");
  });

  it("distinguishes an absent perimeter list from an empty one", () => {
    const view = buildEvidenceView(
      artifact({
        material: {
          materialOrigin: MATERIAL_ORIGIN_PAPER_REAL,
          requestedStrategyVersions: [],
          // observedStrategyVersions ausente a propósito
        },
      }),
    );
    const perimeter = new Map(view.perimeter.map((row) => [row.label, row]));
    expect(perimeter.get("Versiones pedidas")?.value).toBe("(ninguna)");
    expect(perimeter.get("Versiones pedidas")?.inconclusive).toBe(false);
    expect(perimeter.get("Versiones observadas")?.value).toBe("NO MEDIDO");
    expect(perimeter.get("Versiones observadas")?.inconclusive).toBe(true);
  });

  it("only lists perimeter rows for a measured material", () => {
    expect(
      buildEvidenceView(artifact({ material: null })).perimeter,
    ).toHaveLength(0);
  });
});

describe("integrityWarnings", () => {
  it("flags real money and non-virtual execution", () => {
    const warnings = integrityWarnings(
      artifact({ realMoneyAtRisk: true, executionReality: "live" }),
    );
    expect(warnings.some((w) => w.includes("realMoneyAtRisk"))).toBe(true);
    expect(warnings.some((w) => w.includes("executionReality"))).toBe(true);
  });

  it("flags a non-paper venue and saturated risk read", () => {
    const warnings = integrityWarnings(
      artifact({
        brokerVenue: "live",
        material: { riskReadSaturated: true },
      }),
    );
    expect(warnings.some((w) => w.includes("brokerVenue"))).toBe(true);
    expect(warnings.some((w) => w.includes("riskReadSaturated"))).toBe(true);
  });

  it("is silent for a clean paper artifact", () => {
    expect(integrityWarnings(artifact())).toHaveLength(0);
    expect(integrityWarnings(null)).toHaveLength(0);
  });
});

/**
 * Lee las claves de calibración del **instrumento Python real** (no de un literal espejo).
 * Falla ruidosamente si cambia la forma del instrumento: un contrato que no puede fallar no es
 * un contrato. Ruta relativa a este fichero: 5 niveles hasta la raíz del repo.
 */
function pythonCalibrationKeys(): string[] {
  const source = readFileSync(
    join(
      dirname(fileURLToPath(import.meta.url)),
      "../../../../..",
      "packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py",
    ),
    "utf8",
  );
  const matches = [
    ...source.matchAll(/^CALIBRATION_QUESTION_[A-Z0-9_]+\s*=\s*"([^"]+)"/gm),
  ];
  if (matches.length === 0) {
    throw new Error(
      "No se pudo extraer ninguna CALIBRATION_QUESTION_* del instrumento Python: " +
        "revisa auto_adaptive_calibration.py (¿cambió el formato?).",
    );
  }
  return [...new Set(matches.map((match) => match[1]!))].sort();
}

describe("schema contract", () => {
  it("matches the calibration keys the Python instrument actually emits", () => {
    const pythonKeys = pythonCalibrationKeys();
    // Las seis preguntas del instrumento; si Python añade o renombra una, este test cae.
    expect(pythonKeys).toHaveLength(6);
    expect([...AUTO_EVIDENCE_CALIBRATION_KEYS].sort()).toEqual(pythonKeys);
  });

  it("pins the artifact schema", () => {
    expect(AUTO_EVIDENCE_ARTIFACT_SCHEMA).toBe("auto20c_evidence_artifact_v1");
  });
});
