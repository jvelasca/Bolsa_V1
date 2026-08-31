"""F2b — DTOs SubmitIntent list (read-only) mapean al wire sin mutación."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_analytics.cognitive.submit_intent import (
    mark_send_attempted,
    mark_submit_filled,
    record_submit_intent,
)
from bolsa_api.api.v1.routes.accounts import (
    _to_submit_intent_dto,
    list_in_flight_submit_intents,
)
from bolsa_api.schemas.accounts import (
    SubmitIntentListItemDto,
    SubmitIntentsListDto,
    SubmitIntentsListResponseDto,
)
from bolsa_application.submit_intent_store import InMemorySubmitIntentStore


def _intent_dict() -> dict[str, Any]:
    return {
        "decisionId": "DEC-1",
        "intentId": "INT-1",
        "orderId": "ORD-1",
        "accountId": "acc-1",
        "phase": "send_attempted",
        "venueOrderId": None,
        "reason": "crash_before_venue_ack",
        "venue": "paper",
        "sendAttemptedAt": "2026-08-31T12:00:00+00:00",
        "instrumentId": "inst-nvda",
    }


def test_submit_intent_list_item_dto_maps_without_error() -> None:
    dto = SubmitIntentListItemDto.model_validate(_intent_dict())
    assert dto.decision_id == "DEC-1"
    assert dto.phase == "send_attempted"
    assert dto.instrument_id == "inst-nvda"

    dumped = dto.model_dump(by_alias=True)
    assert dumped["decisionId"] == "DEC-1"
    assert dumped["instrumentId"] == "inst-nvda"
    assert dumped["sendAttemptedAt"] == "2026-08-31T12:00:00+00:00"


def test_submit_intent_list_item_dto_instrument_null_fail_closed() -> None:
    dto = SubmitIntentListItemDto.model_validate(
        {**_intent_dict(), "instrumentId": None}
    )
    assert dto.instrument_id is None
    dumped = dto.model_dump(by_alias=True)
    assert dumped["instrumentId"] is None


def test_submit_intents_list_response_dto_wraps_data() -> None:
    resp = SubmitIntentsListResponseDto(
        data=SubmitIntentsListDto(
            account_id="acc-1",
            intents=[SubmitIntentListItemDto.model_validate(_intent_dict())],
            total=1,
        )
    )
    assert resp.data.total == 1
    assert resp.data.intents[0].phase == "send_attempted"
    dumped = resp.model_dump(by_alias=True)
    assert dumped["data"]["accountId"] == "acc-1"
    assert dumped["data"]["intents"][0]["phase"] == "send_attempted"


def test_to_submit_intent_dto_soft_join_instrument() -> None:
    intent = mark_send_attempted(
        record_submit_intent(
            decision_id="DEC-1",
            intent_id="INT-1",
            order_id="ORD-1",
            account_id="acc-1",
        )
    )
    dto = _to_submit_intent_dto(intent, instrument_id="inst-a")
    assert dto.instrument_id == "inst-a"
    dto_null = _to_submit_intent_dto(intent, instrument_id=None)
    assert dto_null.instrument_id is None


@pytest.mark.asyncio
async def test_list_in_flight_route_empty_and_filters_filled() -> None:
    """Read-only: empty list; excludes filled; no put/delete on store."""
    store = InMemorySubmitIntentStore()
    await store.put(
        mark_send_attempted(
            record_submit_intent(
                decision_id="DEC-SEND",
                intent_id="INT-SEND",
                order_id="ORD-SEND",
                account_id="acc-1",
            )
        )
    )
    await store.put(
        mark_submit_filled(
            mark_send_attempted(
                record_submit_intent(
                    decision_id="DEC-FILL",
                    intent_id="INT-FILL",
                    order_id="ORD-FILL",
                    account_id="acc-1",
                )
            )
        )
    )

    session = AsyncMock()
    # soft-join: no decision_sessions rows → instrumentId null
    soft = MagicMock()
    soft.all.return_value = []
    session.execute = AsyncMock(return_value=soft)

    # Patch DI helpers used by the route
    import bolsa_api.api.v1.routes.accounts as accounts_routes

    original_store = accounts_routes.get_submit_intent_store
    accounts_routes.get_submit_intent_store = lambda _session: store  # type: ignore[assignment]
    try:
        empty = await list_in_flight_submit_intents("acc-empty", session)
        assert empty.data.total == 0
        assert empty.data.intents == []

        resp = await list_in_flight_submit_intents("acc-1", session)
        assert resp.data.total == 1
        assert resp.data.intents[0].decision_id == "DEC-SEND"
        assert resp.data.intents[0].phase == "send_attempted"
        assert resp.data.intents[0].instrument_id is None
        # filled excluded
        assert all(i.decision_id != "DEC-FILL" for i in resp.data.intents)
    finally:
        accounts_routes.get_submit_intent_store = original_store  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_list_in_flight_route_soft_joins_instrument() -> None:
    store = InMemorySubmitIntentStore()
    await store.put(
        mark_send_attempted(
            record_submit_intent(
                decision_id="DEC-JOIN",
                intent_id="INT-JOIN",
                order_id="ORD-JOIN",
                account_id="acc-1",
            )
        )
    )
    session = AsyncMock()
    soft = MagicMock()
    soft.all.return_value = [("DEC-JOIN", "inst-nvda")]
    session.execute = AsyncMock(return_value=soft)

    import bolsa_api.api.v1.routes.accounts as accounts_routes

    original_store = accounts_routes.get_submit_intent_store
    accounts_routes.get_submit_intent_store = lambda _session: store  # type: ignore[assignment]
    try:
        resp = await list_in_flight_submit_intents("acc-1", session)
        assert resp.data.intents[0].instrument_id == "inst-nvda"
    finally:
        accounts_routes.get_submit_intent_store = original_store  # type: ignore[assignment]
