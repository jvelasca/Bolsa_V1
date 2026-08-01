/**
 * Feature Registry stubs (RFC-005) — alineados a bolsa_analytics.features.
 * Contratos TS para UI/API; compute canónico sigue en Python.
 */

export type FeatureLeakageRisk = 'low' | 'medium' | 'high';

export interface FeatureDefV1 {
  featureId: string;
  version: string;
  featureKey: string;
  computeKey: string;
  engine?: string;
  params?: Record<string, unknown>;
  inputs?: string[];
  parityRef?: string | null;
  outputDtype?: string;
  entity?: string;
  leakageRisk?: FeatureLeakageRisk;
  updateFrequency?: string;
  onlineTtlSeconds?: number | null;
}

export interface FeatureSetV1 {
  featureSetId: string;
  version: string;
  name?: string;
  members: Array<{ featureId: string; version: string }>;
  compositionHash: string;
}

export interface FeatureSnapshotV1 {
  instrumentId: string;
  featureSetId: string;
  compositionHash: string;
  timestamp: string;
  values: Record<string, number | null | undefined>;
  barIndex?: number | null;
  dataVersion?: string | null;
}

export interface FeatureCatalogResponseV1 {
  defs: FeatureDefV1[];
  sets: FeatureSetV1[];
}
