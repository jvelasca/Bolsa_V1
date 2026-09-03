export type MarketDataProviderId = "yahoo" | "xtb";

export type Timeframe = "1m" | "5m" | "15m" | "1h" | "1d";

export type InstrumentType = "stock";

export type SyncStatus = "success" | "partial" | "failed";

export type DataFreshnessStatus =
  | "current"
  | "stale"
  | "empty"
  | "error"
  | "gap_detected"
  | "syncing";

export interface InstrumentDataStatusDto {
  timeframe: string;
  lastBarDate: string | null;
  expectedLastBarDate: string;
  freshnessStatus: DataFreshnessStatus;
  barCount: number;
  lastSyncStatus: SyncStatus | null;
  lastSyncAt: string | null;
  lastSyncError: string | null;
  sanityWarnings: string[];
  gapCount: number;
  xtbVsCloseDeviationPct: number | null;
  lastXtbQuoteAt: string | null;
}

export interface InstrumentSearchResult {
  symbol: string;
  yahooSymbol: string;
  name: string;
  exchange: string;
  currency: string;
  type: InstrumentType;
}

export interface OhlcvBar {
  timestamp: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjClose?: number;
}

export interface ExternalInstrumentSearchHitDto {
  symbol: string;
  yahooSymbol: string;
  name: string;
  exchange: string;
  currency: string;
  isin?: string | null;
}

export interface InstrumentSearchResponseDto {
  catalog: InstrumentWithMetaDto[];
  external: ExternalInstrumentSearchHitDto[];
}

export interface ImportInstrumentResponseDto {
  data: InstrumentWithMetaDto;
  meta: {
    created: boolean;
    sync: {
      barsAdded: number;
      status: string;
      error?: string | null;
    } | null;
  };
}

export interface InstrumentDto {
  id: string;
  symbol: string;
  yahooSymbol: string;
  name: string;
  exchange: string;
  country: string;
  currency: string;
  sector: string | null;
  isin?: string | null;
  isActive: boolean;
}

export interface OhlcvBarDto {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjClose: number | null;
  source: MarketDataProviderId;
}

export type ListDataFreshnessStatus = "current" | "stale" | "empty" | "error";

export interface InstrumentListMetaDto {
  barCount: number;
  lastSync: {
    status: SyncStatus;
    syncedAt: string;
    error: string | null;
  } | null;
  lastClose: number | null;
  changePct: number | null;
  /** Última vela diaria en BD (YYYY-MM-DD). */
  lastBarDate?: string | null;
  /** Frescura calendario vs mercado (listas / badge sync). */
  freshnessStatus?: ListDataFreshnessStatus;
  /** Fecha de vela diaria esperada hoy (calendario bolsa). */
  expectedLastBarDate?: string | null;
}

export interface InstrumentProfileFieldDto {
  label: string;
  value: string;
}

export interface InstrumentProfileSectionDto {
  title: string;
  fields?: InstrumentProfileFieldDto[];
  text?: string;
}

export interface InstrumentProfileTabDto {
  sections: InstrumentProfileSectionDto[];
  history?: Array<{ date: string; amount: number | null }>;
}

export interface InstrumentProfileDto {
  fetchedAt: string | null;
  basic: InstrumentProfileTabDto;
  dividends: InstrumentProfileTabDto;
  financials: InstrumentProfileTabDto;
}

export interface InstrumentOhlcvLayerDto {
  timeframe: string;
  source: string;
  barCount: number;
  firstDate: string | null;
  lastDate: string | null;
}

export interface InstrumentSyncLogEntryDto {
  provider: string;
  status: SyncStatus;
  barsAdded: number;
  syncedAt: string;
  error: string | null;
}

export interface InstrumentAppDataCountsDto {
  positions: number;
  transactions: number;
  backtestRuns: number;
  listMemberships: number;
  priceAlerts: number;
  pendingOrders: number;
  ledgerEntries: number;
}

export interface InstrumentRecordDto {
  id: string;
  symbol: string;
  yahooSymbol: string;
  name: string;
  exchange: string;
  country: string;
  currency: string;
  sector: string | null;
  isin?: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  profileFetchedAt?: string | null;
  lastXtbValidation?: InstrumentXtbValidationDto | null;
}

export interface InstrumentDbInventoryDto {
  instrument: InstrumentRecordDto;
  ohlcvLayers: InstrumentOhlcvLayerDto[];
  recentSyncLogs: InstrumentSyncLogEntryDto[];
  appData: InstrumentAppDataCountsDto;
  derivedDataNotes: string[];
}

export type InstrumentXtbRecommendation =
  | "aligned"
  | "review"
  | "unavailable"
  | "no_db_reference";

export interface InstrumentXtbValidationDto {
  available: boolean;
  message: string;
  dbLastClose: number | null;
  dbLastDate: string | null;
  xtbLast: number | null;
  xtbBid: number | null;
  xtbAsk: number | null;
  xtbTimestamp: string | null;
  deviationPct: number | null;
  recommendation: InstrumentXtbRecommendation;
  validatedAt: string;
  wroteToDb: boolean;
}

export interface InstrumentWithMetaDto extends InstrumentDto {
  meta: InstrumentListMetaDto;
}

export interface PriceSummaryDto {
  lastClose: number;
  previousClose: number | null;
  changeAbs: number | null;
  changePct: number | null;
  periodLow: number;
  periodHigh: number;
  barCount: number;
  firstDate: string;
  lastDate: string;
}

export interface IndicatorPointDto {
  timestamp: string;
  sma20: number | null;
  sma50: number | null;
  ema20: number | null;
  rsi14: number | null;
}

export type TransactionType = "buy" | "sell";

export interface PortfolioDto {
  id: string;
  name: string;
  currency: string;
  cash: number;
}

export interface OperationalExitPlanDto {
  status: string;
  suggestedAction: string;
  primaryReason: string | null;
  /** V1.29 — qty según ExitPolicy (T1/T2); puede faltar en wire legado. */
  suggestedQty?: number | null;
  /** P4.2 / V1.29 — advisory stop sugerido (protect). */
  suggestedStop?: number | null;
  /** V1.29 — plantilla que parametrizó la sugerencia. */
  policyTemplateId?: string | null;
  trailWidth?: string | null;
}

/** V1.18 L2a — tesis de nacimiento congelada al fill. */
export interface OriginThesisSnapshotDto {
  decisionId: string;
  instrumentId?: string | null;
  status?: string | null;
  opinion?: string | null;
  tradePlanStatus?: string | null;
  hasOperationalPlan?: boolean;
  strength?: number | null;
  entry?: number | null;
  stop?: number | null;
  target1?: number | null;
  target2?: number | null;
  expectedRR?: number | null;
  riskAmount?: number | null;
  direction?: "long" | "short" | string | null;
}

export interface OperationalPositionDto {
  status: string;
  direction: string;
  currentStop: number | null;
  target1: number | null;
  target2: number | null;
  /** V1.65 — origen Decision (≠ tradePlanId cuando ambos existen). */
  decisionId?: string | null;
  tradePlanId: string;
  /** V1.65 — POV canónico del servidor (PositionOperationalView). */
  operationalView?: Record<string, unknown> | null;
  unrealizedR?: number | null;
  plannedEntry?: number | null;
  actualEntry?: number | null;
  initialStop?: number | null;
  exitPlan?: OperationalExitPlanDto | null;
  originThesis?: OriginThesisSnapshotDto | null;
  /** V1.91 — lifecycle FSM stage (from portfolio; Mesa avoids N+1 snapshot). */
  lifecycleStage?: string | null;
}

export interface PositionDto {
  id: string;
  instrumentId: string;
  symbol: string;
  name: string;
  quantity: number;
  avgCost: number;
  lastPrice: number | null;
  marketValue: number | null;
  unrealizedPnl: number | null;
  unrealizedPnlPct: number | null;
  /** Sector del instrumento cuando el API lo proyecta (puede faltar). */
  sector?: string | null;
  operational?: OperationalPositionDto | null;
}

export interface TransactionDto {
  id: string;
  type: TransactionType;
  instrumentId: string;
  symbol: string;
  quantity: number;
  price: number;
  total: number;
  executedAt: string;
}

export interface PortfolioSummaryDto {
  portfolio: PortfolioDto;
  positions: PositionDto[];
  totalMarketValue: number;
  totalCost: number;
  totalUnrealizedPnl: number;
  totalEquity: number;
}

export type BacktestStrategyType =
  import("./strategy-presets.js").BacktestStrategyType;

export type { StrategyPresetCategory } from "./strategy-presets.js";

export {
  BACKTEST_STRATEGIES,
  STRATEGY_PRESET_KEYS,
  STRATEGY_PRESET_CATALOG,
  STRATEGY_PRESET_CATEGORY_LABELS,
  isBacktestStrategyType,
  presetRuleGroups,
  presetIndicatorSpecs,
  presetsByCategory,
} from "./strategy-presets.js";

export interface BacktestTradeDto {
  id: string;
  type: TransactionType;
  timestamp: string;
  price: number;
  quantity: number;
  equityAfter: number;
  /** Why the H0 engine traded — from manifest.outputs.tradeReasons (new runs). */
  reason?: BacktestTradeReasonDto | null;
}

export interface BacktestTradeReasonDto {
  summary: string;
  signalKind?: string;
  side?: string;
  presetKey?: string | null;
  price?: number;
  barIndex?: number;
  rules?: Array<Record<string, unknown>>;
}

export interface BacktestEquityPointDto {
  timestamp: string;
  equity: number;
}

export interface BacktestRunDto {
  id: string;
  instrumentId: string;
  symbol: string;
  name: string;
  strategyType: BacktestStrategyType;
  initialCash: number;
  finalEquity: number;
  totalReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  winCount: number;
  barCount: number;
  firstDate: string;
  lastDate: string;
  createdAt: string;
  /** H0 — contrato research platform */
  timeframe?: string | null;
  dataVersion?: string | null;
  commissionBps?: number | null;
  slippageBps?: number | null;
  manifest?: import("./research-platform.js").RunManifest | null;
  strategyDefinitionId?: string | null;
}

export interface BacktestRunDetailDto extends BacktestRunDto {
  trades: BacktestTradeDto[];
  /** Serie patrimonio por barra (desde manifest.outputs o runs nuevos). */
  equityCurve?: BacktestEquityPointDto[] | null;
}

/** Respuesta POST /backtests/run — ADR-016 Fase 1 */
export interface BacktestRunResponseDto {
  data: BacktestRunDetailDto;
  trialId?: string;
  metrics?: Record<string, number | string | null>;
}

export interface LiveQuoteSourceDto {
  price: number;
  timestamp: string;
  source: "db" | "live";
}

export interface XtbQuoteDto {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  timestamp: string;
}

export interface InstrumentListSummaryDto {
  id: string;
  name: string;
  source: "catalog" | "custom" | string;
  itemCount: number;
  updatedAt: string;
  kind?: "personal" | "linked_universe" | "snapshot" | string | null;
  universeCode?: string | null;
  lastSyncedAt?: string | null;
  contentHash?: string | null;
}

export interface InstrumentListDetailDto {
  id: string;
  name: string;
  source: "catalog" | "custom" | string;
  instrumentIds: string[];
  updatedAt: string;
  kind?: "personal" | "linked_universe" | "snapshot" | string | null;
  universeCode?: string | null;
  lastSyncedAt?: string | null;
  contentHash?: string | null;
  membershipChangelog?: {
    at?: string;
    joined?: string[];
    left?: string[];
    joinedCount?: number;
    leftCount?: number;
  } | null;
}

export interface InstrumentLiveQuoteDto {
  instrumentId: string;
  symbol: string;
  reference: LiveQuoteSourceDto | null;
  xtb: XtbQuoteDto | null;
  spreadPct: number | null;
  xtbAvailable: boolean;
}

export interface FxRateDto {
  from: string;
  to: string;
  rate: number;
  yahooSymbol: string;
  timestamp: string;
  source: string;
}

export interface MarketProviderStatusDto {
  id: MarketDataProviderId;
  label: string;
  enabled: boolean;
  healthy: boolean;
  message: string;
  mode?: string | null;
}

export type AlertCondition = "above" | "below";
export type AlertPriceSource = "daily_close" | "xtb_last";

export interface PriceAlertDto {
  id: string;
  instrumentId: string;
  symbol: string;
  condition: AlertCondition;
  priceSource: AlertPriceSource;
  targetPrice: number;
  isActive: boolean;
  triggeredAt: string | null;
  triggeredPrice: number | null;
  note: string | null;
  createdAt: string;
}

export interface DatabaseTableCountDto {
  table: string;
  label: string;
  count: number;
}

export interface InstrumentOhlcvBreakdownDto {
  timeframe: string;
  barCount: number;
}

export interface DatabaseSummaryDto {
  connected: boolean;
  message: string;
  tables: DatabaseTableCountDto[];
  instrumentOhlcv: InstrumentOhlcvBreakdownDto[];
}

export interface ListMembershipRefDto {
  listId: string;
  listName: string;
  source: string;
}

export interface NamedDependencyRefDto {
  id: string;
  name: string;
  detail?: string | null;
}

/** Impacto al quitar de listas / purgar de BD. */
export interface InstrumentRemovalPreviewDto {
  instrumentId: string;
  symbol: string;
  name: string;
  listMemberships: ListMembershipRefDto[];
  remainingListCount: number;
  trackersByInstrument: NamedDependencyRefDto[];
  trackersByList: NamedDependencyRefDto[];
  priceAlertsActive: number;
  priceAlertsTotal: number;
  signalAlertsActive: number;
  signalAlertsTotal: number;
  positions: number;
  pendingOrders: number;
  transactions: number;
  backtestRuns: number;
  ledgerEntries: number;
  ohlcvBarCount: number;
  wouldBeOrphan: boolean;
  canPurge: boolean;
  purgeBlockedReasons: string[];
  purgeWarnings: string[];
}

export interface RemoveInstrumentFromListResultDto {
  listId: string;
  instrumentId: string;
  removedFromList: boolean;
  becameOrphan: boolean;
  purged: boolean;
  purgeSkippedReasons: string[];
  preview: InstrumentRemovalPreviewDto | null;
}

export interface OrphanInstrumentDto {
  id: string;
  symbol: string;
  name: string;
  ohlcvBarCount: number;
}

export interface OrphanInstrumentsDto {
  orphans: OrphanInstrumentDto[];
  totalOhlcvBars: number;
}

export interface PurgeOrphansResultDto {
  purgedIds: string[];
  skipped: { instrumentId: string; symbol: string; reasons: string[] }[];
  scanned: number;
}

/** Demo simulada cerrada — candidata a purga en Configuración → BD. */
export interface ClosedSimulatedAccountDto {
  id: string;
  name: string;
  currency: string;
  updatedAt: string;
  ledgerEntryCount: number;
  portfolioCount: number;
  positionCount: number;
  transactionCount: number;
  pendingOrderCount: number;
}

export interface ClosedSimulatedAccountsDto {
  accounts: ClosedSimulatedAccountDto[];
  totalLedgerEntries: number;
}

export interface PurgeClosedAccountsResultDto {
  purgedIds: string[];
  skipped: { accountId: string; name: string; reasons: string[] }[];
  scanned: number;
}

export const TIMEFRAMES = {
  DAILY: "1d" as const,
} as const;

export const DEFAULT_TIMEFRAME: Timeframe = TIMEFRAMES.DAILY;
