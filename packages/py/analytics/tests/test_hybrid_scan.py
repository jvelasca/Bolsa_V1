from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.hybrid_scan import (
    evaluate_hybrid_candidate,
    is_hybrid_definition,
    passes_hybrid_gate,
)
from bolsa_analytics.signals.preset_catalog import preset_indicator_specs, preset_rule_groups
from bolsa_analytics.signals.strategy import StrategyBarInput


def _hybrid_definition(
    gate_preset: str = "price_above_sma200",
    min_score: float = 50.0,
) -> dict:
    gate_rules = preset_rule_groups(gate_preset)["entries"]
    return {
        "id": f"hybrid:{gate_preset}:{min_score}",
        "version": 1,
        "kind": "hybrid",
        "presetKey": gate_preset,
        "indicatorSpecs": preset_indicator_specs(gate_preset),
        "hybrid": {
            "ruleGate": gate_rules,
            "aiScorer": {
                "modelId": "technical_rating_v1",
                "minScore": min_score,
                "version": "1.0.0",
            },
            "gatePresetKey": gate_preset,
        },
    }


def _synthetic_uptrend_bars(count: int = 220) -> tuple[list[OhlcvBar], list[StrategyBarInput]]:
    ohlcv: list[OhlcvBar] = []
    strategy: list[StrategyBarInput] = []
    price = 100.0
    for index in range(count):
        price += 0.35 + (index % 5) * 0.05
        timestamp = f"2024-01-{(index % 28) + 1:02d}"
        ohlcv.append(
            OhlcvBar(
                timestamp=timestamp,
                open=price - 0.2,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=1_000_000.0,
            )
        )
        strategy.append(StrategyBarInput(timestamp=timestamp, close=price))
    return ohlcv, strategy


def test_is_hybrid_definition() -> None:
    definition = _hybrid_definition()
    assert is_hybrid_definition(definition)
    assert not is_hybrid_definition({"kind": "indicator_signals"})


def test_hybrid_candidate_passes_gate_and_min_score() -> None:
    definition = _hybrid_definition(min_score=50.0)
    ohlcv, strategy = _synthetic_uptrend_bars()
    from bolsa_analytics.signals.hybrid_scan import build_indicator_context_for_definition

    context = build_indicator_context_for_definition(ohlcv, definition)
    assert passes_hybrid_gate(definition, bars=strategy, indicator_context=context)

    candidate = evaluate_hybrid_candidate(
        definition,
        instrument_id="inst-1",
        symbol="TEST.MC",
        name="Test",
        ohlcv_bars=ohlcv,
        strategy_bars=strategy,
        indicator_context=context,
        strategy_definition_id="hybrid-test",
        strategy_version=1,
    )
    assert candidate is not None
    assert candidate.ai_score >= 50.0
    assert candidate.data_quality_score >= 0.0
    assert candidate.global_score >= candidate.ai_score * 0.7
    assert candidate.signal.kind == "watch"


def test_hybrid_candidate_rejected_below_min_score() -> None:
    definition = _hybrid_definition(min_score=95.0)
    ohlcv, strategy = _synthetic_uptrend_bars()
    from bolsa_analytics.signals.hybrid_scan import build_indicator_context_for_definition

    context = build_indicator_context_for_definition(ohlcv, definition)
    candidate = evaluate_hybrid_candidate(
        definition,
        instrument_id="inst-1",
        symbol="TEST.MC",
        name="Test",
        ohlcv_bars=ohlcv,
        strategy_bars=strategy,
        indicator_context=context,
        strategy_definition_id="hybrid-test",
        strategy_version=1,
    )
    assert candidate is None
