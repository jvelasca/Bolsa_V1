/**
 * Fundamental / Macro / Evidence Assessment contracts (RFC-008 Amendment-2).
 */

import type { AssessmentV1 } from './assessment.js';
import type { EdgeBand } from './evidence-engine.js';
import type { DirectionalBias } from './technical-assessment.js';

export interface FundamentalAssessmentV1 extends Omit<AssessmentV1, 'type' | 'facts' | 'artifactType'> {
  artifactType?: 'ART-FUNDAMENTAL-ASSESSMENT';
  type?: 'fundamental';
  bias: DirectionalBias;
  coverage: number;
  distress: boolean;
  components: Record<string, number>;
  narrativeFacts: string[];
  facts?: string[];
  factSetRef: string;
}

export interface MacroAssessmentV1 extends Omit<AssessmentV1, 'type' | 'facts' | 'artifactType'> {
  artifactType?: 'ART-MACRO-ASSESSMENT';
  type?: 'macro';
  bias: DirectionalBias;
  coverage: number;
  stress: boolean;
  regime: string;
  tradability: 'tradable' | 'reduce' | 'wait';
  components: Record<string, number>;
  narrativeFacts: string[];
  facts?: string[];
  factSetRef: string;
}

export interface EvidenceAssessmentV1 extends Omit<AssessmentV1, 'type' | 'facts' | 'artifactType'> {
  artifactType?: 'ART-EVIDENCE-ASSESSMENT';
  type?: 'evidence';
  band: EdgeBand;
  credibility: number;
  edgeScore: number;
  autoLiveEligible: boolean;
  narrativeFacts: string[];
  facts?: string[];
  edgeReportRef: string;
}

export interface NewsAssessmentV1 extends Omit<AssessmentV1, 'type' | 'facts' | 'artifactType'> {
  artifactType?: 'ART-NEWS-ASSESSMENT';
  type?: 'news';
  bias: DirectionalBias;
  coverage: number;
  sentiment: number;
  eventCount: number;
  narrativeFacts: string[];
  facts?: string[];
  eventIds: string[];
}

export function fundamentalToAssessment(fa: FundamentalAssessmentV1): AssessmentV1 {
  return {
    artifactType: 'ART-ASSESSMENT',
    schemaVersion: '1.0.0',
    assessmentId: fa.assessmentId,
    type: 'fundamental',
    instrumentId: fa.instrumentId,
    timestamp: fa.timestamp,
    score: fa.score,
    confidence: fa.confidence,
    facts: fa.facts ?? fa.narrativeFacts,
    warnings: fa.warnings,
    metadata: {
      bias: fa.bias,
      coverage: fa.coverage,
      distress: fa.distress,
      components: fa.components,
      factSetRef: fa.factSetRef,
    },
  };
}

export function macroToAssessment(ma: MacroAssessmentV1): AssessmentV1 {
  return {
    artifactType: 'ART-ASSESSMENT',
    schemaVersion: '1.0.0',
    assessmentId: ma.assessmentId,
    type: 'macro',
    instrumentId: ma.instrumentId,
    timestamp: ma.timestamp,
    score: ma.score,
    confidence: ma.confidence,
    facts: ma.facts ?? ma.narrativeFacts,
    warnings: ma.warnings,
    metadata: {
      bias: ma.bias,
      coverage: ma.coverage,
      stress: ma.stress,
      regime: ma.regime,
      tradability: ma.tradability,
      components: ma.components,
      factSetRef: ma.factSetRef,
    },
  };
}

export function evidenceToAssessment(ea: EvidenceAssessmentV1): AssessmentV1 {
  return {
    artifactType: 'ART-ASSESSMENT',
    schemaVersion: '1.0.0',
    assessmentId: ea.assessmentId,
    type: 'evidence',
    instrumentId: ea.instrumentId,
    timestamp: ea.timestamp,
    score: ea.score,
    confidence: ea.confidence,
    facts: ea.facts ?? ea.narrativeFacts,
    warnings: ea.warnings,
    metadata: {
      band: ea.band,
      credibility: ea.credibility,
      edgeScore: ea.edgeScore,
      autoLiveEligible: ea.autoLiveEligible,
      edgeReportRef: ea.edgeReportRef,
      directional: false,
    },
  };
}

export function newsToAssessment(na: NewsAssessmentV1): AssessmentV1 {
  return {
    artifactType: 'ART-ASSESSMENT',
    schemaVersion: '1.0.0',
    assessmentId: na.assessmentId,
    type: 'news',
    instrumentId: na.instrumentId,
    timestamp: na.timestamp,
    score: na.score,
    confidence: na.confidence,
    facts: na.facts ?? na.narrativeFacts,
    warnings: na.warnings,
    metadata: {
      bias: na.bias,
      coverage: na.coverage,
      sentiment: na.sentiment,
      eventCount: na.eventCount,
      eventIds: na.eventIds,
    },
  };
}
