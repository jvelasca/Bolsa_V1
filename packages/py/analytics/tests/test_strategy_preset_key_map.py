from bolsa_analytics.signals.preset_catalog import is_valid_preset_key


def test_catalog_includes_coach_presets_beyond_sma_rsi():
    assert is_valid_preset_key("sma_crossover")
    assert is_valid_preset_key("rsi_mean_reversion")
    assert is_valid_preset_key("golden_cross")
    assert is_valid_preset_key("macd_signal_cross")
    assert is_valid_preset_key("donchian_breakout")
    assert is_valid_preset_key("supertrend_follow")
    assert not is_valid_preset_key("not_a_real_preset")
    assert not is_valid_preset_key(None)


def test_map_preset_key_logic_matches_catalog():
    """Mirrors SqlAlchemyStrategyDefinitionRepository._map acceptance rules."""

    def map_preset(column: str | None, definition: dict | None) -> str | None:
        preset_key = column if is_valid_preset_key(column) else None
        if preset_key is None and isinstance(definition, dict):
            nested = definition.get("presetKey")
            if isinstance(nested, str) and is_valid_preset_key(nested):
                preset_key = nested
        return preset_key

    assert map_preset("golden_cross", None) == "golden_cross"
    assert map_preset(None, {"presetKey": "macd_signal_cross"}) == "macd_signal_cross"
    assert map_preset("bogus", {"presetKey": "rsi_mean_reversion"}) == "rsi_mean_reversion"
    assert map_preset(None, {"presetKey": "nope"}) is None
