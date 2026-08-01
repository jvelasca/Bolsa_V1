/**
 * ART-TECHNICAL-ASSESSMENT — Assessment tipado TA (extends AssessmentV1).
 * Emite bias, no BUY. DecisionRuntime traduce bias → Recommendation.
 */

import type { AssessmentV1 } from './assessment.js';

export type DirectionalBias = 'bullish' | 'bearish' | 'neutral';

export interface TechnicalAssessmentV1 extends Omit<AssessmentV1, 'type' | 'facts' | 'artifactType'> {
  artifactType?: 'ART-TECHNICAL-ASSESSMENT';
  type?: 'technical';
  assessmentId: string;
  instrumentId: string;
  timestamp: string;
  /** Score direccional [-1, +1]. */
  score: number;
  bias: DirectionalBias;
  confidence: number;
  coverage: number;
  exhaustion: boolean;
  components: {
    trend?: number;
    momentum?: number;
    volatility?: number;
    pattern?: number;
    volume?: number;
    structure?: number;
    participation?: number;
    [key: string]: number | undefined;
  };
  narrativeFacts: string[];
  /** Alias AssessmentV1.facts */
  facts?: string[];
  warnings: string[];
  factSetRef: string;
}

/** Proyecta TA al envelope común para colecciones heterogéneas. */
export function technicalToAssessment(ta: TechnicalAssessmentV1): AssessmentV1 {
  return {
    artifactType: 'ART-ASSESSMENT',
    schemaVersion: '1.0.0',
    assessmentId: ta.assessmentId,
    type: 'technical',
    instrumentId: ta.instrumentId,
    timestamp: ta.timestamp,
    score: ta.score,
    confidence: ta.confidence,
    facts: ta.facts ?? ta.narrativeFacts,
    warnings: ta.warnings,
    metadata: {
      bias: ta.bias,
      coverage: ta.coverage,
      exhaustion: ta.exhaustion,
      components: ta.components,
      factSetRef: ta.factSetRef,
      specializedArtifactType: ta.artifactType ?? 'ART-TECHNICAL-ASSESSMENT',
    },
  };
}
