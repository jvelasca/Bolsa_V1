"""Data snapshot hashing — reproducible research runs."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BarFingerprint:
    timestamp: str
    close: float


def compute_data_version(bars: Sequence[BarFingerprint]) -> str:
    """Stable hash of OHLCV series used in a run (timestamp + close)."""
    digest = hashlib.sha256()
    for bar in bars:
        digest.update(f"{bar.timestamp}|{bar.close:.8f}".encode())
    return f"sha256:{digest.hexdigest()[:16]}"


def build_data_snapshot_id(
    instrument_id: str,
    timeframe: str,
    data_version: str,
) -> str:
    raw = f"{instrument_id}:{timeframe}:{data_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
