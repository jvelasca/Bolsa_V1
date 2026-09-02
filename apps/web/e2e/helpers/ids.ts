/** E2E identity constants and slice types (V1.64+). */

export const E2E_ACCOUNT_ID = "default-account-seed";
export const E2E_INSTRUMENT_ID = "inst-aapl";
export const E2E_SYMBOL = "AAPL";
export const E2E_WORKSPACE_ID = "ws-e2e-mercado";
export const E2E_MERCADO_ACCOUNT_PREFIX = "e2e-v167";
export const E2E_MERCADO_MULTI_ACCOUNT_PREFIX = "e2e-v173";
export const E2E_HOY_ACCOUNT_PREFIX = "e2e-v168";
export const E2E_PAPER_DAY_ACCOUNT_PREFIX = "e2e-v174";

/** Mock / preferred symbols for multi-instrument integrity (V1.73). */
export const E2E_MULTI_POSITION_INSTRUMENTS = [
  { id: "inst-aapl", symbol: "AAPL", name: "Apple E2E" },
  { id: "inst-msft", symbol: "MSFT", name: "Microsoft E2E" },
  { id: "inst-googl", symbol: "GOOGL", name: "Alphabet E2E" },
] as const;

export const E2E_ENTRY_ONLY_INSTRUMENT = {
  id: "inst-nvda",
  symbol: "NVDA",
  name: "NVIDIA E2E",
} as const;

/** V1.79 — frozen lifecycle identity (AAPL, punta a punta). */
export const E2E_LIFECYCLE_DECISION_ID = "dec-e2e-lifecycle-1";
export const E2E_LIFECYCLE_POSITION_ID = "pos-e2e-lifecycle-1";
export const E2E_LIFECYCLE_TRADE_PLAN_ID = "tp-e2e-lifecycle-1";

export type MercadoLevels = {
  entry: number | null;
  currentStop: number | null;
  target1: number | null;
  target2: number | null;
};

export type MercadoInstrumentSlice = {
  instrumentId: string;
  symbol: string;
  positionId: string;
  tradePlanId: string | null;
  decisionId: string | null;
  levels: MercadoLevels | null;
};
