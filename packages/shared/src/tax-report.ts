import type { CostBasisMethod, TaxJurisdiction } from './account-settings.js';
import type { PositionDto, TransactionDto } from './types.js';

export interface TaxReportTransaction {
  id: string;
  type: 'buy' | 'sell';
  instrumentId: string;
  symbol: string;
  quantity: number;
  price: number;
  total: number;
  executedAt: string;
  /** Comisiones e impuestos vinculados a esta operación (valor absoluto). */
  feeAmount?: number;
}

export interface RealizedGainLineDto {
  id: string;
  instrumentId: string;
  symbol: string;
  sellTransactionId: string;
  executedAt: string;
  quantity: number;
  sellPrice: number;
  proceeds: number;
  costBasis: number;
  realizedGain: number;
  method: CostBasisMethod;
  /** Fechas de adquisición de los lotes consumidos (FIFO). */
  acquisitionDates: string[];
}

export interface UnrealizedGainLineDto {
  instrumentId: string;
  symbol: string;
  quantity: number;
  avgCost: number;
  marketPrice: number | null;
  costBasis: number;
  marketValue: number | null;
  unrealizedGain: number | null;
}

export interface TaxReportSummaryDto {
  accountId: string;
  currency: string;
  method: CostBasisMethod;
  jurisdiction: TaxJurisdiction;
  year: number;
  periodLabel: string;
  realizedLines: RealizedGainLineDto[];
  totalGains: number;
  totalLosses: number;
  netRealizedGain: number;
  estimatedTaxLiability: number | null;
  unrealizedLines: UnrealizedGainLineDto[];
  totalUnrealizedGain: number | null;
  feesPaidTotal: number;
  dividendWithholdingPct: number;
  openPositionCount: number;
}

export interface BuildTaxReportInput {
  accountId: string;
  currency: string;
  method: CostBasisMethod;
  jurisdiction: TaxJurisdiction;
  year: number;
  fiscalYearStartMonth?: number;
  capitalGainsTaxPct?: number | null;
  dividendWithholdingPct?: number;
  transactions: TransactionDto[];
  feesByTransactionId?: Record<string, number>;
  positions?: PositionDto[];
}

function toReportTx(
  tx: TransactionDto,
  feesByTransactionId?: Record<string, number>,
): TaxReportTransaction {
  return {
    id: tx.id,
    type: tx.type,
    instrumentId: tx.instrumentId,
    symbol: tx.symbol,
    quantity: tx.quantity,
    price: tx.price,
    total: tx.total,
    executedAt: tx.executedAt,
    feeAmount: feesByTransactionId?.[tx.id] ?? 0,
  };
}

function sortByDate(transactions: TaxReportTransaction[]): TaxReportTransaction[] {
  return [...transactions].sort((a, b) => a.executedAt.localeCompare(b.executedAt));
}

interface Lot {
  quantity: number;
  unitCost: number;
  acquiredAt: string;
}

function computeFifoRealized(transactions: TaxReportTransaction[]): RealizedGainLineDto[] {
  const lotsByInstrument = new Map<string, Lot[]>();
  const lines: RealizedGainLineDto[] = [];

  for (const tx of sortByDate(transactions)) {
    if (!lotsByInstrument.has(tx.instrumentId)) {
      lotsByInstrument.set(tx.instrumentId, []);
    }
    const lots = lotsByInstrument.get(tx.instrumentId)!;

    if (tx.type === 'buy') {
      const fee = tx.feeAmount ?? 0;
      lots.push({
        quantity: tx.quantity,
        unitCost: (tx.total + fee) / tx.quantity,
        acquiredAt: tx.executedAt,
      });
      continue;
    }

    let remaining = tx.quantity;
    const sellFee = tx.feeAmount ?? 0;
    const proceedsTotal = tx.total - sellFee;
    const acquisitionDates: string[] = [];
    let costBasis = 0;

    while (remaining > 1e-9) {
      const lot = lots[0];
      if (!lot) break;
      const take = Math.min(remaining, lot.quantity);
      costBasis += take * lot.unitCost;
      acquisitionDates.push(lot.acquiredAt);
      lot.quantity -= take;
      remaining -= take;
      if (lot.quantity <= 1e-9) lots.shift();
    }

    lines.push({
      id: tx.id,
      instrumentId: tx.instrumentId,
      symbol: tx.symbol,
      sellTransactionId: tx.id,
      executedAt: tx.executedAt,
      quantity: tx.quantity,
      sellPrice: tx.price,
      proceeds: proceedsTotal,
      costBasis,
      realizedGain: proceedsTotal - costBasis,
      method: 'fifo',
      acquisitionDates,
    });
  }

  return lines;
}

function computeAverageRealized(transactions: TaxReportTransaction[]): RealizedGainLineDto[] {
  const state = new Map<string, { quantity: number; totalCost: number }>();
  const lines: RealizedGainLineDto[] = [];

  for (const tx of sortByDate(transactions)) {
    if (!state.has(tx.instrumentId)) {
      state.set(tx.instrumentId, { quantity: 0, totalCost: 0 });
    }
    const holding = state.get(tx.instrumentId)!;

    if (tx.type === 'buy') {
      holding.totalCost += tx.total + (tx.feeAmount ?? 0);
      holding.quantity += tx.quantity;
      continue;
    }

    const avgCost = holding.quantity > 0 ? holding.totalCost / holding.quantity : 0;
    const sellFee = tx.feeAmount ?? 0;
    const proceeds = tx.total - sellFee;
    const costBasis = avgCost * tx.quantity;
    holding.totalCost = Math.max(0, holding.totalCost - costBasis);
    holding.quantity = Math.max(0, holding.quantity - tx.quantity);

    lines.push({
      id: tx.id,
      instrumentId: tx.instrumentId,
      symbol: tx.symbol,
      sellTransactionId: tx.id,
      executedAt: tx.executedAt,
      quantity: tx.quantity,
      sellPrice: tx.price,
      proceeds,
      costBasis,
      realizedGain: proceeds - costBasis,
      method: 'average',
      acquisitionDates: [],
    });
  }

  return lines;
}

export function computeRealizedGains(
  transactions: TaxReportTransaction[],
  method: CostBasisMethod,
): RealizedGainLineDto[] {
  if (method === 'average') {
    return computeAverageRealized(transactions);
  }
  return computeFifoRealized(transactions);
}

function isInFiscalYear(isoDate: string, year: number, startMonth: number): boolean {
  const date = new Date(isoDate);
  const month = date.getUTCMonth() + 1;
  const calendarYear = date.getUTCFullYear();
  if (startMonth === 1) {
    return calendarYear === year;
  }
  if (month >= startMonth) {
    return calendarYear === year;
  }
  return calendarYear === year + 1;
}

function periodLabel(year: number, startMonth: number): string {
  if (startMonth === 1) return `Año natural ${year}`;
  return `Ejercicio ${year}/${String((year + 1) % 100).padStart(2, '0')}`;
}

export function buildTaxReport(input: BuildTaxReportInput): TaxReportSummaryDto {
  const startMonth = input.fiscalYearStartMonth ?? 1;
  const reportTx = input.transactions.map((tx) =>
    toReportTx(tx, input.feesByTransactionId),
  );
  const allRealized = computeRealizedGains(reportTx, input.method);
  const realizedLines = allRealized.filter((line) =>
    isInFiscalYear(line.executedAt, input.year, startMonth),
  );

  let totalGains = 0;
  let totalLosses = 0;
  for (const line of realizedLines) {
    if (line.realizedGain >= 0) totalGains += line.realizedGain;
    else totalLosses += line.realizedGain;
  }
  const netRealizedGain = totalGains + totalLosses;

  const feesPaidTotal = reportTx.reduce((sum, tx) => sum + (tx.feeAmount ?? 0), 0);

  const unrealizedLines: UnrealizedGainLineDto[] = (input.positions ?? []).map((pos) => {
    const costBasis = pos.quantity * pos.avgCost;
    const marketValue = pos.marketValue;
    const unrealizedGain =
      marketValue != null ? marketValue - costBasis : null;
    return {
      instrumentId: pos.instrumentId,
      symbol: pos.symbol,
      quantity: pos.quantity,
      avgCost: pos.avgCost,
      marketPrice: pos.lastPrice,
      costBasis,
      marketValue,
      unrealizedGain,
    };
  });

  const totalUnrealizedGain =
    unrealizedLines.length > 0
      ? unrealizedLines.reduce((sum, line) => sum + (line.unrealizedGain ?? 0), 0)
      : null;

  const taxPct = input.capitalGainsTaxPct;
  const estimatedTaxLiability =
    taxPct != null && taxPct > 0 && netRealizedGain > 0
      ? (netRealizedGain * taxPct) / 100
      : null;

  return {
    accountId: input.accountId,
    currency: input.currency,
    method: input.method,
    jurisdiction: input.jurisdiction,
    year: input.year,
    periodLabel: periodLabel(input.year, startMonth),
    realizedLines,
    totalGains,
    totalLosses,
    netRealizedGain,
    estimatedTaxLiability,
    unrealizedLines,
    totalUnrealizedGain,
    feesPaidTotal,
    dividendWithholdingPct: input.dividendWithholdingPct ?? 0,
    openPositionCount: input.positions?.length ?? 0,
  };
}

/** Agrupa fees del ledger por referenceId de la operación. */
export function mapLedgerFeesToTransactions(
  entries: { type: string; amount: number; referenceId: string | null }[],
): Record<string, number> {
  const map: Record<string, number> = {};
  for (const entry of entries) {
    if (entry.type !== 'fee' || !entry.referenceId) continue;
    map[entry.referenceId] = (map[entry.referenceId] ?? 0) + Math.abs(entry.amount);
  }
  return map;
}
