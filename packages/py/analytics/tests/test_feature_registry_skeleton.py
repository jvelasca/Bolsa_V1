"""RFC-005 F2 skeleton — catalog, composition hash, OnlineFeatureAdapter PIT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bolsa_analytics.features import (
    OnlineFeatureAdapter,
    bootstrap_catalog,
    composition_hash,
)
from bolsa_analytics.features.models import composition_hash_from_defs
from bolsa_analytics.signals.feature_cache import hash_indicator_specs


def test_bootstrap_catalog_has_core_defs() -> None:
    catalog = bootstrap_catalog()
    defs = catalog.list_defs()
    assert len(defs) >= 10
    rsi = catalog.get_by_key("rsi_14_close")
    assert rsi.indicator_id == "IND-RSI"
    assert rsi.parity_ref == "IND-RSI"
    assert len(catalog.list_by_indicator_id("IND-RSI")) >= 1
    assert len(catalog.list_by_indicator_id("IND-SMA")) >= 2
    feature_set = catalog.get_set("fset_core_v1")
    assert feature_set.composition_hash
    assert len(feature_set.members) == len(defs)


def test_composition_hash_stable() -> None:
    members = [("feat_a", "1.0.0"), ("feat_b", "1.0.0")]
    assert composition_hash(members) == composition_hash(list(reversed(members)))
    catalog = bootstrap_catalog()
    defs = list(catalog.list_defs())
    assert composition_hash_from_defs(defs) == catalog.get_set("fset_core_v1").composition_hash


def test_specs_hash_aligns_with_p8() -> None:
    adapter = OnlineFeatureAdapter()
    specs = adapter.catalog.indicator_specs_for_set("fset_core_v1")
    assert adapter.specs_hash_for_set("fset_core_v1") == hash_indicator_specs(specs)


def test_online_adapter_latest_and_pit() -> None:
    adapter = OnlineFeatureAdapter()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = t0 + timedelta(days=1)
    adapter.materialize_latest_from_values(
        instrument_id="inst_1",
        feature_set_id="fset_core_v1",
        values={"rsi_14_close": 40.0},
        timestamp=t0,
    )
    adapter.materialize_latest_from_values(
        instrument_id="inst_1",
        feature_set_id="fset_core_v1",
        values={"rsi_14_close": 55.0},
        timestamp=t1,
    )
    latest = adapter.get_latest("inst_1", "fset_core_v1")
    assert latest is not None
    assert latest.values["rsi_14_close"] == 55.0

    as_of = adapter.get_as_of("inst_1", "fset_core_v1", t0)
    assert as_of is not None
    assert as_of.values["rsi_14_close"] == 40.0

    # PIT: no ve futuro
    future_only = adapter.get_as_of(
        "inst_1",
        "fset_core_v1",
        t0 - timedelta(seconds=1),
    )
    assert future_only is None
