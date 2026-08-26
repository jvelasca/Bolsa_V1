"""ADR-029 F2 — DTO del Decision Journal: el bundle to_dict() mapea al wire sin error."""

from __future__ import annotations

from typing import Any

from bolsa_api.schemas.accounts import (
    DecisionJournalEntryDto,
    DecisionJournalListDto,
    DecisionJournalListResponseDto,
)


def _list_dict() -> dict[str, Any]:
    return {
        "accountId": "acc-1",
        "entries": [
            {
                "artifactType": "ART-DECISION-JOURNAL-ENTRY",
                "schemaVersion": "1.0.0",
                "entryId": "JNL-1",
                "decisionId": "dec-1",
                "sessionId": "sess-1",
                "accountId": "acc-1",
                "instrumentId": "inst-1",
                "eventType": "proposal_recorded",
                "actor": "system",
                "payload": {"status": "open"},
                "createdAt": "2026-08-24T10:00:00Z",
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }


def test_decision_journal_entry_dto_maps_without_error() -> None:
    entry = _list_dict()["entries"][0]
    dto = DecisionJournalEntryDto.model_validate(entry)
    assert dto.entry_id == "JNL-1"
    assert dto.event_type == "proposal_recorded"
    assert dto.artifact_type == "ART-DECISION-JOURNAL-ENTRY"
    assert dto.schema_version == "1.0.0"

    dumped = dto.model_dump(by_alias=True)
    assert dumped["entryId"] == "JNL-1"
    assert dumped["eventType"] == "proposal_recorded"
    assert dumped["createdAt"] == "2026-08-24T10:00:00Z"


def test_decision_journal_list_dto_maps_without_error() -> None:
    dto = DecisionJournalListDto.model_validate(_list_dict())
    assert dto.account_id == "acc-1"
    assert dto.total == 1
    assert dto.entries[0].entry_id == "JNL-1"

    dumped = dto.model_dump(by_alias=True)
    assert dumped["accountId"] == "acc-1"
    assert dumped["entries"][0]["artifactType"] == "ART-DECISION-JOURNAL-ENTRY"


def test_decision_journal_list_response_dto_wraps_data() -> None:
    resp = DecisionJournalListResponseDto(data=_list_dict())
    assert resp.data.account_id == "acc-1"
    assert resp.data.entries[0].event_type == "proposal_recorded"
    dumped = resp.model_dump(by_alias=True)
    assert dumped["data"]["total"] == 1
    assert dumped["data"]["entries"][0]["entryId"] == "JNL-1"


def test_decision_study_list_dto_maps_without_error() -> None:
    from bolsa_api.schemas.accounts import (
        DecisionJournalStudyListDto,
        DecisionJournalStudyListResponseDto,
    )

    payload = {
        "accountId": "acc-1",
        "studies": [
            {
                "artifactType": "ART-DECISION-JOURNAL-STUDY",
                "schemaVersion": "1.0.0",
                "sessionId": "s1",
                "decisionId": "d1",
                "instrumentId": "inst-1",
                "symbol": "AAPL",
                "name": "Apple",
                "studiedAt": "2026-08-26T09:32:00Z",
                "ageMs": 1000,
                "period": "daily",
                "timeframe": "1d",
                "opinion": "neutral",
                "status": "neutral",
                "strength": 6.1,
                "strengthBand": "strong",
                "hasOperationalPlan": False,
                "userThesis": None,
                "analysisNotes": [],
                "trends": [],
                "consensus": {"bullish": 0, "bearish": 0, "neutral": 1, "total": 1},
                "indicators": {"primary": None, "confirmation": None},
                "invalidation": [],
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }
    dto = DecisionJournalStudyListDto.model_validate(payload)
    assert dto.studies[0].session_id == "s1"
    assert dto.studies[0].has_operational_plan is False
    resp = DecisionJournalStudyListResponseDto(data=payload)
    dumped = resp.model_dump(by_alias=True)
    assert dumped["data"]["studies"][0]["sessionId"] == "s1"
