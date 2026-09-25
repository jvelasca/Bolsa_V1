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
/** Etiqueta de lo no medido: espejo de `NOT_MEASURED` en `auto_evidence_report.py`. */
export const NOT_MEASURED = "NO MEDIDO";
export const ALLOCATION_CHANGE_NONE = "none";

export const EVIDENCE_ARTIFACT_DISCLAIMER =
  "Procedencia autodeclarada por el artefacto; la huella sella el universo medido, no es prueba criptográfica de origen.";

export type EvidenceVerdict =
  | typeof SUPPORTED
  | typeof NOT_SUPPORTED
  | typeof INCONCLUSIVE;

/** Claves de pregunta del informe de calibración (mismo productor que `auto_adaptive_calibration`). */
export const AUTO_EVIDENCE_CALIBRATION_KEYS = [
  "interval_coverage",
  "edge_sign_calibration",
  "probability_positive_calibration",
  "confidence_calibration",
  "shrinkage_calibration",
  "effective_n_calibration",
  "coverage_calibration",
] as const;

const CALIBRATION_LABELS: ReadonlyArray<readonly [string, string]> = [
  ["interval_coverage", "Interval coverage"],
  ["edge_sign_calibration", "Edge sign"],
  ["probability_positive_calibration", "P(R>0)"],
  ["confidence_calibration", "Confidence calibration"],
  ["shrinkage_calibration", "Shrinkage"],
  ["effective_n_calibration", "Effective-N"],
  ["coverage_calibration", "Coverage (regime)"],
];

export type AutoEvidenceMaterial = {
  materialOrigin?: string | null;
  account?: string | null;
  requestedStrategyVersions?: string[] | null;
  observedStrategyVersions?: string[] | null;
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

export type AutoEvidenceCorrelationPair = {
  left: string;
  right: string;
  correlation: number | null;
  sharedBuckets: number | null;
  notes: string[];
};

/** AUTO-21 — matriz de correlación por cubo temporal publicada por el artefacto (opcional). */
export type AutoEvidenceCorrelation = {
  method: string | null;
  bucket: string | null;
  minBuckets: number | null;
  strategies: string[];
  pairs: AutoEvidenceCorrelationPair[];
  notes: string[];
};

/** AUTO-21 — evidencia de UNA estrategia para el régimen actual (opcional). */
export type AutoEvidenceRegimeRow = {
  strategyVersion: string;
  regime: string;
  measuredN: number | null;
  episodes: number | null;
  expectancyR: number | null;
  probabilityPositive: number | null;
  edgeConfidence: string | null;
  notes: string[];
};

/** AUTO-21 — evidencia del régimen actual publicada por el artefacto (opcional). */
export type AutoEvidenceCurrentEvidence = {
  method: string | null;
  regime: string | null;
  adverse: boolean | null;
  byStrategy: Record<string, AutoEvidenceRegimeRow>;
  notes: string[];
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
  /** AUTO-21 — opcionales: ausentes ⇒ el artefacto es el mismo que auditó `v2.67`. */
  correlation?: AutoEvidenceCorrelation | null;
  currentRegime?: string | null;
  currentEvidence?: AutoEvidenceCurrentEvidence | null;
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

/** Lista de strings preservando la AUSENCIA (`null`): ausente ≠ `[]` (ver P3-3). */
function asStringArrayOrNull(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  return value.map((item) => String(item));
}

function asMaterial(value: unknown): AutoEvidenceMaterial | null {
  if (!isRecord(value)) return null;
  return {
    ...value,
    requestedStrategyVersions: asStringArrayOrNull(
      value.requestedStrategyVersions,
    ),
    observedStrategyVersions: asStringArrayOrNull(
      value.observedStrategyVersions,
    ),
    versionsRequestedWithoutMaterial: asStringArray(
      value.versionsRequestedWithoutMaterial,
    ),
    versionsObservedNotRequested: asStringArray(
      value.versionsObservedNotRequested,
    ),
    regimesPresent: asStringArray(value.regimesPresent),
  };
}

function asNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** AUTO-21 — normaliza el bloque `correlation`; ausente o mal formado ⇒ `null` (no se inventa). */
function asCorrelation(value: unknown): AutoEvidenceCorrelation | null {
  if (!isRecord(value)) return null;
  const rawPairs = Array.isArray(value.pairs) ? value.pairs : [];
  const pairs: AutoEvidenceCorrelationPair[] = rawPairs
    .filter(isRecord)
    .map((pair) => ({
      left: asStringOrNull(pair.left) ?? "",
      right: asStringOrNull(pair.right) ?? "",
      correlation: asNumberOrNull(pair.correlation),
      sharedBuckets: asNumberOrNull(pair.sharedBuckets),
      notes: asStringArray(pair.notes),
    }));
  return {
    method: asStringOrNull(value.method),
    bucket: asStringOrNull(value.bucket),
    minBuckets: asNumberOrNull(value.minBuckets),
    strategies: asStringArray(value.strategies),
    pairs,
    notes: asStringArray(value.notes),
  };
}

/** AUTO-21 — normaliza el bloque `currentEvidence`; ausente o mal formado ⇒ `null` (no se inventa). */
function asCurrentEvidence(value: unknown): AutoEvidenceCurrentEvidence | null {
  if (!isRecord(value)) return null;
  const byStrategy: Record<string, AutoEvidenceRegimeRow> = {};
  const raw = isRecord(value.byStrategy) ? value.byStrategy : {};
  for (const [version, row] of Object.entries(raw)) {
    if (!isRecord(row)) continue;
    byStrategy[version] = {
      strategyVersion: asStringOrNull(row.strategyVersion) ?? version,
      regime: asStringOrNull(row.regime) ?? "",
      measuredN: asNumberOrNull(row.measuredN),
      episodes: asNumberOrNull(row.episodes),
      expectancyR: asNumberOrNull(row.expectancyR),
      probabilityPositive: asNumberOrNull(row.probabilityPositive),
      edgeConfidence: asStringOrNull(row.edgeConfidence),
      notes: asStringArray(row.notes),
    };
  }
  return {
    method: asStringOrNull(value.method),
    regime: asStringOrNull(value.regime),
    adverse: asBooleanOrNull(value.adverse),
    byStrategy,
    notes: asStringArray(value.notes),
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
      correlation:
        root.correlation == null ? null : asCorrelation(root.correlation),
      currentRegime: asStringOrNull(root.currentRegime),
      currentEvidence:
        root.currentEvidence == null
          ? null
          : asCurrentEvidence(root.currentEvidence),
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
  const rootOrigin = artifact.materialOrigin;
  const materialOrigin = artifact.material?.materialOrigin ?? null;
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
  // P3-2: dos orígenes autodeclarados que se contradicen NO se resuelven a favor de `paper_real`.
  if (
    rootOrigin != null &&
    materialOrigin != null &&
    rootOrigin !== materialOrigin
  ) {
    return {
      kind: "desconocido",
      label: "PROCEDENCIA DESCONOCIDA",
      tone: "danger",
      decisionSafe: false,
      caveat: `Contradicción de procedencia autodeclarada: raíz='${rootOrigin}' vs material='${materialOrigin}'; no se asume PAPER real.`,
    };
  }
  const origin = rootOrigin ?? materialOrigin;
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
  correlation: EvidenceRow[];
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

/** Lista del perímetro: ausente/no-array ⇒ `NO MEDIDO`; vacía ⇒ `(ninguna)`. Ausente ≠ `[]` (P3-3). */
function listLabel(value: unknown): string {
  if (!Array.isArray(value)) return "NO MEDIDO";
  return value.length > 0
    ? value.map((item) => String(item)).join(", ")
    : "(ninguna)";
}

/** ¿El valor es una lista medible? (no ausente y no escalar) — espejo de `isinstance(raw, (list, tuple))`. */
function isMeasuredList(value: unknown): value is string[] {
  return Array.isArray(value);
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
      value: listLabel(material.requestedStrategyVersions),
      inconclusive: !isMeasuredList(material.requestedStrategyVersions),
    },
    {
      label: "Versiones observadas",
      value: listLabel(material.observedStrategyVersions),
      inconclusive: !isMeasuredList(material.observedStrategyVersions),
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
  // P3-2: la procedencia autodeclarada en dos sitios no puede contradecirse en silencio.
  const rootOrigin = artifact.materialOrigin;
  const materialOrigin = artifact.material?.materialOrigin ?? null;
  if (
    rootOrigin != null &&
    materialOrigin != null &&
    rootOrigin !== materialOrigin
  ) {
    warnings.push(
      `materialOrigin incoherente: raíz='${rootOrigin}' vs material='${materialOrigin}'.`,
    );
  }
  return warnings;
}

/** Número a 4 decimales; ausente/no finito ⇒ `NO MEDIDO` (a diferencia del veredicto). */
function measureLabel(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(4);
  }
  return NOT_MEASURED;
}

/**
 * AUTO-21 — fila(s) de evidencia del régimen actual. Sin artefacto, sin bloque o sin estrategias ⇒
 * `NO MEDIDO`; con lectura, una línea por estrategia con su `P(R>0)` y su banda. Nunca se inventa.
 */
function currentEvidenceLabel(
  artifact: AutoEvidenceArtifact | null | undefined,
): EvidenceRow[] {
  const evidence = artifact?.currentEvidence ?? null;
  const versions =
    evidence == null ? [] : Object.keys(evidence.byStrategy).sort();
  if (evidence == null || versions.length === 0) {
    return [
      { label: "Current evidence", value: NOT_MEASURED, inconclusive: true },
    ];
  }
  const parts = versions.map((version) => {
    const row = evidence.byStrategy[version];
    const edge = row?.edgeConfidence ?? "UNKNOWN";
    return `${version}: P(R>0) ${measureLabel(row?.probabilityPositive)} (${edge})`;
  });
  return [
    { label: "Current evidence", value: parts.join("; "), inconclusive: false },
  ];
}

/** AUTO-21 — filas del bloque de correlación (una por par); sin lectura ⇒ `[]`. */
function correlationRows(
  artifact: AutoEvidenceArtifact | null | undefined,
): EvidenceRow[] {
  const correlation = artifact?.correlation ?? null;
  if (!correlation || correlation.pairs.length === 0) return [];
  return correlation.pairs.map((pair) => {
    const notes = pair.notes.length > 0 ? ` [${pair.notes.join(", ")}]` : "";
    return {
      label: `${pair.left} vs ${pair.right}`,
      value: `${measureLabel(pair.correlation)} (cubos=${countLabel(
        pair.sharedBuckets,
      )})${notes}`,
      inconclusive: pair.correlation == null,
    };
  });
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
  const currentRegime = artifact?.currentRegime ?? null;
  const currentEvidence = currentEvidenceLabel(artifact);
  return {
    source: classifyEvidenceSource(artifact),
    material: materialRows(artifact?.material ?? null),
    calibration,
    declared: [
      {
        label: "Current regime",
        value: currentRegime ?? NOT_MEASURED,
        inconclusive: currentRegime == null,
      },
      ...currentEvidence,
      {
        label: "Allocation change",
        value: `${ALLOCATION_CHANGE_NONE} (auto18-v1 congelado: la evidencia no mueve el reparto)`,
        inconclusive: false,
      },
    ],
    correlation: correlationRows(artifact),
    perimeter: perimeterRows(artifact?.material ?? null),
    warnings: integrityWarnings(artifact),
  };
}
