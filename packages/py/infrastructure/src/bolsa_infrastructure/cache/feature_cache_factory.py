"""Factory FeatureCache — memory (default) o Redis (P8)."""

from __future__ import annotations

from functools import lru_cache

from bolsa_analytics.signals.feature_cache import (
    DEFAULT_CACHE_MAX_ENTRIES,
    DEFAULT_CACHE_TTL_SECONDS,
    FeatureCache,
    InMemoryFeatureCache,
    set_global_feature_cache,
)
from bolsa_infrastructure.cache.redis_feature_cache import RedisFeatureCache
from bolsa_infrastructure.config import Settings, get_settings


@lru_cache
def create_feature_cache(settings: Settings | None = None) -> FeatureCache:
    resolved = settings or get_settings()
    backend = resolved.feature_cache_backend.lower().strip()
    if backend == "redis":
        return RedisFeatureCache(
            resolved.redis_url,
            ttl_seconds=resolved.feature_cache_ttl_seconds,
        )
    return InMemoryFeatureCache(
        max_entries=resolved.feature_cache_max_entries,
        ttl_seconds=resolved.feature_cache_ttl_seconds,
    )


def get_feature_cache() -> FeatureCache:
    cache = create_feature_cache()
    set_global_feature_cache(cache)
    return cache
