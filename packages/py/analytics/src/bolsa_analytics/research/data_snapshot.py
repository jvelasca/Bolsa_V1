"""Data snapshot hashing — reproducible research runs."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BarFingerprint:
    timestamp: str
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None


def compute_data_version(bars: Sequence[BarFingerprint]) -> str:
    """Stable hash of the full OHLCV series used in a run.

    Hashea los cinco campos OHLCV (timestamp, open, high, low, close, volume)
    con precisión ``:.8f``. Para callers que solo aportan ``close``, los precios
    abren en ``close`` y el volumen en ``0`` (no rompe la firma existente). Detectar
    cambios en ATR/Keltner/Volumen y costes v2 exige aportar OHLCV completo (P0.2).
    """
    digest = hashlib.sha256()
    for bar in bars:
        open_ = bar.open if bar.open is not None else bar.close
        high = bar.high if bar.high is not None else bar.close
        low = bar.low if bar.low is not None else bar.close
        volume = float(bar.volume if bar.volume is not None else 0.0)
        digest.update(
            (
                f"{bar.timestamp}|{open_:.8f}|{high:.8f}|{low:.8f}|{bar.close:.8f}|{volume:.8f}"
            ).encode()
        )
    return f"sha256:{digest.hexdigest()[:16]}"


def build_data_snapshot_id(
    instrument_id: str,
    timeframe: str,
    data_version: str,
) -> str:
    raw = f"{instrument_id}:{timeframe}:{data_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
