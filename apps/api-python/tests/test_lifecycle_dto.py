"""V1.87 — LifecycleEventRequestDto extra=forbid (offline, no PG)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bolsa_api.api.v1.routes.lifecycle import LifecycleEventRequestDto


def test_dto_unknown_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        LifecycleEventRequestDto.model_validate(
            {"kind": "T1_EXECUTED", "quanity": 5}
        )


def test_dto_known_fields_ok() -> None:
    dto = LifecycleEventRequestDto.model_validate(
        {"kind": "POSITION_OPENED", "accountId": "acc-1", "positionId": "pos-1"}
    )
    assert dto.kind == "POSITION_OPENED"
    assert dto.account_id == "acc-1"
    assert dto.position_id == "pos-1"
