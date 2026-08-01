/**
 * Assessment — contrato común de interpretación (RFC-008 Amendment-2).
 *
 * Evidence = observación
 * Assessment = interpretación estructurada (nunca BUY)
 * Decision = acción (solo DecisionRuntime → DecisionPackage)
 */

export type AssessmentType =
  | 'technical'
  | 'fundamental'
  | 'macro'
  | 'news'
  | 'sentiment'
  | 'evidence';

export interface AssessmentV1 {
  artifactType?: 'ART-ASSESSMENT';
  schemaVersion?: '1.0.0';
  assessmentId: string;
  type: AssessmentType;
  instrumentId: string;
  timestamp: string;
  /** Contribución direccional [-1, +1] — no es la decisión. */
  score: number;
  confidence: number;
  facts: string[];
  warnings: string[];
  /** Campos del motor especializado (bias, components, coverage, …). */
  metadata?: Record<string, unknown>;
}
