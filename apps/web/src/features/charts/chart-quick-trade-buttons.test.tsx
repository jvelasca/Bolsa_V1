import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ChartQuickTradeButtons,
  instrumentForQuickTrade,
} from "./chart-quick-trade-buttons";
import { useTradingUiStore } from "@/stores/trading-ui-store";

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => ({ entriesBlocked: false }),
}));

const instrument = {
  id: "i-1",
  symbol: "AAPL",
  name: "Apple",
  exchange: "NASDAQ",
  currency: "USD",
  country: "US",
} as const;

describe("ChartQuickTradeButtons", () => {
  it("V y C disparan callbacks distintos y exponen el lado", () => {
    const onBuy = vi.fn();
    const onSell = vi.fn();
    render(<ChartQuickTradeButtons onBuy={onBuy} onSell={onSell} />);

    const sell = screen.getByTestId("chart-quick-sell");
    const buy = screen.getByTestId("chart-quick-buy");
    expect(sell).toHaveAttribute("data-side", "sell");
    expect(buy).toHaveAttribute("data-side", "buy");

    fireEvent.click(sell);
    expect(onSell).toHaveBeenCalledTimes(1);
    expect(onBuy).not.toHaveBeenCalled();

    fireEvent.click(buy);
    expect(onBuy).toHaveBeenCalledTimes(1);
  });
});

describe("instrumentForQuickTrade", () => {
  it("usa la última vela como precio y calcula la variación vs la anterior", () => {
    const result = instrumentForQuickTrade(instrument, [
      {
        timestamp: "2026-10-31",
        open: 100,
        high: 102,
        low: 99,
        close: 100,
        volume: 10,
        adjClose: 100,
        source: "yahoo",
      },
      {
        timestamp: "2026-11-01",
        open: 100,
        high: 111,
        low: 100,
        close: 110,
        volume: 12,
        adjClose: 110,
        source: "yahoo",
      },
    ]);

    expect(result.meta.lastClose).toBe(110);
    expect(result.meta.changePct).toBeCloseTo(10);
    expect(result.meta.barCount).toBe(2);
  });
});

describe("trading-ui-store · lado sugerido", () => {
  beforeEach(() => {
    useTradingUiStore.setState({
      orderInstrument: null,
      orderPreset: null,
      orderSideHint: null,
    });
  });

  it("abre con el lado V/C sin pre-armar confirmación", () => {
    useTradingUiStore
      .getState()
      .openOrderDialog(instrument as never, null, "sell");

    const state = useTradingUiStore.getState();
    expect(state.orderPreset).toBeNull();
    expect(state.orderSideHint).toBe("sell");
  });

  it("el preset de salida mantiene su lado y se limpia al cerrar", () => {
    useTradingUiStore
      .getState()
      .openOrderDialog(instrument as never, { side: "buy", quantity: 5 });

    expect(useTradingUiStore.getState().orderSideHint).toBe("buy");
    useTradingUiStore.getState().closeOrderDialog();
    expect(useTradingUiStore.getState().orderSideHint).toBeNull();
    expect(useTradingUiStore.getState().orderPreset).toBeNull();
  });
});
