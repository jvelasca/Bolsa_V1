/**
 * Market State Engine contracts (RFC-008 D6).
 * Régimen / macro antes del TA — no es la decisión.
 */

export type MarketRegimeV1 =
  | 'risk_on'
  | 'neutral'
  | 'risk_off'
  | 'crisis'
  | 'uncertain';

export type TradabilityV1 = 'tradable' | 'reduce' | 'wait';

export type HorizonHint = 'intraday' | 'swing' | 'position' | 'long_term';

export interface MacroInputsV1 {
  vix?: number | null;
  vixPercentile?: number | null;
  yieldCurve10y2yBps?: number | null;
  creditSpreadOasBps?: number | null;
  usdDxyChange5dPct?: number | null;
  breadthPctAboveMa50?: number | null;
  fetchedAt?: string | null;
}

export interface WeightRuleResultV1 {
  wTa: number;
  wFund: number;
  wMacro: number;
  wNews: number;
  horizon: HorizonHint;
  regime: MarketRegimeV1;
  rationale: string;
  sizeHint: number;
  vetoNewLong: boolean;
}

export interface MarketStateV1 {
  stateId: string;
  timestamp: string;
  regime: MarketRegimeV1;
  tradability: TradabilityV1;
  tradable: boolean;
  scoreMacro: number;
  coverage: number;
  stress: boolean;
  factSetId: string;
  notes: string[];
}

export interface ContextValidationResultV1 {
  valid: boolean;
  reason: string;
  marketStateId?: string | null;
  highImpactMacroActive: boolean;
}
