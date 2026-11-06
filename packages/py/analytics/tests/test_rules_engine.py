from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.preset_rules import preset_rule_groups
from bolsa_analytics.signals.rules_engine import (
    evaluate_exit_last_bar_gated,
    evaluate_rules_signals,
)
from bolsa_analytics.signals.strategy import StrategyBarInput, evaluate_strategy


def _sample_bars() -> tuple[list[str], list[float]]:
    timestamps = [f"2024-01-{day:02d}" for day in range(1, 61)]
    closes = [100.0 + day * 0.5 for day in range(1, 61)]
    return timestamps, closes


def test_preset_rule_groups_match_sma_crossover() -> None:
    groups = preset_rule_groups("sma_crossover")
    assert groups["entries"]["rules"][0]["type"] == "indicator_cross"
    assert groups["exits"]["rules"][0]["direction"] == "bearish"


def test_rules_engine_gated_matches_preset_sma() -> None:
    timestamps, closes = _sample_bars()
    definition = strategy_definition_from_preset("sma_crossover", ["inst-1"])
    from bolsa_analytics.signals.evaluate import evaluate_preset_signals_gated

    preset_events = evaluate_preset_signals_gated("sma_crossover", timestamps, closes)
    rule_events = evaluate_rules_signals(definition, timestamps, closes, mode="gated")
    assert len(rule_events) == len(preset_events)


def test_evaluate_strategy_uses_rules_path_with_preset_definition() -> None:
    timestamps, closes = _sample_bars()
    definition = strategy_definition_from_preset("sma_crossover", ["inst-1"])
    bars = [
        StrategyBarInput(timestamp=ts, close=close)
        for ts, close in zip(timestamps, closes, strict=True)
    ]

    rule_events = evaluate_rules_signals(definition, timestamps, closes, mode="gated")
    strategy_events = evaluate_strategy(definition, bars, mode="gated")
    assert len(strategy_events) == len(rule_events)


def test_evaluate_exit_last_bar_returns_none_without_exit_rule() -> None:
    timestamps, closes = _sample_bars()
    definition = strategy_definition_from_preset("sma_crossover", ["inst-1"])
    assert evaluate_exit_last_bar_gated(definition, timestamps, closes) is None


# ── ADR-048 — una sola semántica de salida: última barra con OHLCV REAL ──────────────


def _vwap_exit_definition() -> dict[str, object]:
    """Salida por ``precio < vwap``: depende del VOLUMEN, así que close-only la degrada.

    Es el caso que separa las dos rutas: con ``volume = 0`` el VWAP no existe
    (``cum_vol = 0``), la regla no dispara y la posición no se cierra.
    """
    spec = {"definitionId": "vwap", "parameters": {}}
    return {
        "id": "strat-vwap",
        "version": 1,
        "presetKey": "vwap_reclaim",
        "indicatorSpecs": [spec],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_vs_indicator",
                    "indicatorSpec": spec,
                    "operator": "gt",
                    "signalKind": "entry_long",
                }
            ],
        },
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_vs_indicator",
                    "indicatorSpec": spec,
                    "operator": "lt",
                    "signalKind": "exit",
                }
            ],
        },
    }


def _real_bars_with_a_gap_down() -> tuple[list[str], list[float], list[OhlcvBar]]:
    """Volumen alto sobre precios altos y un último cierre muy por debajo del VWAP."""
    timestamps = [f"2024-02-{day:02d}" for day in range(1, 31)]
    closes = [100.0] * 29 + [50.0]
    bars = [
        OhlcvBar(
            timestamp=ts,
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=10_000.0,
        )
        for ts, close in zip(timestamps, closes, strict=True)
    ]
    return timestamps, closes, bars


def test_the_real_ohlcv_path_can_emit_an_exit_the_close_only_path_cannot() -> None:
    """El OHLCV real cierra; la ventana close-only (``volume = 0``) no lo ve.

    Es el delta que motiva ADR-048: el mismo preset, la misma barra y **dos** resultados
    según el dato. La ruta de producto es la real; la close-only se conserva como wrapper.
    """
    timestamps, closes, bars = _real_bars_with_a_gap_down()
    definition = _vwap_exit_definition()

    assert evaluate_exit_last_bar_gated(definition, timestamps, closes, bars=bars) is not None
    assert evaluate_exit_last_bar_gated(definition, timestamps, closes) is None


def test_the_close_only_wrapper_keeps_the_historical_signal() -> None:
    """Sin ``bars`` la geometría es ``open = high = low = close`` y ``volume = 0``."""
    timestamps, closes = _sample_bars()
    definition = strategy_definition_from_preset("sma_crossover", ["inst-1"])

    historical = evaluate_exit_last_bar_gated(definition, timestamps, closes)
    same_bars = [
        OhlcvBar(timestamp=ts, open=c, high=c, low=c, close=c, volume=0.0)
        for ts, c in zip(timestamps, closes, strict=True)
    ]

    assert historical == evaluate_exit_last_bar_gated(
        definition, timestamps, closes, bars=same_bars
    )


def test_the_real_ohlcv_path_ignores_a_misaligned_window() -> None:
    """Una ventana desalineada no es una ventana: fail-closed en vez de índice torcido."""
    timestamps, closes, bars = _real_bars_with_a_gap_down()
    definition = _vwap_exit_definition()

    assert (
        evaluate_exit_last_bar_gated(definition, timestamps, closes, bars=bars[:-1]) is None
    )
