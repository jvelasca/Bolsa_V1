/**
 * Índices de mercado — aliases + tipos (capa A discovery).
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 */

export type MarketIndexHitDto = {
  code: string | null;
  displayName: string;
  yahooSymbol: string;
  region: string | null;
  currency: string | null;
  quoteType: string;
  source: string;
  constituentReady: boolean;
  score: number;
};

export type IndexConstituentMemberDto = {
  symbol: string;
  yahooSymbol: string;
  name: string | null;
};

export type IndexConstituentsDto = {
  indexCode: string;
  yahooIndexSymbol: string;
  provider: string;
  asOf: string;
  contentHash: string;
  members: IndexConstituentMemberDto[];
};

export type SubscribeMarketIndexResultDto = {
  listId: string;
  indexCode: string;
  displayName: string;
  yahooIndexSymbol: string;
  contentHash: string;
  instrumentIds: string[];
  progress: {
    total: number;
    alreadyPresent: number;
    imported: number;
    failed: string[];
    joined: string[];
    left: string[];
  };
  status: 'ready' | 'partial' | string;
};

export type CatalogIndexEntryDto = {
  code: string;
  displayName: string;
  yahooSymbol: string;
  region: string;
  currency: string;
  constituentReady: boolean;
  expectedCountMin: number;
  expectedCountMax: number;
  listId: string;
};

export type IndexSubscribeJobDto = {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | string;
  payload: {
    indexKey?: string;
    syncBars?: boolean;
    yearsBack?: number;
    [key: string]: unknown;
  };
  result: {
    phase?: string;
    checked?: number;
    total?: number;
    alreadyPresent?: number;
    imported?: number;
    failed?: string[];
    currentSymbol?: string;
    listId?: string;
    indexCode?: string;
    displayName?: string;
    instrumentIds?: string[];
    status?: string;
    joined?: string[];
    left?: string[];
    [key: string]: unknown;
  } | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
};

/** Alias humano → código canónico (espejo Python). */
export const MARKET_INDEX_ALIASES: Record<string, string> = {
  ibex: 'IBEX35',
  ibex35: 'IBEX35',
  'ibex 35': 'IBEX35',
  '^ibex': 'IBEX35',
  sp500: 'SPX',
  spx: 'SPX',
  's&p500': 'SPX',
  's&p 500': 'SPX',
  '^gspc': 'SPX',
  sp100: 'OEX',
  's&p100': 'OEX',
  's&p 100': 'OEX',
  oex: 'OEX',
  dax: 'DAX',
  dax40: 'DAX',
  '^gdaxi': 'DAX',
  ndx: 'NDX',
  nasdaq100: 'NDX',
  'nasdaq 100': 'NDX',
  eurostoxx50: 'STOXX50E',
  'euro stoxx 50': 'STOXX50E',
  stoxx50: 'STOXX50E',
  dow: 'DJI',
  dowjones: 'DJI',
  'dow jones': 'DJI',
  djia: 'DJI',
  '^dji': 'DJI',
  dji: 'DJI',
  ftse: 'FTSE100',
  ftse100: 'FTSE100',
  'ftse 100': 'FTSE100',
  '^ftse': 'FTSE100',
  ftsemib: 'FTSEMIB',
  'ftse mib': 'FTSEMIB',
  mib: 'FTSEMIB',
  'hang seng': 'HSI',
  hangseng: 'HSI',
  hsi: 'HSI',
  '^hsi': 'HSI',
};

export function canonicalMarketIndexCode(query: string): string | null {
  const key = query.trim().toLowerCase().replace(/\s+/g, ' ');
  return MARKET_INDEX_ALIASES[key] ?? null;
}

/** ID estable de InstrumentList catalog para un índice (espejo Python). */
export function catalogListIdForIndex(code: string): string {
  const normalized = code.trim().toUpperCase();
  if (normalized === 'IBEX35') return 'ibex35';
  return `idx-${normalized.toLowerCase()}`;
}
