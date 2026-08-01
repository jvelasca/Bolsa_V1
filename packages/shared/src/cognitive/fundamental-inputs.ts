/**
 * Inputs fundamentales Knowledge Layer (RFC-008 D5).
 * Yahoo quoteSummary v3: marketCap, PE, sector, ROE, márgenes, growth, D/E, currentRatio, Altman Z, FCF yield.
 * Altman: balanceSheetHistory + income (EBIT); fallback EBITDA documentado.
 * Piotroski: F2 (series YoY).
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

export interface FundamentalInputsV1 {
  marketCap?: number | null;
  trailingPe?: number | null;
  forwardPe?: number | null;
  sector?: string | null;
  roe?: number | null;
  roa?: number | null;
  roic?: number | null;
  operatingMargin?: number | null;
  profitMargin?: number | null;
  revenueGrowth?: number | null;
  epsGrowth?: number | null;
  earningsGrowth?: number | null;
  debtToEquity?: number | null;
  currentRatio?: number | null;
  quickRatio?: number | null;
  freeCashflow?: number | null;
  fcfYield?: number | null;
  priceToBook?: number | null;
  piotroski?: number | null;
  altmanZ?: number | null;
  fetchedAt?: string | null;
}
