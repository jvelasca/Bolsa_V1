"""Artefactos Feature Registry (RFC-005) — DEF / SET / SNAP."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class FeatureDef:
    """ART-FEATURE-DEF (payload esencial)."""

    feature_id: str
    version: str
    feature_key: str
    compute_key: str
    engine: str = "bolsa_analytics"
    params: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[str, ...] = ("ohlcv.close",)
    parity_ref: str | None = None
    """Legacy chart definitionId (sma, rsi…) OR canonical IND-* (preferido)."""
    indicator_id: str | None = None
    """Canonical IndicatorUniverse id (IND-RSI). Dueño de la relación Indicator←Feature."""
    output_dtype: str = "float64"
    entity: str = "instrument"
    leakage_risk: Literal["low", "medium", "high"] = "low"
    update_frequency: str = "1d"
    online_ttl_seconds: int | None = 86400

    def to_indicator_spec(self) -> dict[str, Any]:
        """Proyección a IndicatorSpec (chart definitionId + params)."""
        from bolsa_analytics.features.indicator_ids import resolve_chart_definition_id

        raw = self.indicator_id or self.parity_ref or self.compute_key
        definition_id = resolve_chart_definition_id(raw, self.compute_key)
        return {"definitionId": definition_id, "parameters": dict(self.params)}


@dataclass(frozen=True, slots=True)
class FeatureSet:
    """ART-FEATURE-SET."""

    feature_set_id: str
    version: str
    members: tuple[tuple[str, str], ...]  # (feature_id, version)
    composition_hash: str
    name: str = ""


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """ART-FEATURE-SNAP (DTO concreto; satisface FeatureSnapshotDTO)."""

    instrument_id: str
    timestamp: datetime
    feature_set_id: str
    composition_hash: str
    values: dict[str, Any]
    bar_index: int | None = None
    data_version: str | None = None


def composition_hash(members: list[tuple[str, str]] | tuple[tuple[str, str], ...]) -> str:
    """Hash canónico de members ordenados (evoluciona hash P8 de IndicatorSpec[])."""
    normalized = sorted((str(fid), str(ver)) for fid, ver in members)
    payload = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def composition_hash_from_defs(defs: list[FeatureDef]) -> str:
    return composition_hash([(d.feature_id, d.version) for d in defs])
