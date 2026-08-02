from bolsa_analytics.signals.feature_cache import (
    FeatureCacheKey,
    InMemoryFeatureCache,
    get_or_build_preset_features,
    hash_indicator_specs,
)


def test_feature_cache_hit_on_same_key() -> None:
    cache = InMemoryFeatureCache(max_entries=8, ttl_seconds=60)
    specs_hash = hash_indicator_specs([{"definitionId": "sma", "parameters": {"period": 20}}])
    key = FeatureCacheKey.make("inst-1", "1d", 500, 60, "2024-01-60", 150.5, specs_hash)
    timestamps = [f"2024-01-{day:02d}" for day in range(1, 61)]
    closes = [100.0 + day for day in range(1, 61)]

    first = get_or_build_preset_features(cache, key, timestamps, closes)
    second = get_or_build_preset_features(cache, key, timestamps, closes)

    assert first is second
    assert cache.hits == 1
    assert cache.misses == 1


def test_feature_cache_evicts_when_full() -> None:
    cache = InMemoryFeatureCache(max_entries=2, ttl_seconds=60)

    cache.get_or_build("a", lambda: {"v": 1})
    cache.get_or_build("b", lambda: {"v": 2})
    cache.get_or_build("c", lambda: {"v": 3})

    assert len(cache._entries) == 2


def test_hash_indicator_specs_stable() -> None:
    specs_a = [{"definitionId": "rsi", "parameters": {"period": 14}}]
    specs_b = [{"definitionId": "rsi", "parameters": {"period": 14}}]
    assert hash_indicator_specs(specs_a) == hash_indicator_specs(specs_b)

    specs_c = [{"definitionId": "sma", "parameters": {"period": 20}}]
    assert hash_indicator_specs(specs_a) != hash_indicator_specs(specs_c)
