"""F0.6a — DTO del Decision Board: el bundle to_dict() mapea al wire sin error."""

from __future__ import annotations

from typing import Any

from bolsa_api.schemas.accounts import (
    DecisionBoardBucketCountsDto,
    DecisionBoardDto,
    DecisionBoardResponseDto,
)


def _bundle_dict() -> dict[str, Any]:
    return {
        "accountId": "acc-1",
        "generatedAt": "2026-08-24T09:00:00Z",
        "buckets": {
            "pendingConfirm": 1,
            "vetoed": 1,
            "deferred": 1,
            "autoWaiting": 2,
            "total": 5,
        },
        "semiF3Queue": [
            {"instrumentId": "i1", "symbol": "AAA", "status": "pending_confirm"}
        ],
        "decisionSessions": [
            {
                "sessionId": "s1",
                "kind": "propose",
                "status": "open",
                "instrumentId": "inst-1",
                "symbol": "AAA",
                "decisionId": "DEC-1",
                "createdAt": "2026-08-24T09:00:00Z",
                "gate": "VETO",
                "tradePlan": {
                    "status": "BLOCKED",
                    "whyNot": ["regime"],
                    "executionAllowed": False,
                },
                "wyckoffSpringAnchor": {"phase": "reclaim", "effort": "none"},
            }
        ],
        "equity": 1000.0,
        "freeMargin": 500.0,
    }


def test_decision_board_dto_maps_without_error() -> None:
    dto = DecisionBoardDto.model_validate(_bundle_dict())
    assert dto.account_id == "acc-1"
    assert dto.buckets.vetoed == 1
    assert dto.semi_f3_queue[0].instrument_id == "i1"
    assert dto.decision_sessions[0].gate == "VETO"
    assert dto.decision_sessions[0].trade_plan is not None
    assert dto.decision_sessions[0].trade_plan["status"] == "BLOCKED"
    assert dto.decision_sessions[0].wyckoff_spring_anchor is not None
    assert dto.decision_sessions[0].wyckoff_spring_anchor["phase"] == "reclaim"
    assert dto.equity == 1000.0

    dumped = dto.model_dump(by_alias=True)
    assert dumped["accountId"] == "acc-1"
    assert dumped["buckets"]["pendingConfirm"] == 1
    assert dumped["semiF3Queue"][0]["status"] == "pending_confirm"
    assert dumped["decisionSessions"][0]["createdAt"] == "2026-08-24T09:00:00Z"
    assert dumped["decisionSessions"][0]["tradePlan"]["whyNot"] == ["regime"]
    assert dumped["decisionSessions"][0]["wyckoffSpringAnchor"]["effort"] == "none"
    assert dumped["freeMargin"] == 500.0


def test_decision_board_session_dto_omits_absent_plan() -> None:
    raw = {
        "sessionId": "s2",
        "kind": "propose",
        "status": "open",
        "instrumentId": "inst-2",
        "createdAt": "2026-08-24T09:00:00Z",
        "gate": "PASS",
    }
    from bolsa_api.schemas.accounts import DecisionSessionViewDto

    dto = DecisionSessionViewDto.model_validate(raw)
    dumped = dto.model_dump(by_alias=True, exclude_none=True)
    assert "tradePlan" not in dumped
    assert "wyckoffSpringAnchor" not in dumped


def test_decision_board_response_dto_wraps_data() -> None:
    resp = DecisionBoardResponseDto(data=_bundle_dict())
    assert resp.data.account_id == "acc-1"
    assert resp.data.buckets.total == 5
    dumped = resp.model_dump(by_alias=True)
    assert dumped["data"]["accountId"] == "acc-1"


def test_decision_board_bucket_counts_defaults_zero() -> None:
    counts = DecisionBoardBucketCountsDto.model_validate(
        {"pendingConfirm": 0, "vetoed": 0, "deferred": 0, "autoWaiting": 0, "total": 0}
    )
    assert counts.total == 0
