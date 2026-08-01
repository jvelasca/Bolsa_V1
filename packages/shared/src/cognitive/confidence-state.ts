/**
 * ART-CONFIDENCE-STATE — Confidence Lifecycle (RFC-008 D7 §12).
 * confidence_0 → eventos → hint hold/tighten/reduce/exit/expire.
 */

export type ConfidenceHint = 'hold' | 'tighten' | 'reduce' | 'exit' | 'expire';

export type ConfidenceEventKind =
  | 'market_event'
  | 'regime_change'
  | 'invalidator'
  | 'evidence_update'
  | 'time_decay'
  | 'manual';

export interface ConfidenceEventV1 {
  kind: ConfidenceEventKind;
  delta: number;
  claim: string;
  at: string;
  refs?: Record<string, string>;
}

export interface ConfidenceStateV1 {
  artifactType: 'ART-CONFIDENCE-STATE';
  schemaVersion: '1.0.0';
  stateId: string;
  decisionId: string;
  instrumentId: string;
  confidence0: number;
  confidence: number;
  hint: ConfidenceHint;
  expiresAt?: string | null;
  expired: boolean;
  events: ConfidenceEventV1[];
  notes: string[];
  createdAt: string;
  updatedAt: string;
}

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

export function hintForConfidence(
  confidence: number,
  opts: { expired?: boolean; hardExit?: boolean } = {},
): ConfidenceHint {
  if (opts.expired) return 'expire';
  if (opts.hardExit || confidence < 0.25) return 'exit';
  if (confidence < 0.45) return 'reduce';
  if (confidence < 0.65) return 'tighten';
  return 'hold';
}

export function applyConfidenceDelta(
  confidence: number,
  delta: number,
): number {
  return Math.round(clamp01(confidence + delta) * 10000) / 10000;
}
