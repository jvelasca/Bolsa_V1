import { render, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { ReactNode } from 'react';
import { DEFAULT_CHART_CONFIG, type OhlcvBarDto } from '@bolsa/shared';
import { OhlcvChart } from './ohlcv-chart';

const sampleBars: OhlcvBarDto[] = [
  {
    timestamp: '2024-01-02',
    open: 10.52,
    high: 10.88,
    low: 10.41,
    close: 10.76,
    volume: 12450000,
    adjClose: 10.76,
    source: 'yahoo',
  },
];

const setData = vi.fn();
const fitContent = vi.fn();
const remove = vi.fn();

vi.mock('lightweight-charts', () => ({
  CandlestickSeries: 'CandlestickSeries',
  HistogramSeries: 'HistogramSeries',
  LineSeries: 'LineSeries',
  ColorType: { Solid: 'solid' },
  CrosshairMode: { Normal: 0, Magnet: 1 },
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({ setData })),
    applyOptions: vi.fn(),
    remove,
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    timeScale: vi.fn(() => ({ fitContent })),
  })),
}));

const config = {
  ...DEFAULT_CHART_CONFIG,
  display: { ...DEFAULT_CHART_CONFIG.display, height: 300 },
};

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('OhlcvChart', () => {
  it('muestra mensaje cuando no hay barras', () => {
    const { container } = renderWithProviders(<OhlcvChart bars={[]} config={config} />);

    expect(within(container).getByText(/Sin datos OHLCV/i)).toBeInTheDocument();
  });

  it('renderiza contenedor del gráfico con datos', () => {
    const { container } = renderWithProviders(<OhlcvChart bars={sampleBars} config={config} />);

    expect(within(container).queryByText(/Sin datos OHLCV/i)).not.toBeInTheDocument();
    expect(container.querySelector('.w-full')).toBeTruthy();
  });
});
