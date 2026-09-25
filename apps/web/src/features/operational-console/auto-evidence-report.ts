/**
 * AUTO-20D — lectura y presentación del artefacto `auto20c_evidence_artifact_v1`.
 *
 * Este módulo NO mide ni recalcula nada: recibe el artefacto que produce
 * `auto_replay_battery.py --out` (envelope determinista + `report` verbatim) y lo prepara para
 * que un humano lo lea sin poder confundir su PROCEDENCIA. Dos reglas duras:
 *
 * 1. **Nunca se inventa un cero.** Un conteo ausente (`null`) se muestra como "NO MEDIDO"; es
 *    distinto de `0`, que significa "hemos medido y no hay". Igual que el render Python.
 * 2. **Nunca se asume PAPER real.** Un `materialOrigin` desconocido —o un artefacto sin material—
 *    no se degrada a "PAPER REAL": se declara su procedencia (o su ausencia) tal cual.
 *
 * Módulo puro y determinista: sin I/O, sin reloj, sin estado.
 *
 * @see packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py
 */

export const AUTO_EVIDENCE_ARTIFACT_SCHEMA = "auto20c_evidence_artifact_v1";
export const MATERIAL_ORIGIN_PAPER_REAL = "paper_real";
export const MATERIAL_ORIGIN_SYNTHETIC_FIXTURE = "synthetic_fixture";
export const EXECUTION_REALITY_VIRTUAL_PAPER = "virtual_paper_only";
export const INCONCLUSIVE = "INCONCLUSIVE";
export const SUPPORTED = "SUPPORTED";
export const NOT_SUPPORTED = "NOT_SUPPORTED";
export const OUT_OF_SCOPE_AUTO21 = "AUTO-21 (fuera de alcance)";
export const ALLOCATION_CHANGE_NONE = "none";

export const EVIDENCE_ARTIFACT_DISCLAIMER =
  "Procedencia autodeclarada por el artefacto; la huella sella el universo medido, no es prueba criptográfica de origen.";

export type EvidenceVerdict =
  | typeof SUPPORTED
  | typeof NOT_SUPPORTED
  | typeof INCONCLUSIVE;

/** Claves de pregunta del informe de calibración (mismo productor que `auto_adaptive_calibration`). */
export const AUTO_EVIDENCE_CALIBRATION_KEYS = [
  "shrinkage_calibration",
  "effective_n_calibration",
  "interval_coverage",
  "edge_sign_calibration",
  "confidence_calibration",
  "coverage_calibration",
] as const;

const CALIBRATION_LABELS: ReadonlyArray<readonly [string, string]> = [
  ["shrinkage_calibration", "Shrinkage"],
  ["effective_n_calibration", "Effective-N"],
  ["interval_coverage", "Interval coverage"],
  ["edge_sign_calibration", "Edge sign"],
  ["confidence_calibration", "Confidence calibration"],
  ["coverage_calibration", "Coverage (regime)"],
];

export type AutoEvidenceMaterial = {
  materialOrigin?: string | null;
  account?: string | null;
  requestedStrategyVersions?: string[];
  observedStrategyVersions?: string[];
  versionsRequestedWithoutMaterial?: string[];
  versionsObservedNotRequested?: string[];
  executionReality?: string | null;
  brokerVenue?: string | null;
  fillsTotalForAccount?: number | null;
  fillsSelected?: number | null;
  fillsExcludedNoVersion?: number | null;
  fillsExcludedOtherVersion?: number | null;
  closedCycles?: number | null;
  cyclesWithRisk?: number | null;
  cyclesWithoutRisk?: number | null;
  regimesPresent?: string[];
  fingerprint?: string | null;
  costAppliedCycles?: number | null;
  reservationsRead?: number | null;
  riskReadSaturated?: boolean | null;
  riskBasis?: string | null;
  exportTimestamp?: string | null;
  [key: string]: unknown;
};

export type AutoEvidenceArtifact = {
  schema: string;
  executionReality: string | null;
  realMoneyAtRisk: boolean | null;
  brokerVenue: string | null;
  materialOrigin: string | null;
  note: string | null;
  material: AutoEvidenceMaterial | null;
  report: Record<string, unknown>;
};

export type ParseAutoEvidenceResult =
  | { ok: true; artifact: AutoEvidenceArtifact }
  | { ok: false; error: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asStringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function asBooleanOrNull(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}

function asMaterial(value: unknown): AutoEvidenceMaterial | null {
  if (!isRecord(value)) return null;
  return {
    ...value,
    requestedStrategyVersions: asStringArray(value.requestedStrategyVersions),
    observedStrategyVersions: asStringArray(value.observedStrategyVersions),
    versionsRequestedWithoutMaterial: asStringArray(
      value.versionsRequestedWithoutMaterial,
    ),
    versionsObservedNotRequested: asStringArray(
      value.versionsObservedNotRequested,
    ),
    regimesPresent: asStringArray(value.regimesPresent),
  };
}

/**
 * Valida y normaliza un artefacto AUTO-20C. El esquema es obligatorio: importar un JSON ajeno
 * como evidencia AUTO sería una mentira de procedencia, así que se rechaza con motivo declarado.
 */
export function parseAutoEvidenceArtifact(
  raw: unknown,
): ParseAutoEvidenceResult {
  const root = isRecord(raw) ? raw : null;
  if (!root) {
    return { ok: false, error: "JSON inválido: se esperaba un objeto." };
  }
  const schema = asStringOrNull(root.schema);
  if (schema !== AUTO_EVIDENCE_ARTIFACT_SCHEMA) {
    return {
      ok: false,
      error: `Esquema no reconocido (${
        schema ?? "sin schema"
      }): se esperaba ${AUTO_EVIDENCE_ARTIFACT_SCHEMA}.`,
    };
  }
  if (!isRecord(root.report)) {
    return { ok: false, error: "Falta el informe de calibración (`report`)." };
  }
  const material = root.material == null ? null : asMaterial(root.material);
  if (root.material != null && material === null) {
    return { ok: false, error: "`material` presente pero no es un objeto." };
  }
  return {
    ok: true,
    artifact: {
      schema,
      executionReality: asStringOrNull(root.executionReality),
      realMoneyAtRisk: asBooleanOrNull(root.realMoneyAtRisk),
      brokerVenue: asStringOrNull(root.brokerVenue),
      materialOrigin: asStringOrNull(root.materialOrigin),
      note: asStringOrNull(root.note),
      material,
      report: root.report,
    },
  };
}

export type EvidenceSourceKind =
  | "paper_real"
  | "synthetic_fixture"
  | "sin_material"
  | "desconocido";

export type EvidenceSourceTone = "ok" | "warn" | "neutral" | "danger";

export type EvidenceSourceView = {
  kind: EvidenceSourceKind;
  label: string;
  tone: EvidenceSourceTone;
  /** `true` solo cuando la procedencia es PAPER real: fixture y sin-material NO son base de decisión. */
  decisionSafe: boolean;
  caveat: string | null;
};

/**
 * Clasifica la PROCEDENCIA del artefacto. Es la pieza que impide que un fixture se lea como una
 * corrida PAPER real: el caso desconocido nunca se degrada a `paper_real`.
 */
export function classifyEvidenceSource(
  artifact: AutoEvidenceArtifact | null | undefined,
): EvidenceSourceView {
  if (!artifact) {
    return {
      kind: "sin_material",
      label: "SIN MATERIAL · NO MEDIDO",
      tone: "neutral",
      decisionSafe: false,
      caveat: "No hay artefacto importado: no se ha medido nada.",
    };
  }
  const origin =
    artifact.materialOrigin ?? artifact.material?.materialOrigin ?? null;
  if (artifact.material === null) {
    return {
      kind: "sin_material",
      label: "SIN MATERIAL · NO MEDIDO",
      tone: "neutral",
      decisionSafe: false,
      caveat:
        "El artefacto no declara material: el informe no se apoya en ningún universo medido.",
    };
  }
  if (origin === MATERIAL_ORIGIN_PAPER_REAL) {
    return {
      kind: "paper_real",
      label: "PAPER REAL",
      tone: "ok",
      decisionSafe: true,
      caveat:
        "Datos reales de la cuenta PAPER con DINERO VIRTUAL: nunca una plataforma real.",
    };
  }
  if (origin === MATERIAL_ORIGIN_SYNTHETIC_FIXTURE) {
    return {
      kind: "synthetic_fixture",
      label: "FIXTURE SINTÉTICO",
      tone: "warn",
      decisionSafe: false,
      caveat: "NO UTILIZAR PARA DECISIONES: datos sintéticos de test.",
    };
  }
  return {
    kind: "desconocido",
    label: "PROCEDENCIA DESCONOCIDA",
    tone: "danger",
    decisionSafe: false,
    caveat: `materialOrigin ${origin ?? "ausente"} no reconocido: no se asume PAPER real.`,
  };
}

export type EvidenceRow = {
  label: string;
  value: string;
  inconclusive: boolean;
};

export type EvidenceView = {
  source: EvidenceSourceView;
  material: EvidenceRow[];
  calibration: EvidenceRow[];
  declared: EvidenceRow[];
  perimeter: EvidenceRow[];
  warnings: string[];
};

function verdictLabel(value: unknown): EvidenceVerdict {
  const normalized =
    typeof value === "string" ? value.trim().toLowerCase() : "";
  if (normalized === "supported") return SUPPORTED;
  if (normalized === "not_supported") return NOT_SUPPORTED;
  return INCONCLUSIVE;
}

function questionVerdict(
  report: Record<string, unknown>,
  key: string,
): EvidenceVerdict {
  const questions = report.questions;
  if (Array.isArray(questions)) {
    for (const row of questions) {
      if (isRecord(row) && row.question === key) {
        return verdictLabel(row.verdict);
      }
    }
  }
  return INCONCLUSIVE;
}

/** Número → texto; `null`/no finito ⇒ INCONCLUSIVE (nunca un 0 de relleno). */
function numberLabel(value: unknown): EvidenceRow["value"] {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(4);
  }
  return INCONCLUSIVE;
}

/** Conteo → texto; `null` ⇒ "NO MEDIDO" (distinto del 0 legítimo). */
function countLabel(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return "NO MEDIDO";
}

function joinList(items: string[] | undefined, empty = "(ninguna)"): string {
  return items && items.length > 0 ? items.join(", ") : empty;
}

function walkForwardEfficiency(report: Record<string, unknown>): unknown {
  const aggregate = report.aggregate;
  return isRecord(aggregate) ? aggregate.walkForwardEfficiency : undefined;
}

function materialRows(material: AutoEvidenceMaterial | null): EvidenceRow[] {
  if (!material) {
    return [
      {
        label: "Material",
        value: "NO MEDIDO (corrida sin exportación PAPER)",
        inconclusive: true,
      },
    ];
  }
  const regimes = asStringArray(material.regimesPresent);
  return [
    {
      label: "Origen del material",
      value: material.materialOrigin ?? "NO MEDIDO",
      inconclusive: material.materialOrigin == null,
    },
    {
      label: "Cuenta",
      value: material.account ?? "NO MEDIDO",
      inconclusive: material.account == null,
    },
    {
      label: "Ciclos cerrados",
      value: countLabel(material.closedCycles),
      inconclusive: typeof material.closedCycles !== "number",
    },
    {
      label: "Medidos (con R)",
      value: countLabel(material.cyclesWithRisk),
      inconclusive: typeof material.cyclesWithRisk !== "number",
    },
    {
      label: "Sin R",
      value: countLabel(material.cyclesWithoutRisk),
      inconclusive: typeof material.cyclesWithoutRisk !== "number",
    },
    {
      label: "Regímenes",
      value:
        regimes.length > 0
          ? `${regimes.join(", ")} (${regimes.length})`
          : "(sin régimen declarado)",
      inconclusive: regimes.length === 0,
    },
    {
      label: "Huella",
      value: material.fingerprint ?? "NO MEDIDO",
      inconclusive: material.fingerprint == null,
    },
  ];
}

function perimeterRows(material: AutoEvidenceMaterial | null): EvidenceRow[] {
  if (!material) return [];
  const requestedWithout = asStringArray(
    material.versionsRequestedWithoutMaterial,
  );
  const observedNotRequested = asStringArray(
    material.versionsObservedNotRequested,
  );
  const rows: EvidenceRow[] = [
    {
      label: "Versiones pedidas",
      value: joinList(asStringArray(material.requestedStrategyVersions)),
      inconclusive: false,
    },
    {
      label: "Versiones observadas",
      value: joinList(asStringArray(material.observedStrategyVersions)),
      inconclusive: false,
    },
    {
      label: "Fills totales (cuenta)",
      value: countLabel(material.fillsTotalForAccount),
      inconclusive: typeof material.fillsTotalForAccount !== "number",
    },
    {
      label: "Fills seleccionados",
      value: countLabel(material.fillsSelected),
      inconclusive: typeof material.fillsSelected !== "number",
    },
    {
      label: "Excluidos (sin versión)",
      value: countLabel(material.fillsExcludedNoVersion),
      inconclusive: typeof material.fillsExcludedNoVersion !== "number",
    },
    {
      label: "Excluidos (otra versión)",
      value: countLabel(material.fillsExcludedOtherVersion),
      inconclusive: typeof material.fillsExcludedOtherVersion !== "number",
    },
    {
      label: "Reservas leídas",
      value: countLabel(material.reservationsRead),
      inconclusive: typeof material.reservationsRead !== "number",
    },
    {
      label: "Lectura de riesgo saturada",
      value:
        material.riskReadSaturated === true
          ? "sí (completitud NO garantizada)"
          : material.riskReadSaturated === false
            ? "no (la lectura terminó; NO significa 'todas las reservas existen')"
            : "NO MEDIDO",
      inconclusive: typeof material.riskReadSaturated !== "boolean",
    },
  ];
  if (requestedWithout.length > 0) {
    rows.push({
      label: "Pedidas sin material",
      value: requestedWithout.join(", "),
      inconclusive: false,
    });
  }
  if (observedNotRequested.length > 0) {
    rows.push({
      label: "Observadas no pedidas",
      value: observedNotRequested.join(", "),
      inconclusive: false,
    });
  }
  return rows;
}

/** Avisos de integridad: la UI no acepta en silencio una procedencia incoherente. */
export function integrityWarnings(
  artifact: AutoEvidenceArtifact | null | undefined,
): string[] {
  if (!artifact) return [];
  const warnings: string[] = [];
  if (artifact.realMoneyAtRisk === true) {
    warnings.push(
      "realMoneyAtRisk=true: un artefacto PAPER no debería declarar dinero real en riesgo.",
    );
  }
  if (
    artifact.executionReality !== null &&
    artifact.executionReality !== EXECUTION_REALITY_VIRTUAL_PAPER
  ) {
    warnings.push(
      `executionReality='${artifact.executionReality}' no es '${EXECUTION_REALITY_VIRTUAL_PAPER}'.`,
    );
  }
  if (artifact.executionReality === null) {
    warnings.push(
      "executionReality ausente: no se puede confirmar ejecución virtual.",
    );
  }
  if (
    artifact.brokerVenue !== null &&
    artifact.brokerVenue.trim().toLowerCase() !== "paper"
  ) {
    warnings.push(`brokerVenue='${artifact.brokerVenue}' no es paper.`);
  }
  if (artifact.material?.riskReadSaturated === true) {
    warnings.push(
      "riskReadSaturated=true: la lectura de reservas no garantizó completitud.",
    );
  }
  return warnings;
}

/** Vista determinista para el render: procedencia + bloques verbatim (sin recalcular nada). */
export function buildEvidenceView(
  artifact: AutoEvidenceArtifact | null | undefined,
): EvidenceView {
  const calibration: EvidenceRow[] = CALIBRATION_LABELS.map(([key, label]) => {
    const verdict = questionVerdict(artifact?.report ?? {}, key);
    return {
      label,
      value: verdict,
      inconclusive: verdict === INCONCLUSIVE,
    };
  });
  const wfeValue = numberLabel(walkForwardEfficiency(artifact?.report ?? {}));
  calibration.push({
    label: "Walk-forward efficiency",
    value: wfeValue,
    inconclusive: wfeValue === INCONCLUSIVE,
  });
  return {
    source: classifyEvidenceSource(artifact),
    material: materialRows(artifact?.material ?? null),
    calibration,
    declared: [
      {
        label: "Current regime",
        value: OUT_OF_SCOPE_AUTO21,
        inconclusive: true,
      },
      {
        label: "Current evidence",
        value: OUT_OF_SCOPE_AUTO21,
        inconclusive: true,
      },
      {
        label: "Allocation change",
        value: `${ALLOCATION_CHANGE_NONE} (auto18-v1 congelado: la evidencia no mueve el reparto)`,
        inconclusive: false,
      },
    ],
    perimeter: perimeterRows(artifact?.material ?? null),
    warnings: integrityWarnings(artifact),
  };
}
