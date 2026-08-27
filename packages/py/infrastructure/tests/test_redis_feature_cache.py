from unittest.mock import MagicMock

import pytest

from bolsa_analytics.signals.evaluate import build_preset_features
from bolsa_infrastructure.cache.redis_feature_cache import (
    RedisFeatureCache,
    decode_feature_payload,
    encode_feature_payload,
)


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

    encoded = encode_feature_payload(built)
    redis_client.get.return_value = encoded

    second = cache.get_or_build("key-1", builder)
    assert cache.hits == 1
    assert first.sma20 == second.sma20


def test_decode_rejects_checksum_mismatch() -> None:
    timestamps = ["2024-01-01", "2024-01-02"]
    closes = [100.0, 101.0]
    built = build_preset_features(timestamps, closes)
    import json

    payload = json.loads(encode_feature_payload(built))
    payload["sha256"] = payload["sha256"][:-1] + (
        "0" if payload["sha256"][-1] != "0" else "1"
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        decode_feature_payload(json.dumps(payload))


def test_tampered_blob_is_cache_miss_not_unpickled() -> None:
    redis_client = MagicMock()
    timestamps = ["2024-01-01", "2024-01-02"]
    closes = [100.0, 101.0]
    built = build_preset_features(timestamps, closes)
    import json

    payload = json.loads(encode_feature_payload(built))
    payload["sha256"] = "0" * 64
    redis_client.get.return_value = json.dumps(payload)

    cache = RedisFeatureCache.__new__(RedisFeatureCache)
    cache._redis = redis_client
    cache.ttl_seconds = 60
    cache.hits = 0
    cache.misses = 0

    rebuilt = cache.get_or_build("key-1", lambda: built)
    assert cache.hits == 0
    assert cache.misses == 1
    assert rebuilt.sma20 == built.sma20
