"""Puente Feature Registry ↔ compute_spec (paridad IndicatorSpec)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bolsa_analytics.features.catalog import FeatureCatalog, bootstrap_catalog
from bolsa_analytics.features.models import FeatureDef, FeatureSnapshot
from bolsa_analytics.features.online_adapter import OnlineFeatureAdapter
from bolsa_analytics.indicators.compute import (
    IndicatorSpecInput,
    OhlcvBar,
    compute_spec,
)


def _last_line_value(result_lines: list[Any], preferred_key: str | None) -> float | None:
    if not result_lines:
        return None
    line = None
    if preferred_key:
        for candidate in result_lines:
            if candidate.key == preferred_key:
                line = candidate
                break
    if line is None:
        line = result_lines[0]
    if not line.points:
        return None
    return float(line.points[-1].value)


def compute_feature_value(bars: list[OhlcvBar], feature_def: FeatureDef) -> float | None:
    """Último valor de la feature vía compute_spec (indicator_id / parity_ref → chart)."""
    from bolsa_analytics.features.indicator_ids import resolve_chart_definition_id

    params = dict(feature_def.params)
    line_key = params.pop("line", None)
    params.pop("source", None)
    raw = feature_def.indicator_id or feature_def.parity_ref or feature_def.compute_key
    result = compute_spec(
        bars,
        IndicatorSpecInput(
            definition_id=resolve_chart_definition_id(raw, feature_def.compute_key),
            parameters=params,
        ),
    )
    preferred = str(line_key) if line_key is not None else "main"
    return _last_line_value(result.lines, preferred)


def compute_feature_set_values(
    bars: list[OhlcvBar],
    *,
    catalog: FeatureCatalog | None = None,
    feature_set_id: str = "fset_core_v1",
) -> dict[str, float | None]:
    cat = catalog or bootstrap_catalog()
    feature_set = cat.get_set(feature_set_id)
    values: dict[str, float | None] = {}
    for feature_id, _version in feature_set.members:
        feature_def = cat.get_def(feature_id)
        values[feature_def.feature_key] = compute_feature_value(bars, feature_def)
    return values


def materialize_feature_snapshot(
    adapter: OnlineFeatureAdapter,
    *,
    instrument_id: str,
    bars: list[OhlcvBar],
    feature_set_id: str = "fset_core_v1",
) -> FeatureSnapshot | None:
    """
    Calcula el set core y lo publica en el adapter (IFeaturePort.get_latest).
    Best-effort para scans: no falla el hot path si falta valor.
    """
    if not bars:
        return None
    values = compute_feature_set_values(
        bars,
        catalog=adapter.catalog,
        feature_set_id=feature_set_id,
    )
    # Solo materializar si hay al menos un valor numérico
    numeric = {k: v for k, v in values.items() if v is not None}
    if not numeric:
        return None
    ts_raw = bars[-1].timestamp
    try:
        timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except ValueError:
        timestamp = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return adapter.materialize_latest_from_values(
        instrument_id=instrument_id,
        feature_set_id=feature_set_id,
        values=numeric,
        timestamp=timestamp,
    )
