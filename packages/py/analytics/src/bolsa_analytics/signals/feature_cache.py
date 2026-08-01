"""P8 — cache de features por IndicatorSpec hash (in-memory; Redis en infrastructure)."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from bolsa_analytics.signals.evaluate import PresetFeatureSeries, build_preset_features

DEFAULT_CACHE_MAX_ENTRIES = 512
DEFAULT_CACHE_TTL_SECONDS = 3600.0

T = TypeVar("T")


def hash_indicator_specs(specs: list[dict[str, Any]]) -> str:
    """Hash estable de IndicatorSpec[] — clave de partición del cache."""
    if not specs:
        return "none"
    normalized = [
        {
            "definitionId": str(spec.get("definitionId") or ""),
            "parameters": spec.get("parameters") or {},
        }
        for spec in specs
    ]
    normalized.sort(
        key=lambda item: (item["definitionId"], json.dumps(item["parameters"], sort_keys=True)),
    )
    payload = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class FeatureCacheKey:
    @staticmethod
    def make(
        instrument_id: str,
        timeframe: str,
        bar_limit: int,
        bar_count: int,
        last_timestamp: str,
        last_close: float,
        indicator_specs_hash: str,
    ) -> str:
        return (
            f"{instrument_id}:{timeframe}:{bar_limit}:{bar_count}:"
            f"{indicator_specs_hash}:{last_timestamp}:{last_close:.6f}"
        )


class FeatureCache(Protocol):
    hits: int
    misses: int

    def get_or_build(self, key: str, builder: Callable[[], T]) -> T: ...

    def clear(self) -> None: ...


@dataclass
class InMemoryFeatureCache:
    max_entries: int = DEFAULT_CACHE_MAX_ENTRIES
    ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS
    _entries: dict[str, tuple[float, Any]] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def get_or_build(self, key: str, builder: Callable[[], T]) -> T:
        now = time.monotonic()
        cached = self._entries.get(key)
        if cached is not None:
            expires_at, value = cached
            if expires_at > now:
                self.hits += 1
                return value  # type: ignore[no-any-return]
            del self._entries[key]

        self.misses += 1
        value = builder()
        self._entries[key] = (now + self.ttl_seconds, value)
        if len(self._entries) > self.max_entries:
            self._evict_oldest()
        return value

    def _evict_oldest(self) -> None:
        if not self._entries:
            return
        oldest_key = min(self._entries, key=lambda item: self._entries[item][0])
        del self._entries[oldest_key]

    def clear(self) -> None:
        self._entries.clear()
        self.hits = 0
        self.misses = 0


# Retrocompatible SC-5
PresetFeatureCache = InMemoryFeatureCache


def preset_feature_cache_make_key(
    instrument_id: str,
    timeframe: str,
    bar_limit: int,
    bar_count: int,
    last_timestamp: str,
    last_close: float,
    indicator_specs_hash: str = "preset",
) -> str:
    return FeatureCacheKey.make(
        instrument_id,
        timeframe,
        bar_limit,
        bar_count,
        last_timestamp,
        last_close,
        indicator_specs_hash,
    )


PresetFeatureCache.make_key = staticmethod(preset_feature_cache_make_key)  # type: ignore[attr-defined]


def get_or_build_preset_features(
    cache: FeatureCache,
    key: str,
    timestamps: list[str],
    closes: list[float],
) -> PresetFeatureSeries:
    return cache.get_or_build(key, lambda: build_preset_features(timestamps, closes))


_global_feature_cache: FeatureCache = InMemoryFeatureCache()


def get_preset_feature_cache() -> FeatureCache:
    return _global_feature_cache


def set_global_feature_cache(cache: FeatureCache) -> None:
    global _global_feature_cache
    _global_feature_cache = cache
