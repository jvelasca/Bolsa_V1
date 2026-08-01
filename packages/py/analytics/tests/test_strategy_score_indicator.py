from bolsa_analytics.indicators.compute import OhlcvBar, compute_spec, IndicatorSpecInput
from bolsa_analytics.research.llm_indicator_draft import draft_indicator_from_prompt_with_llm
from bolsa_analytics.research.prompt_indicator_draft import draft_indicator_from_prompt
from bolsa_analytics.signals.rules_engine import compute_rule_group_pass_series
from bolsa_analytics.signals.preset_catalog import preset_indicator_specs, preset_rule_groups


def _bars(count: int = 120) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []
    price = 100.0
    for index in range(count):
        price += 0.2
        bars.append(
            OhlcvBar(
                timestamp=f"2024-01-{(index % 28) + 1:02d}",
                open=price - 0.1,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=1_000_000.0,
            )
        )
    return bars


def test_compute_strategy_hybrid_score_with_gate() -> None:
    result = compute_spec(
        _bars(),
        IndicatorSpecInput(
            definition_id="strategy_hybrid_score_v1",
            parameters={
                "warmupBars": 50,
                "minScore": 60,
                "gatePresetKey": "price_above_sma200",
                "showGateLine": True,
            },
        ),
    )
    keys = {line.key for line in result.lines}
    assert "main" in keys
    assert "gate" in keys
    gate_points = next(line for line in result.lines if line.key == "gate").points
    assert len(gate_points) > 0
    assert all(point.value in (0.0, 100.0) for point in gate_points)


def test_gate_pass_series_price_above_sma200() -> None:
    bars = _bars(250)
    groups = preset_rule_groups("price_above_sma200")
    specs = preset_indicator_specs("price_above_sma200")
    series = compute_rule_group_pass_series(
        bars,
        groups["entries"],
        [dict(spec) for spec in specs],
    )
    assert len(series) == len(bars)
    assert any(value == 100.0 for value in series if value is not None)


def test_llm_indicator_draft_fallback_without_api_key(monkeypatch) -> None:
    from bolsa_ai import reset_default_proxy

    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_default_proxy()
    heuristic = draft_indicator_from_prompt("RSI 14")
    llm = draft_indicator_from_prompt_with_llm("RSI 14")
    assert llm.definition_id == heuristic.definition_id
    assert llm.engine == "indicator_prompt_catalog_v1"
