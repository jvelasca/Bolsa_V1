from unittest.mock import MagicMock

from bolsa_analytics.signals.evaluate import build_preset_features
from bolsa_infrastructure.cache.redis_feature_cache import RedisFeatureCache


def test_redis_feature_cache_hit() -> None:
    redis_client = MagicMock()
    redis_client.get.return_value = None

    cache = RedisFeatureCache.__new__(RedisFeatureCache)
    cache._redis = redis_client
    cache.ttl_seconds = 60
    cache.hits = 0
    cache.misses = 0

    timestamps = ["2024-01-01", "2024-01-02"]
    closes = [100.0, 101.0]
    built = build_preset_features(timestamps, closes)

    def builder():
        return built

    first = cache.get_or_build("key-1", builder)
    assert cache.misses == 1
    assert redis_client.setex.called

    import base64
    import pickle

    encoded = base64.b64encode(pickle.dumps(built)).decode("ascii")
    redis_client.get.return_value = encoded

    second = cache.get_or_build("key-1", builder)
    assert cache.hits == 1
    assert first.sma20 == second.sma20
