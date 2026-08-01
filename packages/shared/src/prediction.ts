/**
 * Prediction / Model stubs (RFC-006 §7.3–7.4) — contratos UI/API.
 * Inferencia canónica en Python (Quant Runtime); no LLM.
 */

export interface ModelArtifactV1 {
  artifactType?: 'ART-MODEL';
  modelId: string;
  modelVersion: string;
  framework: 'lightgbm' | 'heuristic' | 'numpy_fallback' | string;
  featureSetId: string;
  compositionHash: string;
  target: { name: string; type: 'continuous' | 'class' | 'rank' };
  metrics?: Record<string, number | null>;
  modelChecksum: string;
  hyperparameters?: Record<string, unknown>;
  trainedAt?: string;
}

export interface PredictionV1 {
  artifactType?: 'ART-PREDICTION';
  schemaVersion: string;
  predictionId: string;
  instrumentId: string;
  modelId: string;
  modelVersion: string;
  modelChecksum: string;
  featureSetId: string;
  compositionHash: string;
  featureSnapshotId?: string | null;
  timestamp: string;
  asOf: string;
  horizon: string;
  /** Score tipado: dirección [-1,+1] o probabilidad según modelId. */
  value: number | Record<string, number>;
  confidence: number;
  probabilities?: Record<string, number>;
  dataVersion?: string | null;
  traceId?: string | null;
}
