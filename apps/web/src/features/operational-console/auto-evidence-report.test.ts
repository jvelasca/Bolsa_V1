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
  EXECUTION_LABEL_VIRTUAL,
  EXECUTION_REALITY_VIRTUAL_PAPER,
  INCONCLUSIVE,
  MATERIAL_ORIGIN_PAPER_REAL,
  MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
  NOT_MEASURED,
  buildEvidenceView,
  classifyEvidenceSource,
  classifyExecutionReality,
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

describe("classifyExecutionReality", () => {
  it("labels a paper artifact as VIRTUAL and never as real money", () => {
    const view = classifyExecutionReality(artifact());
    expect(view.kind).toBe("virtual_paper");
    expect(view.label).toBe(EXECUTION_LABEL_VIRTUAL);
    expect(view.realMoneyAtRisk).toBe(false);
    expect(view.tone).toBe("ok");
  });

  it("separates PAPER REAL data from real money in the source subtitle", () => {
    const source = classifyEvidenceSource(artifact());
    expect(source.label).toBe("PAPER REAL");
    expect(source.subtitle).toContain("NO ES DINERO REAL");
  });

  it("declares NOT MEASURED when executionReality is absent, never assuming virtual", () => {
    const view = classifyExecutionReality(artifact({ executionReality: null }));
    expect(view.kind).toBe("no_medido");
    expect(view.label).toBe(NOT_MEASURED);
    expect(view.tone).toBe("warn");
  });

  it("flags real money at risk as unknown instead of degrading to virtual", () => {
    const view = classifyExecutionReality(artifact({ realMoneyAtRisk: true }));
    expect(view.kind).toBe("desconocido");
    expect(view.tone).toBe("danger");
    expect(view.realMoneyAtRisk).toBe(true);
  });

  it("flags a non-virtual execution reality without pretending it is virtual", () => {
    const view = classifyExecutionReality(
      artifact({ executionReality: "live" }),
    );
    expect(view.kind).toBe("desconocido");
    expect(view.tone).toBe("danger");
    expect(view.caveat).toContain("live");
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

  it("maps supported/not_supported and formats the WFE in GLOBAL EVIDENCE", () => {
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
    const global = new Map(view.global.map((row) => [row.label, row]));
    expect(global.get("WFE")?.value).toBe("0.4213");
    expect(global.get("WFE")?.inconclusive).toBe(false);
  });

  it("keeps the DECLARED P(R>0) apart from the REALIZED OOS share", () => {
    const view = buildEvidenceView(
      artifact({
        report: {
          questions: [
            {
              question: "probability_positive_calibration",
              verdict: "not_supported",
              metrics: { meanDeclaredProbability: 0.2857 },
            },
          ],
          aggregate: { probabilityPositiveOos: 0.5222 },
        },
      }),
    );
    const global = new Map(view.global.map((row) => [row.label, row.value]));
    expect(global.get("P(R>0)")).toBe("0.2857");
    expect(global.get("P(R>0) OOS")).toBe("0.5222");
  });

  it("declares NO MEDIDO for the three context levels without a reading, and the freeze", () => {
    const view = buildEvidenceView(artifact());
    expect(view.currentRegime.map((row) => row.value)).toEqual([NOT_MEASURED]);
    expect(view.currentRegime[0]?.inconclusive).toBe(true);
    expect(view.regimeEvidence.map((row) => row.value)).toEqual([NOT_MEASURED]);
    expect(view.regimeEvidence[0]?.inconclusive).toBe(true);
    expect(view.crossStrategy.map((row) => row.value)).toEqual([NOT_MEASURED]);
    expect(view.crossStrategy[0]?.inconclusive).toBe(true);
    const allocation = new Map(
      view.allocation.map((row) => [row.label, row.value]),
    );
    expect(allocation.get("Allocation change")).toContain(
      ALLOCATION_CHANGE_NONE,
    );
    expect(allocation.get("Allocation change")).toContain("auto18-v1");
    // El WFE ausente del agregado es NO MEDIDO, nunca un 0 de relleno.
    const empty = buildEvidenceView(
      artifact({ report: { questions: [], aggregate: {} } }),
    );
    const global = new Map(empty.global.map((row) => [row.label, row.value]));
    expect(global.get("P(R>0)")).toBe(NOT_MEASURED);
    expect(global.get("P(R>0) OOS")).toBe(NOT_MEASURED);
    expect(global.get("WFE")).toBe(NOT_MEASURED);
  });

  it("maps the edge band to the verdict the backend declares, never inventing one", () => {
    const view = buildEvidenceView(
      artifact({
        currentRegime: "TREND_UP",
        currentEvidence: {
          method: "current_regime_evidence_v1",
          regime: "TREND_UP",
          adverse: false,
          byStrategy: {
            "orb-high": {
              strategyVersion: "orb-high",
              regime: "TREND_UP",
              measuredN: 12,
              episodes: 4,
              expectancyR: 0.4,
              probabilityPositive: 0.7012,
              edgeConfidence: "HIGH",
              notes: [],
            },
            "orb-medium": {
              strategyVersion: "orb-medium",
              regime: "TREND_UP",
              measuredN: 10,
              episodes: 3,
              expectancyR: 0.1,
              probabilityPositive: 0.55,
              edgeConfidence: "MEDIUM",
              notes: ["interval_crosses_zero"],
            },
            "orb-low": {
              strategyVersion: "orb-low",
              regime: "TREND_UP",
              measuredN: 9,
              episodes: 3,
              expectancyR: -0.2,
              probabilityPositive: 0.2,
              edgeConfidence: "LOW",
              notes: [],
            },
            "orb-b": {
              strategyVersion: "orb-b",
              regime: "TREND_UP",
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
    const rows = new Map(view.regimeEvidence.map((row) => [row.label, row]));
    expect(rows.get("orb-high")?.value).toBe(
      "SUPPORTED · HIGH · P(R>0) 0.7012",
    );
    expect(rows.get("orb-high")?.inconclusive).toBe(false);
    expect(rows.get("orb-medium")?.value).toContain("INCONCLUSIVE");
    expect(rows.get("orb-medium")?.value).toContain("P(R>0) 0.5500");
    expect(rows.get("orb-low")?.value).toContain("NOT_SUPPORTED");
    // Sin celda del régimen: INCONCLUSIVE con su nota, jamás un SUPPORTED fingido.
    expect(rows.get("orb-b")?.value).toContain(INCONCLUSIVE);
    expect(rows.get("orb-b")?.value).toContain("no_evidence_for_regime");
    expect(rows.get("orb-b")?.inconclusive).toBe(true);
  });

  it("never publishes a 0.0000 correlation for a pair that could not be measured", () => {
    const view = buildEvidenceView(
      artifact({
        correlation: {
          method: "bucket_correlation_v1",
          bucket: "day",
          minBuckets: 4,
          strategies: ["orb-a", "orb-b", "orb-c"],
          pairs: [
            {
              left: "orb-a",
              right: "orb-b",
              correlation: 0.42,
              sharedBuckets: 6,
              notes: [],
            },
            {
              left: "orb-a",
              right: "orb-c",
              correlation: null,
              sharedBuckets: 0,
              notes: ["no_shared_buckets"],
            },
          ],
          notes: [],
        },
      }),
    );
    const byLabel = new Map(view.crossStrategy.map((row) => [row.label, row]));
    expect(byLabel.get("orb-a vs orb-b")?.value).toBe("0.4200 (cubos=6)");
    expect(byLabel.get("orb-a vs orb-b")?.inconclusive).toBe(false);
    const unmeasured = byLabel.get("orb-a vs orb-c");
    expect(unmeasured?.value).toContain(NOT_MEASURED);
    expect(unmeasured?.value).toContain("no_shared_buckets");
    expect(unmeasured?.value).not.toContain("0.0000");
    expect(unmeasured?.inconclusive).toBe(true);
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

  it("treats a non-list perimeter value as not measured (mirror of Python)", () => {
    const view = buildEvidenceView(
      artifact({
        material: {
          materialOrigin: MATERIAL_ORIGIN_PAPER_REAL,
          // escalar donde se espera una lista: no se itera
          requestedStrategyVersions: "orb-a" as unknown as string[],
        },
      }),
    );
    const perimeter = new Map(view.perimeter.map((row) => [row.label, row]));
    expect(perimeter.get("Versiones pedidas")?.value).toBe("NO MEDIDO");
    expect(perimeter.get("Versiones pedidas")?.inconclusive).toBe(true);
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
    // Las siete preguntas del instrumento; si Python añade o renombra una, este test cae.
    expect(pythonKeys).toHaveLength(7);
    expect([...AUTO_EVIDENCE_CALIBRATION_KEYS].sort()).toEqual(pythonKeys);
  });

  it("pins the artifact schema", () => {
    expect(AUTO_EVIDENCE_ARTIFACT_SCHEMA).toBe("auto20c_evidence_artifact_v1");
  });
});
