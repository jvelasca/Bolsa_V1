"""V2.12 — LiveOrderRecoveryWorker: UNKNOWN vía query_broker (NO re-POST).

Pruebas sin PG (`_drain_unknowns` + `resolve_one_unknown` aceptan cualquier store
con `get/put/list_unknown`) de la lógica fail-closed:
* query legal → fila pasa a FILLED/PARTIAL/rejected/cancelled/working persistidos;
* sin cliente (None) / `unavailable` / intraducible → la fila queda UNKNOWN;
* en ningún caso se sintetiza `execute_trade`/ledger aquí.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    build_live_order,
    transition_live_order,
)
from bolsa_api.background.live_order_recovery_worker import (  # type: ignore[import-untyped]
    _drain_unknowns,
    _no_query_provider,
    resolve_one_unknown,
)
from bolsa_application.live_order_query import (
    BrokerOrderQueryResult,
    MockLiveOrderQuery,
)
from bolsa_application.live_order_store import InMemoryLiveOrderStore


def _ui_unknown(*, order_id: str = "lo-x", venue_order_id: str = "xtb-x") -> LiveOrder:
    order = build_live_order(
        order_id=order_id,
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        account_id="acc-1",
    )
    submitted = transition_live_order(
        transition_live_order(order, "SUBMITTING"),
        "SUBMITTED",
        venue_order_id=venue_order_id,
    )
    return transition_live_order(submitted, "UNKNOWN")


@pytest.mark.asyncio
async def test_query_filled_resolves_unknown_no_execute_trade() -> None:
    order = _ui_unknown(order_id="lo-fill", venue_order_id="xtb-fill")
    store = InMemoryLiveOrderStore()
    await store.put(order)

    async def provider(venue: str, account_id: str, vid: str) -> MockLiveOrderQuery:
        assert venue == "LIVE"
        return MockLiveOrderQuery(
            BrokerOrderQueryResult(
                outcome="filled",
                venue_order_id=vid,
                filled_quantity=100.0,
                remaining_quantity=0.0,
            )
        )

    stats = await _drain_unknowns(store, query_provider=provider, limit=50)
    assert stats["drained"] == 1
    assert stats["resolved"] == 1
    assert stats["errors"] == 0

    resolved = await store.get("lo-fill")
    assert resolved is not None
    assert resolved.status == "FILLED"
    assert resolved.filled_quantity == 100.0
    assert resolved.remaining_quantity == 0.0
    # NO execute_trade synthesis: máquina resuelta, sin apply financiero inventado.
    assert resolved.financial_apply_count == 0


@pytest.mark.asyncio
async def test_query_partial_resolves_unknown_with_filled_qty() -> None:
    order = _ui_unknown(order_id="lo-partial", venue_order_id="xtb-p")
    store = InMemoryLiveOrderStore()
    await store.put(order)

    async def provider(venue: str, account_id: str, vid: str) -> MockLiveOrderQuery:
        return MockLiveOrderQuery(
            BrokerOrderQueryResult(
                outcome="partial",
                venue_order_id=vid,
                filled_quantity=40.0,
                remaining_quantity=60.0,
            )
        )

    stats = await _drain_unknowns(store, query_provider=provider, limit=50)
    assert stats["resolved"] == 1
    resolved = await store.get("lo-partial")
    assert resolved is not None
    assert resolved.status == "PARTIAL"
    assert resolved.filled_quantity == 40.0
    assert resolved.remaining_quantity == 60.0


@pytest.mark.asyncio
async def test_no_query_provider_leaves_unknown() -> None:
    """Sin cliente de query cableado → fila queda UNKNOWN (fail-closed)."""
    order = _ui_unknown(order_id="lo-none", venue_order_id="xtb-none")
    store = InMemoryLiveOrderStore()
    await store.put(order)

    status = await resolve_one_unknown(
        order,
        await _no_query_provider(order.venue, order.account_id, order.venue_order_id),
        store=store,
        account_id=order.account_id or "acc-1",
    )
    assert status == "unavailable"
    still = await store.get("lo-none")
    assert still is not None
    assert still.status == "UNKNOWN"


@pytest.mark.asyncio
async def test_unavailable_outcome_leaves_unknown() -> None:
    order = _ui_unknown(order_id="lo-unavail", venue_order_id="xtb-u")
    store = InMemoryLiveOrderStore()
    await store.put(order)

    async def provider(venue: str, account_id: str, vid: str) -> MockLiveOrderQuery:
        return MockLiveOrderQuery(
            BrokerOrderQueryResult(
                outcome="unavailable",
                venue_order_id=vid,
                filled_quantity=0.0,
                remaining_quantity=100.0,
            )
        )

    stats = await _drain_unknowns(store, query_provider=provider, limit=50)
    assert stats["resolved"] == 0
    assert stats["unavailable"] == 1
    still = await store.get("lo-unavail")
    assert still is not None
    assert still.status == "UNKNOWN"


@pytest.mark.asyncio
async def test_submitting_repost_target_never_reposts_from_unknown() -> None:
    """UNKNOWN nunca transita a SUBMITTING (no re-POST): se queda UNKNOWN."""
    order = _ui_unknown(order_id="lo-rm", venue_order_id="xtb-rm")
    store = InMemoryLiveOrderStore()
    await store.put(order)

    # El dominio prohíbe SUBMITTING←UNKNOWN; el drainer respeta el grafo.
    resolved = await resolve_one_unknown(
        order,
        None,
        store=store,
        account_id="acc-1",
    )
    assert resolved == "unavailable"
    still = await store.get("lo-rm")
    assert still is not None
    assert still.status == "UNKNOWN"


@pytest.mark.asyncio
async def test_query_cancelled_resolves_unknown_no_op_on_next_drain() -> None:
    """Test-double hardening: UNKNOWN → CANCELLED se persiste; un segundo drain es
    no-op (orden terminada no resucita ni se re-procesa / double-transiciona)."""
    order = _ui_unknown(order_id="lo-cxl", venue_order_id="xtb-cxl")
    store = InMemoryLiveOrderStore()
    await store.put(order)

    async def provider(venue: str, account_id: str, vid: str) -> MockLiveOrderQuery:
        return MockLiveOrderQuery(
            BrokerOrderQueryResult(
                outcome="cancelled",
                venue_order_id=vid,
                filled_quantity=0.0,
                remaining_quantity=100.0,
            )
        )

    first = await _drain_unknowns(store, query_provider=provider, limit=50)
    assert first["drained"] == 1
    assert first["resolved"] == 1

    resolved = await store.get("lo-cxl")
    assert resolved is not None
    assert resolved.status == "CANCELLED"
    # UNKNOWN ya no es listable → el siguiente tick no vuelve a tocar la fila.
    second = await _drain_unknowns(store, query_provider=provider, limit=50)
    assert second["drained"] == 0
    assert second["resolved"] == 0


@pytest.mark.asyncio
async def test_double_worker_does_not_double_process_unknown() -> None:
    """Multi-worker: un UNKNOWN reclamado en fresco por worker A no lo procesa B.

    El claim funciona como row-lock/lease: mientras A tiene el lease, B no
    vuelve a tocar la misma orden (no doble persistencia ni doble consulta).
    """
    store = InMemoryLiveOrderStore()
    order = _ui_unknown(order_id="lo-two", venue_order_id="xtb-two")
    await store.put(order)

    async def provider_unknown(venue: str, account_id: str, vid: str):
        return MockLiveOrderQuery(
            BrokerOrderQueryResult(
                outcome="unavailable",
                venue_order_id=vid,
                filled_quantity=0.0,
                remaining_quantity=100.0,
            )
        )

    # A intenta resolver; no hay cliente → unavailable → la orden queda UNKNOWN
    # pero con el lease claim fresco de A.
    a = await _drain_unknowns(
        store,
        query_provider=provider_unknown,
        limit=50,
        worker_id="worker-a",
    )
    assert a["drained"] == 1
    assert a["unavailable"] == 1

    still = await store.get("lo-two")
    assert still is not None and still.status == "UNKNOWN"

    # B en el mismo instante (claim fresco de A) NO reclama la misma orden.
    b = await _drain_unknowns(
        store,
        query_provider=provider_unknown,
        limit=50,
        worker_id="worker-b",
    )
    assert b["drained"] == 0
    assert b["unavailable"] == 0

    # Nadie duplicó: sigue siendo UNKNOWN y sin doble efecto.
    after = await store.get("lo-two")
    assert after is not None and after.status == "UNKNOWN"
