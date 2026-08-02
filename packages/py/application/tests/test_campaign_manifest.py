"""Unit tests for campaign manifest + dataset metadata (Q0.2 / Q1.1 / Q1.5)."""

from bolsa_application.campaign_manifest import (
    CAMPAIGN_MANIFEST_SCHEMA,
    build_campaign_manifest,
    validate_campaign_manifest,
)
from bolsa_application.dataset_metadata import dataset_metadata_from_bars, merge_dataset_into_blocks


def test_build_campaign_manifest_v0() -> None:
    m = build_campaign_manifest(
        campaign_id="ibex35-test",
        universe="ibex35",
        bar_count=500,
        presets=["sma_crossover"],
        cpu_cost_units=12.5,
        git_commit="abc123",
    )
    assert m.schema_version == CAMPAIGN_MANIFEST_SCHEMA
    ref = m.to_manifest_ref()
    assert ref["campaign"] == "ibex35-test"
    assert ref["barCount"] == 500
    assert ref["cpuCostUnits"] == 12.5
    assert ref["gitCommit"] == "abc123"


def test_validate_campaign_manifest_requires_fields() -> None:
    errs = validate_campaign_manifest({"schema_version": CAMPAIGN_MANIFEST_SCHEMA})
    assert "campaign_id missing" in errs
    assert "universe missing" in errs


def test_dataset_metadata_from_bars() -> None:
    bars = [{"timestamp": "2020-01-02"}, {"timestamp": "2020-01-03"}, {"timestamp": "2020-01-04"}]
    meta = dataset_metadata_from_bars(bars)
    assert meta["bars"] == 3
    assert meta["datasetStart"] == "2020-01-02"
    assert meta["datasetEnd"] == "2020-01-04"
    blocks = merge_dataset_into_blocks(None, meta)
    assert blocks["dataset"]["schemaVersion"] == "dataset_meta_v0"
