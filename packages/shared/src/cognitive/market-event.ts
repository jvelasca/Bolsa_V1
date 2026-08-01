/**
 * ART-MARKET-EVENT — eventos estructurados (RFC-008 D4).
 */

export type MarketEventImpact = 'low' | 'medium' | 'high' | 'very_high';

export interface MarketEventV1 {
  artifactType: 'ART-MARKET-EVENT';
  schemaVersion: '1.0.0';
  eventId: string;
  entity: string;
  eventType: string;
  sentiment: number;
  impact: MarketEventImpact;
  horizonDays: number;
  affects: string[];
  source: string;
  credibility: number;
  validFrom: string;
  validTo: string;
}

export interface EventBlackoutContextV1 {
  hoursToEarnings?: number | null;
  hoursSinceEarnings?: number | null;
  highImpactMacroActive: boolean;
  fedFomcActive: boolean;
  ecbActive: boolean;
  activeEventIds: string[];
}
