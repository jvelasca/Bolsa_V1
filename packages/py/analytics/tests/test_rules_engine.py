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
