export function chartTradingViewUrl(symbol?: string, yahooSymbol?: string): string {
  const tvSymbol = yahooSymbol?.replace('.MC', '') ?? symbol ?? '';
  return tvSymbol
    ? `https://www.tradingview.com/chart/?symbol=BME%3A${encodeURIComponent(tvSymbol)}`
    : 'https://www.tradingview.com/chart/';
}
