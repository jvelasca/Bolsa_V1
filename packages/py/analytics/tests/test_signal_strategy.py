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


# ── B-3: el estado ``gated`` viene del libro, no de un replay de la ventana ──────


def _rsi_definition() -> dict:
    return {
        "id": "preset:rsi_mean_reversion",
        "version": 1,
        "name": "RSI reversión",
        "kind": "indicator_signals",
        "presetKey": "rsi_mean_reversion",
        "universe": {"instrumentIds": ["inst-1"]},
        "timeframe": "1d",
        "indicatorSpecs": [{"definitionId": "rsi", "parameters": {"period": 14}}],
    }


def _drop_on_last_bar() -> list[StrategyBarInput]:
    """Plana y un desplome en la ÚLTIMA barra: la entrada nace justo al final."""
    values = [100.0] * 119 + [50.0]
    return [StrategyBarInput(timestamp=f"t{index}", close=v) for index, v in enumerate(values)]


def _jump_on_last_bar() -> list[StrategyBarInput]:
    """Oscilación con RSI ~50 y un salto final que deja RSI > 70 en la última barra.

    La serie plana no sirve: con cero ganancias y cero pérdidas el RSI queda en 100
    desde la primera barra y la salida se cumpliría siempre, no al final.
    """
    values = [100.0 + (0.5 if index % 2 == 0 else -0.5) for index in range(119)] + [120.0]
    return [StrategyBarInput(timestamp=f"t{index}", close=v) for index, v in enumerate(values)]


def _v_bars(up: int = 60, down: int = 60) -> list[StrategyBarInput]:
    """Sube y luego baja: la salida se cumple a mitad de ventana y la entrada al final."""
    values = [100.0 + index for index in range(up)]
    values += [values[-1] - 1.5 * index for index in range(1, down + 1)]
    return [StrategyBarInput(timestamp=f"t{index}", close=v) for index, v in enumerate(values)]


def test_gated_exit_is_reachable_without_entry_in_window() -> None:
    """B-3 (criterio del audit): posición abierta ANTES de la ventana ⇒ el motor vende.

    Sin ``assume_long`` el replay de la ventana no ve la entrada y suprime la salida: el
    portador quedaría atrapado en una posición que su propia regla pide cerrar.
    """
    bars = _jump_on_last_bar()
    raw = evaluate_strategy_last_bar(_rsi_definition(), bars, mode="raw")
    gated_default = evaluate_strategy_last_bar(_rsi_definition(), bars, mode="gated")
    gated_with_book = evaluate_strategy_last_bar(
        _rsi_definition(), bars, mode="gated", assume_long=True
    )

    assert [event.kind for event in raw] == ["exit"]
    assert gated_default == [], "el replay de la ventana no ve la entrada: silencio"
    assert [event.kind for event in gated_with_book] == ["exit"]


def test_assume_long_suppresses_a_second_entry() -> None:
    """Ya dentro: una condición de entrada de nivel no vuelve a comprar."""
    bars = _drop_on_last_bar()
    gated_default = evaluate_strategy_last_bar(_rsi_definition(), bars, mode="gated")
    gated_with_book = evaluate_strategy_last_bar(
        _rsi_definition(), bars, mode="gated", assume_long=True
    )

    assert [event.kind for event in gated_default] == ["entry_long"]
    assert gated_with_book == []


def test_assume_long_does_not_reenter_after_an_in_window_exit() -> None:
    """B-3: si el replay cierra a mitad de ventana, la entrada final NO reabre.

    Es el fallo que destapó el banco de contrato: al arrancar largo, la salida de mitad
    de ventana dejaba ``has_long=False`` y la entrada de la última barra volvía a comprar
    lo que la propia estrategia acababa de vender.
    """
    bars = _v_bars()
    baseline = evaluate_strategy(_rsi_definition(), bars, mode="gated")
    with_book = evaluate_strategy(_rsi_definition(), bars, mode="gated", assume_long=True)

    assert [event.kind for event in baseline] == ["entry_long"]
    assert [event.kind for event in with_book] == ["exit"]


def test_assume_long_does_not_affect_raw_mode() -> None:
    """`raw` no tiene estado: declarar la posición abierta no debe cambiar su respuesta."""
    bars = _jump_on_last_bar()
    baseline = evaluate_strategy_last_bar(_rsi_definition(), bars, mode="raw")
    with_book = evaluate_strategy_last_bar(_rsi_definition(), bars, mode="raw", assume_long=True)

    assert [event.kind for event in baseline] == [event.kind for event in with_book]
