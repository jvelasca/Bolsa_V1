"""P2 — particionado y fusión de resultados de scan (ADR-010)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.research.scan_manifest import merge_instrument_snapshot_metas
from bolsa_domain.platform_kernel import MAX_SCAN_INSTRUMENTS_CHUNK

JOB_KIND_SINGLE = "single"
JOB_KIND_PARENT = "parent"
JOB_KIND_CHUNK = "chunk"


def should_chunk_universe(instrument_count: int) -> bool:
    return instrument_count > MAX_SCAN_INSTRUMENTS_CHUNK


def split_instrument_chunks(instrument_ids: list[str], chunk_size: int = MAX_SCAN_INSTRUMENTS_CHUNK) -> list[list[str]]:
    if chunk_size < 1:
        raise ValueError("chunk_size debe ser >= 1")
    return [instrument_ids[index : index + chunk_size] for index in range(0, len(instrument_ids), chunk_size)]


def chunk_scan_payload(
    base_payload: dict[str, Any],
    *,
    parent_job_id: str,
    chunk_index: int,
    chunk_total: int,
    instrument_ids: list[str],
) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in base_payload.items()
        if key not in ("jobKind", "parentJobId", "chunkIndex", "chunkTotal", "childJobIds", "scanRequest")
    }
    payload["jobKind"] = JOB_KIND_CHUNK
    payload["parentJobId"] = parent_job_id
    payload["chunkIndex"] = chunk_index
    payload["chunkTotal"] = chunk_total
    payload["universe"] = {"instrumentIds": instrument_ids}
    return payload


def parent_scan_payload(
    base_payload: dict[str, Any],
    *,
    child_job_ids: list[str],
    total_instruments: int,
) -> dict[str, Any]:
    return {
        "jobKind": JOB_KIND_PARENT,
        "scanRequest": dict(base_payload),
        "childJobIds": child_job_ids,
        "totalInstruments": total_instruments,
        "chunkSize": MAX_SCAN_INSTRUMENTS_CHUNK,
    }


def merge_scan_result_dicts(
    results: list[dict[str, Any]],
    *,
    parent_scan_id: str,
    max_results: int,
    list_id: str | None,
    strategy_definition_id: str | None,
    timeframe: str,
) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    scanned_count = 0
    seen_instruments: set[str] = set()

    for result in results:
        scanned_count += int(result.get("scannedCount") or 0)
        for item in result.get("skipped") or []:
            skipped.append(item)
        if len(hits) >= max_results:
            continue
        for hit in result.get("hits") or []:
            instrument_id = str(hit.get("instrumentId") or "")
            if instrument_id and instrument_id in seen_instruments:
                continue
            if instrument_id:
                seen_instruments.add(instrument_id)
            hits.append(hit)
            if len(hits) >= max_results:
                break

    return {
        "scanId": parent_scan_id,
        "scannedCount": scanned_count,
        "hitCount": len(hits),
        "hits": hits,
        "skipped": skipped,
        "strategyDefinitionId": strategy_definition_id,
        "listId": list_id,
        "timeframe": timeframe,
        "instrumentSnapshots": merge_instrument_snapshot_metas(results),
    }
