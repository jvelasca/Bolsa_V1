"""Entidad de dominio de vela OHLCV de mercado — sin dependencias externas."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class OhlcvBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = None
    source: Literal["yahoo", "xtb"] = "yahoo"
