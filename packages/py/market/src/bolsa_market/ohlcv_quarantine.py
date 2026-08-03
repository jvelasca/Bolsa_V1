"""Contadores de cuarentena OHLCV (barras descartadas por integridad).

No persiste en BD: métricas de proceso para logs / health / tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

log = logging.getLogger("bolsa_market.ohlcv_quarantine")


@dataclass
class OhlcvQuarantineStats:
    """Acumulado de barras rechazadas en parseo Yahoo."""

    daily_rejected: int = 0
    intradaily_rejected: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(self, *, kind: str, reason: str, symbol: str | None = None) -> None:
        with self._lock:
            if kind == "daily":
                self.daily_rejected += 1
            else:
                self.intradaily_rejected += 1
            self.by_reason[reason] = self.by_reason.get(reason, 0) + 1
        log.warning(
            "ohlcv_quarantine kind=%s reason=%s symbol=%s",
            kind,
            reason,
            symbol or "-",
        )

    def reset(self) -> None:
        with self._lock:
            self.daily_rejected = 0
            self.intradaily_rejected = 0
            self.by_reason.clear()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "daily_rejected": self.daily_rejected,
                "intradaily_rejected": self.intradaily_rejected,
                "by_reason": dict(self.by_reason),
            }


_STATS = OhlcvQuarantineStats()


def get_ohlcv_quarantine_stats() -> OhlcvQuarantineStats:
    """Singleton de cuarentena OHLCV del proceso."""
    return _STATS
