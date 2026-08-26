"""DEX-3 Mesa UI — DTOs OperationalIncident mapean al wire sin error."""

from __future__ import annotations

from typing import Any

from bolsa_api.schemas.accounts import (
    OperationalIncidentDto,
    OperationalIncidentResponseDto,
    OperationalIncidentsListDto,
    OperationalIncidentsListResponseDto,
    ResolveOperationalIncidentBodyDto,
)


def _incident_dict() -> dict[str, Any]:
    return {
        "incidentId": "inc-1",
        "accountId": "acc-1",
        "kind": "portfolio_drift",
        "status": "open",
        "snapshot": "portfolio_drift",
        "openedAt": "2026-08-26T10:00:00+00:00",
        "reviewedAt": None,
        "reviewedBy": None,
        "resolvedAt": None,
        "resolvedBy": None,
        "resolutionNote": None,
        "clearedAt": None,
    }


def test_operational_incident_dto_maps_without_error() -> None:
    dto = OperationalIncidentDto.model_validate(_incident_dict())
    assert dto.incident_id == "inc-1"
    assert dto.kind == "portfolio_drift"
    assert dto.status == "open"

    dumped = dto.model_dump(by_alias=True)
    assert dumped["incidentId"] == "inc-1"
    assert dumped["openedAt"] == "2026-08-26T10:00:00+00:00"


def test_operational_incidents_list_response_dto_wraps_data() -> None:
    resp = OperationalIncidentsListResponseDto(
        data=OperationalIncidentsListDto(
            account_id="acc-1",
            incidents=[OperationalIncidentDto.model_validate(_incident_dict())],
            total=1,
        )
    )
    assert resp.data.total == 1
    assert resp.data.incidents[0].kind == "portfolio_drift"
    dumped = resp.model_dump(by_alias=True)
    assert dumped["data"]["accountId"] == "acc-1"
    assert dumped["data"]["incidents"][0]["status"] == "open"


def test_operational_incident_response_dto_wraps_single() -> None:
    resp = OperationalIncidentResponseDto(
        data=OperationalIncidentDto.model_validate(
            {**_incident_dict(), "status": "resolved", "resolutionNote": "ok"}
        )
    )
    assert resp.data.status == "resolved"
    assert resp.data.resolution_note == "ok"


def test_resolve_operational_incident_body_requires_note() -> None:
    body = ResolveOperationalIncidentBodyDto.model_validate(
        {"resolutionNote": "manual top-up", "resolvedBy": "op"}
    )
    assert body.resolution_note == "manual top-up"
    dumped = body.model_dump(by_alias=True)
    assert dumped["resolutionNote"] == "manual top-up"
