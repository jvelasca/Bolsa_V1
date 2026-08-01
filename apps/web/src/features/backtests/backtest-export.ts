import type { BacktestEquityPointDto, BacktestRunDetailDto, BacktestTradeDto } from '@bolsa/shared';

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvEscape(value: string | number): string {
  const text = String(value);
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

export function equityCurveFromDetail(detail: BacktestRunDetailDto): BacktestEquityPointDto[] {
  if (detail.equityCurve?.length) return detail.equityCurve;
  const manifestCurve = detail.manifest?.outputs?.equityCurve;
  return manifestCurve ?? [];
}

export function exportBacktestJson(detail: BacktestRunDetailDto) {
  const payload = {
    ...detail,
    equityCurve: equityCurveFromDetail(detail),
  };
  downloadBlob(
    `backtest-${detail.id}.json`,
    JSON.stringify(payload, null, 2),
    'application/json',
  );
}

export function exportTradesCsv(detail: BacktestRunDetailDto) {
  const header = ['timestamp', 'type', 'price', 'quantity', 'equityAfter'];
  const rows = detail.trades.map((trade: BacktestTradeDto) =>
    [trade.timestamp, trade.type, trade.price, trade.quantity, trade.equityAfter]
      .map(csvEscape)
      .join(','),
  );
  downloadBlob(`backtest-${detail.id}-trades.csv`, [header.join(','), ...rows].join('\n'), 'text/csv');
}

export function exportEquityCsv(detail: BacktestRunDetailDto) {
  const curve = equityCurveFromDetail(detail);
  const header = ['timestamp', 'equity'];
  const rows = curve.map((point) =>
    [point.timestamp, point.equity].map(csvEscape).join(','),
  );
  downloadBlob(
    `backtest-${detail.id}-equity.csv`,
    [header.join(','), ...rows].join('\n'),
    'text/csv',
  );
}
