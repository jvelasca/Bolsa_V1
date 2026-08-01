"""Modelos Knowledge Layer / ART-FACT-SET (RFC-008 D2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TechnicalInputs:
    """Snapshot de features numéricas para interpretación TA (última barra)."""

    rsi: float | None = None
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    # OBV slope: >0 rising, <0 falling
    obv_slope: float | None = None
    price_slope: float | None = None
    # Bandwidth relativo (upper-lower)/mid * 100
    bb_width_pct: float | None = None
    atr: float | None = None
    # Percentil histórico del ATR (0–100)
    atr_percentile: float | None = None
    close: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None

    @staticmethod
    def from_feature_map(values: dict[str, Any]) -> TechnicalInputs:
        """Acepta keys de catálogo (rsi_14_close, adx_14, …) o alias cortos."""

        def g(*keys: str) -> float | None:
            for k in keys:
                if k in values and values[k] is not None:
                    try:
                        return float(values[k])
                    except (TypeError, ValueError):
                        return None
            return None

        return TechnicalInputs(
            rsi=g("rsi", "rsi_14_close", "feat_rsi_14_close"),
            adx=g("adx", "adx_14", "feat_adx_14"),
            plus_di=g("plus_di", "adx_14_plus_di", "di_plus"),
            minus_di=g("minus_di", "adx_14_minus_di", "di_minus"),
            obv_slope=g("obv_slope", "obv_delta"),
            price_slope=g("price_slope", "close_delta"),
            bb_width_pct=g("bb_width_pct", "bb_bandwidth_pct"),
            atr=g("atr", "atr_14", "feat_atr_14"),
            atr_percentile=g("atr_percentile", "atr_14_percentile"),
            close=g("close", "ohlcv.close"),
            sma_20=g("sma_20", "sma_20_close", "feat_sma_20_close"),
            sma_50=g("sma_50", "sma_50_close", "feat_sma_50_close"),
        )


@dataclass(frozen=True, slots=True)
class Fact:
    fact_id: str
    key: str
    value: str
    confidence: float
    claim: str
    refs: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "factId": self.fact_id,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "claim": self.claim,
            "refs": self.refs,
        }


@dataclass(frozen=True, slots=True)
class FactSet:
    fact_set_id: str
    instrument_id: str
    timestamp: str
    facts: tuple[Fact, ...]
    artifact_type: str = "ART-FACT-SET"
    schema_version: str = "1.0.0"
    source: str = "technical_v1"

    def get(self, key: str) -> Fact | None:
        for f in self.facts:
            if f.key == key:
                return f
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "factSetId": self.fact_set_id,
            "instrumentId": self.instrument_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "facts": [f.to_dict() for f in self.facts],
        }
