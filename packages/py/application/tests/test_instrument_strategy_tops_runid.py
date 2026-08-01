"""lab_validated / active TOP must carry runId on every slot."""

from __future__ import annotations

import pytest

from bolsa_application.instrument_strategy_tops import (
    assert_lab_validated_slots_have_run_id,
)


def test_semifinal_in_sample_allows_missing_run_id() -> None:
    assert_lab_validated_slots_have_run_id(
        evidence_level="in_sample_only",
        status="semifinal",
        slots=[{"rank": 1, "label": "SMA", "runId": None}],
    )


def test_lab_validated_rejects_missing_run_id() -> None:
    with pytest.raises(ValueError, match="runId"):
        assert_lab_validated_slots_have_run_id(
            evidence_level="lab_validated",
            status="active",
            slots=[
                {"rank": 1, "label": "SMA", "runId": "run-1"},
                {"rank": 2, "label": "RSI", "runId": None},
            ],
        )


def test_active_rejects_empty_run_id() -> None:
    with pytest.raises(ValueError, match="runId"):
        assert_lab_validated_slots_have_run_id(
            evidence_level="in_sample_only",
            status="active",
            slots=[{"rank": 1, "label": "SMA", "runId": "  "}],
        )


def test_lab_validated_accepts_all_run_ids() -> None:
    assert_lab_validated_slots_have_run_id(
        evidence_level="lab_validated",
        status="active",
        slots=[
            {"rank": 1, "runId": "r1"},
            {"rank": 2, "run_id": "r2"},
        ],
    )
