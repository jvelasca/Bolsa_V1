"""F2+ — catálogo ≥10 + paridad FeatureDef ↔ compute_spec."""

from __future__ import annotations

from datetime import datetime, timezone

from bolsa_analytics.features import (
    OnlineFeatureAdapter,
    bootstrap_catalog,
    compute_feature_set_values,
    compute_feature_value,
    materialize_feature_snapshot,
)
from bolsa_analytics.indicators.compute import IndicatorSpecInput, OhlcvBar, compute_spec


def _bars() -> list[OhlcvBar]:
    closes = [100, 102, 104, 106, 108, 107, 105, 107, 112, 114, 113, 115, 116, 118, 117, 119, 121, 120, 122, 124, 123, 125, 127, 126, 128, 130, 129, 131, 133, 132]
    bars: list[OhlcvBar] = []
    for i, close in enumerate(closes):
        high = close + 2
        low = close - 2
        open_ = close - 0.5
        bars.append(
            OhlcvBar(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00+00:00",
                open=open_,
                high=high,
                low=low,
                close=float(close),
                volume=1000 + i * 10,
            )
        )
    return bars


def test_bootstrap_has_at_least_ten_features() -> None:
    catalog = bootstrap_catalog()
    assert len(catalog.list_defs()) >= 10
    assert catalog.get_set("fset_core_v1").composition_hash


def test_parity_each_feature_matches_compute_spec() -> None:
    from bolsa_analytics.features.indicator_ids import resolve_chart_definition_id

    bars = _bars()
    catalog = bootstrap_catalog()
    for feature_def in catalog.list_defs():
        via_bridge = compute_feature_value(bars, feature_def)
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
        preferred = str(line_key) if line_key else "main"
        line = next((ln for ln in result.lines if ln.key == preferred), None)
        if line is None and result.lines:
            line = result.lines[0]
        expected = float(line.points[-1].value) if line and line.points else None
        assert via_bridge == expected, feature_def.feature_key


def test_materialize_snapshot_via_port() -> None:
    bars = _bars()
    adapter = OnlineFeatureAdapter()
    snap = materialize_feature_snapshot(
        adapter,
        instrument_id="inst_demo",
        bars=bars,
    )
    assert snap is not None
    assert snap.feature_set_id == "fset_core_v1"
    assert len(snap.values) >= 10
    latest = adapter.get_latest("inst_demo", "fset_core_v1")
    assert latest is not None
    assert latest.values["rsi_14_close"] is not None
    as_of = adapter.get_as_of(
        "inst_demo",
        "fset_core_v1",
        datetime(2024, 1, 30, tzinfo=timezone.utc),
    )
    assert as_of is not None


def test_compute_feature_set_values_stable_keys() -> None:
    values = compute_feature_set_values(_bars())
    assert "sma_20_close" in values
    assert "macd_12_26" in values
    assert "volume" in values
