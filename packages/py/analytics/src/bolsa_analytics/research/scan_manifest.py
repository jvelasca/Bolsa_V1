"""Scan manifest builder — reproducibilidad radar (ADR-010 P4)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence

from bolsa_analytics.research.data_snapshot import build_data_snapshot_id, compute_data_version
from bolsa_analytics.research.manifest import BarFingerprint

SCAN_MANIFEST_VERSION = "1.0"
SCAN_ENGINE_NAME = "bolsa_signal_scan"
SCAN_ENGINE_VERSION = "0.1.0"


def fingerprint_bars(timestamps: Sequence[str], closes: Sequence[float]) -> list[BarFingerprint]:
    return [BarFingerprint(timestamp=ts, close=close) for ts, close in zip(timestamps, closes, strict=True)]


def build_instrument_snapshot_meta(
    *,
    instrument_id: str,
    timeframe: str,
    timestamps: Sequence[str],
    closes: Sequence[float],
) -> dict[str, Any]:
    fingerprints = fingerprint_bars(timestamps, closes)
    data_version = compute_data_version(fingerprints)
    snapshot_id = build_data_snapshot_id(instrument_id, timeframe, data_version)
    return {
        "id": snapshot_id,
        "instrumentId": instrument_id,
        "timeframe": timeframe,
        "dataVersion": data_version,
        "barCount": len(fingerprints),
        "from": fingerprints[0].timestamp,
        "to": fingerprints[-1].timestamp,
        "source": "postgres",
    }


def build_scan_aggregate_data_version(snapshot_metas: Sequence[dict[str, Any]]) -> str:
    if not snapshot_metas:
        return "sha256:empty"
    parts = sorted(
        f"{meta['instrumentId']}:{meta['dataVersion']}" for meta in snapshot_metas if meta.get("instrumentId")
    )
    digest = hashlib.sha256("|".join(parts).encode())
    return f"sha256:{digest.hexdigest()[:16]}"


def merge_instrument_snapshot_metas(results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for result in results:
        for meta in result.get("instrumentSnapshots") or []:
            snapshot_id = str(meta.get("id") or "")
            if snapshot_id:
                by_id[snapshot_id] = meta
    return list(by_id.values())


def hash_gate_config(definition: dict[str, Any]) -> str | None:
    hybrid = definition.get("hybrid")
    if not isinstance(hybrid, dict):
        return None
    payload = {
        "ruleGate": hybrid.get("ruleGate"),
        "fundamentalGate": hybrid.get("fundamentalGate"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode())
    return f"sha256:{digest.hexdigest()[:16]}"


def hash_fundamentals_batch(fundamentals_by_instrument: dict[str, dict[str, Any] | None]) -> str | None:
    if not fundamentals_by_instrument:
        return None
    parts = sorted(
        f"{instrument_id}:{meta.get('fetchedAt') if meta else 'missing'}"
        for instrument_id, meta in fundamentals_by_instrument.items()
    )
    digest = hashlib.sha256("|".join(parts).encode())
    return f"sha256:{digest.hexdigest()[:16]}"


def build_scan_manifest(
    *,
    scan_id: str,
    strategy_definition_id: str,
    strategy_version: int,
    timeframe: str,
    universe: dict[str, Any],
    scanned_count: int,
    hit_count: int,
    instrument_snapshots: Sequence[dict[str, Any]],
    tracker_definition_id: str | None = None,
    cache_stats: dict[str, int] | None = None,
    scan_mode: str | None = None,
    scorer_version: str | None = None,
    scorer_id: str | None = None,
    gate_rule_hash: str | None = None,
    fundamentals_version: str | None = None,
) -> dict[str, Any]:
    data_version = build_scan_aggregate_data_version(instrument_snapshots)
    manifest: dict[str, Any] = {
        "manifestVersion": SCAN_MANIFEST_VERSION,
        "scanId": scan_id,
        "strategyDefinitionId": strategy_definition_id,
        "strategyVersion": strategy_version,
        "dataVersion": data_version,
        "timeframe": timeframe,
        "universe": universe,
        "scannedCount": scanned_count,
        "hitCount": hit_count,
        "engine": {"name": SCAN_ENGINE_NAME, "version": SCAN_ENGINE_VERSION},
        "dataSnapshots": list(instrument_snapshots),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if tracker_definition_id:
        manifest["trackerDefinitionId"] = tracker_definition_id
    if cache_stats is not None:
        manifest["cacheStats"] = cache_stats
    if scan_mode:
        manifest["scanMode"] = scan_mode
    if scorer_version:
        manifest["scorerVersion"] = scorer_version
    if scorer_id:
        manifest["scorerId"] = scorer_id
    if gate_rule_hash:
        manifest["gateRuleHash"] = gate_rule_hash
    if fundamentals_version:
        manifest["fundamentalsVersion"] = fundamentals_version
    return manifest
