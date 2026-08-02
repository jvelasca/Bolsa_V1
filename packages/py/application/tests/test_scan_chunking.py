from bolsa_application.scan_chunking import (
    merge_scan_result_dicts,
    should_chunk_universe,
    split_instrument_chunks,
)
from bolsa_domain.platform_kernel import MAX_SCAN_INSTRUMENTS_CHUNK


def test_should_chunk_universe() -> None:
    assert should_chunk_universe(MAX_SCAN_INSTRUMENTS_CHUNK) is False
    assert should_chunk_universe(MAX_SCAN_INSTRUMENTS_CHUNK + 1) is True


def test_split_instrument_chunks() -> None:
    ids = [f"id-{index}" for index in range(501)]
    chunks = split_instrument_chunks(ids)
    assert len(chunks) == 3
    assert len(chunks[0]) == MAX_SCAN_INSTRUMENTS_CHUNK
    assert len(chunks[1]) == MAX_SCAN_INSTRUMENTS_CHUNK
    assert len(chunks[2]) == 1


def test_merge_scan_result_dicts_respects_max_results() -> None:
    results = [
        {
            "scannedCount": 10,
            "hits": [
                {"instrumentId": "a", "symbol": "A"},
                {"instrumentId": "b", "symbol": "B"},
            ],
            "skipped": [],
        },
        {
            "scannedCount": 10,
            "hits": [{"instrumentId": "c", "symbol": "C"}],
            "skipped": [{"instrumentId": "x", "reason": "skip"}],
        },
    ]
    merged = merge_scan_result_dicts(
        results,
        parent_scan_id="parent-1",
        max_results=2,
        list_id="list-1",
        strategy_definition_id="strat-1",
        timeframe="1d",
    )
    assert merged["scanId"] == "parent-1"
    assert merged["scannedCount"] == 20
    assert merged["hitCount"] == 2
    assert len(merged["hits"]) == 2
    assert merged["hits"][0]["instrumentId"] == "a"
    assert merged["listId"] == "list-1"
    assert len(merged["skipped"]) == 1
