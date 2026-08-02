"""Macro snapshot desde Yahoo (^VIX, curva proxy) — RFC-008 D6 feed live."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bolsa_market.yahoo_chart import YahooMarketDataProvider
from bolsa_market.yahoo_client import get_yahoo_finance_client

# Símbolos Yahoo (índices US)
VIX_SYMBOL = "^VIX"
TNX_SYMBOL = "^TNX"  # 10Y yield (%)
FVX_SYMBOL = "^FVX"  # 5Y yield (%) — proxy de tramo corto vs 2Y puro

_CACHE: dict[str, Any] | None = None
_CACHE_AT: float = 0.0
_CACHE_TTL_SEC = 900.0  # 15 min


def _percentile_rank(values: list[float], current: float) -> float:
    if not values:
        return 50.0
    below = sum(1 for v in values if v <= current)
    return round(100.0 * below / len(values), 1)


async def fetch_macro_snapshot_dict(
    *,
    provider: YahooMarketDataProvider | None = None,
    use_cache: bool = True,
) -> dict[str, Any] | None:
    """
    Devuelve dict compatible con MacroInputs.from_dict.
    Si Yahoo falla parcialmente, rellena lo disponible; si no hay VIX → None.
    """
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if use_cache and _CACHE is not None and (now - _CACHE_AT) < _CACHE_TTL_SEC:
        return dict(_CACHE)

    prov = provider or YahooMarketDataProvider(get_yahoo_finance_client())
    to_d = date.today()
    from_d = to_d - timedelta(days=400)

    vix: float | None = None
    vix_pct: float | None = None
    curve_bps: float | None = None

    try:
        vix_bars = await prov.fetch_daily_bars(VIX_SYMBOL, from_d, to_d)
        closes = [float(b.close) for b in vix_bars if b.close is not None]
        if closes:
            vix = closes[-1]
            vix_pct = _percentile_rank(closes[-252:] if len(closes) >= 20 else closes, vix)
    except Exception:
        vix = None

    try:
        tnx_bars = await prov.fetch_daily_bars(TNX_SYMBOL, to_d - timedelta(days=14), to_d)
        fvx_bars = await prov.fetch_daily_bars(FVX_SYMBOL, to_d - timedelta(days=14), to_d)
        tnx = float(tnx_bars[-1].close) if tnx_bars else None
        fvx = float(fvx_bars[-1].close) if fvx_bars else None
        if tnx is not None and fvx is not None:
            # Diferencial 10Y−5Y en bps (proxy de pendiente; no es 10Y−2Y exacto)
            curve_bps = round((tnx - fvx) * 100.0, 1)
    except Exception:
        curve_bps = None

    if vix is None and curve_bps is None:
        return None

    snap = {
        "vix": vix,
        "vixPercentile": vix_pct,
        "yieldCurve10y2yBps": curve_bps,
        "fetchedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sourceVersion": "yahoo_macro_v1",
        "notes": ["curve=10Y−5Y (^TNX−^FVX) proxy"],
    }
    if use_cache:
        _CACHE = dict(snap)
        _CACHE_AT = now
    return snap


class YahooMacroSnapshotPort:
    """Adaptador MacroSnapshotPort para ProposeRecommendationFromTa."""

    def __init__(self, provider: YahooMarketDataProvider | None = None) -> None:
        self._provider = provider

    async def get_macro(self) -> dict[str, Any] | None:
        return await fetch_macro_snapshot_dict(provider=self._provider, use_cache=True)


def clear_macro_snapshot_cache() -> None:
    global _CACHE, _CACHE_AT
    _CACHE = None
    _CACHE_AT = 0.0
