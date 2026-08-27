"""Redis backend para FeatureCache (P8) — compartido entre workers Arq."""

from __future__ import annotations

import base64
import hashlib
import json
import pickle
from collections.abc import Callable
from typing import Any, TypeVar

import redis

T = TypeVar("T")

REDIS_KEY_PREFIX = "bolsa:features:v2:"


def _checksum(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def encode_feature_payload(value: Any) -> str:
    blob = pickle.dumps(value)
    return json.dumps(
        {
            "sha256": _checksum(blob),
            "blob": base64.b64encode(blob).decode("ascii"),
        }
    )


def decode_feature_payload(raw: str) -> Any:
    payload = json.loads(raw)
    digest = payload["sha256"]
    blob = base64.b64decode(str(payload["blob"]).encode("ascii"))
    if _checksum(blob) != digest:
        raise ValueError("Feature cache checksum mismatch")
    return pickle.loads(blob)


class RedisFeatureCache:
    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: float = 3600.0,
    ) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _redis_key(self, key: str) -> str:
        return f"{REDIS_KEY_PREFIX}{key}"

    def get_or_build(self, key: str, builder: Callable[[], T]) -> T:
        redis_key = self._redis_key(key)
        try:
            raw = self._redis.get(redis_key)
        except Exception:
            raw = None

        if raw is not None:
            try:
                value = decode_feature_payload(raw)
                self.hits += 1
                return value  # type: ignore[no-any-return]
            except Exception:
                pass

        self.misses += 1
        value = builder()
        try:
            encoded = encode_feature_payload(value)
            self._redis.setex(redis_key, int(self.ttl_seconds), encoded)
        except Exception:
            pass
        return value

    def clear(self) -> None:
        self.hits = 0
        self.misses = 0
        try:
            cursor = 0
            pattern = f"{REDIS_KEY_PREFIX}*"
            while True:
                cursor, keys = self._redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._redis.close()
        except Exception:
            pass
