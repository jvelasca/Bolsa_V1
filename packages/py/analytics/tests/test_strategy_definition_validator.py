from bolsa_analytics.research.hybrid_definition import strategy_definition_from_hybrid
from bolsa_analytics.research.strategy_definition_validator import validate_strategy_definition


def test_hybrid_definition_validates() -> None:
    definition = strategy_definition_from_hybrid(
        name="Test hybrid",
        gate_preset_key="price_above_sma200",
        min_score=60,
        instrument_ids=["inst-1"],
    )
    assert definition["kind"] == "hybrid"
    assert validate_strategy_definition(definition) == []
