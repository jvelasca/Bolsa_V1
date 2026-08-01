from bolsa_analytics.backtest import BacktestBarInput, run_backtest
from bolsa_analytics.signals.strategy import (
    StrategyBarInput,
    drawing_marker_to_signal_event_v1,
    evaluate_strategy,
    evaluate_strategy_last_bar,
)


def _sma_crossover_definition(instrument_id: str = "inst-1") -> dict:
    return {
        "id": "preset:sma_crossover",
        "version": 1,
        "name": "Cruce SMA 20/50",
        "kind": "indicator_signals",
        "presetKey": "sma_crossover",
        "universe": {"instrumentIds": [instrument_id]},
        "timeframe": "1d",
        "indicatorSpecs": [
            {"definitionId": "sma", "parameters": {"period": 20}},
            {"definitionId": "sma", "parameters": {"period": 50}},
        ],
    }


def _sample_bars() -> list[StrategyBarInput]:
    return [
        StrategyBarInput(timestamp=f"2024-01-{day:02d}", close=100.0 + day * 0.5)
        for day in range(1, 61)
    ]


def test_evaluate_strategy_gated_matches_backtest() -> None:
    bars = _sample_bars()
    backtest_bars = [BacktestBarInput(timestamp=bar.timestamp, close=bar.close) for bar in bars]
    result = run_backtest(backtest_bars, "sma_crossover", 10000)

    events = evaluate_strategy(_sma_crossover_definition(), bars, mode="gated")

    assert len(events) == len(result.trades)
    for event, trade in zip(events, result.trades, strict=True):
        assert event.instrument_id == "inst-1"
        assert event.strategy_definition_id == "preset:sma_crossover"
        assert event.timestamp == trade.timestamp
        assert event.price == trade.price
        if trade.type == "buy":
            assert event.kind == "entry_long"
        else:
            assert event.kind == "exit"


def test_evaluate_strategy_raw_emits_more_than_gated() -> None:
    bars = _sample_bars()
    raw = evaluate_strategy(_sma_crossover_definition(), bars, mode="raw")
    gated = evaluate_strategy(_sma_crossover_definition(), bars, mode="gated")
    assert len(raw) >= len(gated)


def test_infer_preset_from_indicator_specs() -> None:
    definition = {
        "id": "draft-rsi",
        "version": 1,
        "universe": {"instrumentIds": ["x"]},
        "indicatorSpecs": [{"definitionId": "rsi", "parameters": {"period": 14}}],
    }
    bars = _sample_bars()
    events = evaluate_strategy(definition, bars, mode="gated")
    assert all(event.preset_key == "rsi_mean_reversion" for event in events)


def test_evaluate_strategy_last_bar_filters_to_final_bar() -> None:
    bars = _sample_bars()
    all_events = evaluate_strategy(_sma_crossover_definition(), bars, mode="raw")
    last_bar = evaluate_strategy_last_bar(_sma_crossover_definition(), bars, mode="raw")
    last_index = len(bars) - 1

    assert all(event.bar_index == last_index for event in last_bar)
    expected = [event for event in all_events if event.bar_index == last_index]
    assert len(last_bar) == len(expected)


def test_drawing_marker_to_signal_event_v1() -> None:
    event = drawing_marker_to_signal_event_v1(
        {
            "id": "m1",
            "drawingId": "d1",
            "timestamp": "2024-01-10",
            "price": 105.5,
            "direction": "up",
        },
        instrument_id="inst-1",
        strategy_definition_id="strat-1",
        strategy_version=2,
        bar_index=9,
    )
    assert event.kind == "entry_long"
    assert event.bar_index == 9
    assert event.strategy_version == 2
