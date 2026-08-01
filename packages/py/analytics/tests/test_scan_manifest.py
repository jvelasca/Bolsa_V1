from bolsa_analytics.research.scan_manifest import (
    build_instrument_snapshot_meta,
    build_scan_aggregate_data_version,
    build_scan_manifest,
    merge_instrument_snapshot_metas,
)


def test_build_instrument_snapshot_meta() -> None:
    meta = build_instrument_snapshot_meta(
        instrument_id="inst-1",
        timeframe="1d",
        timestamps=["2026-01-01", "2026-01-02"],
        closes=[100.0, 101.5],
    )
    assert meta["instrumentId"] == "inst-1"
    assert meta["barCount"] == 2
    assert meta["dataVersion"].startswith("sha256:")


def test_build_scan_aggregate_data_version() -> None:
    metas = [
        {"instrumentId": "b", "dataVersion": "sha256:aaa"},
        {"instrumentId": "a", "dataVersion": "sha256:bbb"},
    ]
    version = build_scan_aggregate_data_version(metas)
    assert version.startswith("sha256:")
    assert version != "sha256:empty"


def test_merge_instrument_snapshot_metas_dedupes() -> None:
    merged = merge_instrument_snapshot_metas(
        [
            {"instrumentSnapshots": [{"id": "snap-1", "instrumentId": "a"}]},
            {"instrumentSnapshots": [{"id": "snap-1", "instrumentId": "a"}, {"id": "snap-2", "instrumentId": "b"}]},
        ]
    )
    assert len(merged) == 2


def test_build_scan_manifest_shape() -> None:
    snapshots = [
        build_instrument_snapshot_meta(
            instrument_id="inst-1",
            timeframe="1d",
            timestamps=["2026-01-01", "2026-01-02"],
            closes=[10.0, 11.0],
        )
    ]
    manifest = build_scan_manifest(
        scan_id="scan-1",
        strategy_definition_id="strat-1",
        strategy_version=1,
        timeframe="1d",
        universe={"listId": "list-1"},
        scanned_count=10,
        hit_count=2,
        instrument_snapshots=snapshots,
        tracker_definition_id="tracker-1",
        cache_stats={"hits": 3, "misses": 1},
        scan_mode="hybrid",
        scorer_version="1.0.0",
        scorer_id="technical_rating_v1",
        gate_rule_hash="sha256:abc123",
    )
    assert manifest["manifestVersion"] == "1.0"
    assert manifest["scanId"] == "scan-1"
    assert manifest["dataSnapshots"] == snapshots
    assert manifest["cacheStats"] == {"hits": 3, "misses": 1}
    assert manifest["scanMode"] == "hybrid"
    assert manifest["scorerId"] == "technical_rating_v1"
