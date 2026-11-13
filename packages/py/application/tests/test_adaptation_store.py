"""Persistencia de propuestas (ADR-049): un fichero por propuesta, ids saneados."""

from __future__ import annotations

from pathlib import Path

from bolsa_application.adaptation_store import (
    adaptation_path_in,
    iter_adaptation_records,
    load_adaptation_record,
    merge_adaptation_record,
    save_adaptation_record,
)


def test_roundtrip_save_load_merge(tmp_path: Path) -> None:
    record = {"id": "adp_abc", "status": "proposed", "createdAt": "2026-11-13T08:00:00Z"}
    path = save_adaptation_record(tmp_path, record)

    assert path.is_file()
    assert load_adaptation_record(tmp_path, "adp_abc") == record

    merged = merge_adaptation_record(tmp_path, "adp_abc", {"status": "rejected"})
    assert merged is not None
    assert merged["status"] == "rejected"
    assert merged["createdAt"] == record["createdAt"]


def test_hostile_id_cannot_escape_directory(tmp_path: Path) -> None:
    path = adaptation_path_in(tmp_path, "../otra/cuenta")

    assert path.parent == tmp_path


def test_missing_record_returns_none(tmp_path: Path) -> None:
    assert load_adaptation_record(tmp_path, "adp_missing") is None
    assert merge_adaptation_record(tmp_path, "adp_missing", {"x": 1}) is None


def test_corrupt_file_is_ignored_when_listing(tmp_path: Path) -> None:
    save_adaptation_record(tmp_path, {"id": "adp_1", "status": "proposed", "createdAt": "1"})
    save_adaptation_record(tmp_path, {"id": "adp_2", "status": "proposed", "createdAt": "2"})
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    records = list(iter_adaptation_records(tmp_path))

    assert [record["id"] for record in records] == ["adp_2", "adp_1"]


def test_listing_missing_directory_is_empty(tmp_path: Path) -> None:
    assert list(iter_adaptation_records(tmp_path / "nope")) == []
